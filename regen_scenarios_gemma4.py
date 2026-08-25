"""
CHW Companion — Gemma 4 Cache Regeneration Script
Run in: Kaggle notebook with GPU T4 + Internet ON + HF_TOKEN secret

Purpose: regenerate scenarios.json using a Gemma 4 model so the cache
is honest end-to-end (same model family as live inference).

Model priority chain (fastest/smallest first):
  1. principled-intelligence/gemma-4-E2B-it-text-only  (~4-6 GB, vision/audio
     encoders stripped, full LM weights identical to google/gemma-4-E2B-it)
  2. principled-intelligence/gemma-4-E4B-it-text-only  (~8-10 GB, same deal)
  3. google/gemma-4-E2B-it                             (full multimodal, ~15 GB)
  4. google/gemma-4-E4B-it                             (known ~25s, last resort)

The text-only variants are community uploads of official Google weights with
vision/audio encoder tensors removed — the language model is identical. For a
text-only clinical triage app, they are the correct choice and remain Gemma 4.

After running this script:
  1. Download /kaggle/working/scenarios_gemma4_raw.json
  2. Review the CURATION REPORT printed at the end
  3. Manually fix any urgency tier errors, language_detected mismatches,
     or do_not_do entries that read as actions not prohibitions
  4. Set "curated_at" and update "curation_note" in the JSON
  5. Replace app/scenarios.json with the curated file
  6. Update server.py MODEL_ID to match the model_id in the new file
"""

import json
import os
import re
import time
from pathlib import Path

# ── 1. Auth ─────────────────────────────────────────────────────────────────

try:
    from kaggle_secrets import UserSecretsClient
    os.environ["HF_TOKEN"] = UserSecretsClient().get_secret("HF_TOKEN")
    print("HF_TOKEN loaded from Kaggle secrets")
except Exception as e:
    print(f"Kaggle secrets unavailable ({e}); falling back to env HF_TOKEN")

assert os.environ.get("HF_TOKEN"), (
    "HF_TOKEN not set. Kaggle: Add-ons -> Secrets -> add 'HF_TOKEN'."
)

# ── 2. Hardware check ────────────────────────────────────────────────────────

import torch
print(f"torch {torch.__version__}")
print(f"CUDA: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    props = torch.cuda.get_device_properties(0)
    vram_gb = props.total_memory / 1e9
    print(f"GPU: {props.name}  VRAM: {vram_gb:.1f} GB")
else:
    print("WARNING: No GPU — inference will be very slow")

# ── 3. Model selection ───────────────────────────────────────────────────────

from transformers import AutoTokenizer, AutoModelForCausalLM

CANDIDATES = [
    "principled-intelligence/gemma-4-E2B-it-text-only",
    "principled-intelligence/gemma-4-E4B-it-text-only",
    "google/gemma-4-E2B-it",
    "google/gemma-4-E4B-it",
]

model, tokenizer, MODEL_ID = None, None, None
load_start = time.time()

for candidate in CANDIDATES:
    try:
        print(f"\nLoading {candidate}...")
        tokenizer = AutoTokenizer.from_pretrained(
            candidate, token=os.environ["HF_TOKEN"]
        )
        model = AutoModelForCausalLM.from_pretrained(
            candidate,
            token=os.environ["HF_TOKEN"],
            device_map="auto",
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )
        MODEL_ID = candidate
        print(f"Loaded in {time.time() - load_start:.1f}s")
        break
    except Exception as e:
        print(f"  failed: {type(e).__name__}: {e}")

assert model is not None, "All candidates failed. Check HF_TOKEN access."

# ── 4. Prompts (copied verbatim from server.py) ──────────────────────────────
# Keep in sync: if server.py prompts change, regenerate scenarios.

PRIMARY_PROMPT = """You are a clinical decision support assistant for Community Health Workers.
Be conservative - when uncertain, escalate urgency. Never make a definitive diagnosis.
Always support, never replace, clinical judgment.

Respond ONLY with a valid JSON object in this exact format (no other text):
{
  "urgency": "EMERGENCY",
  "urgency_color": "red",
  "recommended_action": "Refer immediately to nearest health facility for urgent care.",
  "confidence": "high"
}

Urgency levels:
- EMERGENCY: Life-threatening, refer NOW (red)
- URGENT: Serious, refer within hours (orange)
- ROUTINE: Needs treatment, can be today (yellow)
- MONITOR: Home care with instructions (green)
"""

DETAIL_PROMPT = """You are a clinical decision support assistant for Community Health Workers
in low-resource, remote settings. A primary triage verdict has already been issued.
Provide additional clinical detail to help the CHW act safely.

Common presentations in this setting: malaria, pneumonia, diarrhoea/dehydration,
malnutrition, trauma, obstetric emergencies, snake bite, meningitis.

Respond ONLY with a valid JSON object in this exact format (no other text):
{
  "primary_concern": "Suspected severe malaria with danger signs",
  "warning_signs": ["High fever with convulsions", "Unconsciousness", "Severe vomiting"],
  "questions_to_ask": ["Is the child able to drink?", "Any convulsions in last 24 hours?"],
  "do_not_do": ["Do not wait to see if fever resolves", "Do not give aspirin to children"],
  "language_detected": "English"
}
"""

# ── 5. Inference helpers ─────────────────────────────────────────────────────

def _apply_template(messages):
    out = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, return_tensors="pt"
    )
    if isinstance(out, torch.Tensor):
        out = {"input_ids": out}
    else:
        out = dict(out)
    return {k: v.to(model.device) for k, v in out.items() if hasattr(v, "to")}


def _build_inputs(system_prompt, user_text):
    msgs = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_text},
    ]
    try:
        return _apply_template(msgs)
    except Exception:
        merged = [{"role": "user", "content": system_prompt + "\n\n" + user_text}]
        return _apply_template(merged)


def _generate(system_prompt, user_text, max_new_tokens):
    inputs = _build_inputs(system_prompt, user_text)
    prompt_len = inputs["input_ids"].shape[1]
    t0 = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    dt = time.time() - t0
    n_new = outputs.shape[1] - prompt_len
    text = tokenizer.decode(outputs[0][prompt_len:], skip_special_tokens=True)
    return text, dt, n_new


def _parse_json(text):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        # Try stripping markdown code fences
        cleaned = re.sub(r"```json?\s*", "", m.group()).strip().rstrip("`")
        try:
            return json.loads(cleaned)
        except Exception:
            return None


# ── 6. Latency benchmark (3 warm runs) ──────────────────────────────────────

BENCH_USER = (
    "Patient: female, age 4. Symptoms: fever 39.5C for 2 days, "
    "vomiting twice today, refuses to drink. Lives in malaria-endemic area."
)

print("\n" + "=" * 60)
print("LATENCY BENCHMARK")
print("=" * 60)

times_primary = []
times_detail  = []

for i in range(3):
    _, dt_p, n_p = _generate(PRIMARY_PROMPT, BENCH_USER, max_new_tokens=100)
    _, dt_d, n_d = _generate(DETAIL_PROMPT,  BENCH_USER, max_new_tokens=280)
    times_primary.append(dt_p)
    times_detail.append(dt_d)
    print(f"  Run {i+1}: primary {dt_p:.1f}s ({n_p} tok)  "
          f"detail {dt_d:.1f}s ({n_d} tok)")

avg_p = sum(times_primary) / len(times_primary)
avg_d = sum(times_detail)  / len(times_detail)
print(f"\n  Average primary: {avg_p:.1f}s   detail: {avg_d:.1f}s")
print(f"  Model: {MODEL_ID}")

# ── 7. Scenario definitions ──────────────────────────────────────────────────
# user_prompt and trigger_keywords are preserved from the curated v1 cache.
# primary_response and detail_response are regenerated below.

SCENARIOS_BASE = [
    {
        "id": "malaria-pediatric-fever",
        "title_en": "Pediatric high fever in malaria zone",
        "user_prompt": "Patient: female, age 4. Symptoms: fever 39.5C for 2 days, vomiting twice today, refuses to drink water. Lives in malaria-endemic area, no bednet used.",
        "trigger_keywords": ["fever", "vomiting", "malaria"],
    },
    {
        "id": "malaria-infant-convulsion",
        "title_en": "Infant convulsion with fever — cerebral malaria risk",
        "user_prompt": "Patient: male, age 8 months. Symptoms: sudden convulsions lasting about 3 minutes, high fever 40C, eyes rolling back, unresponsive after seizure. Mother says he had fever since yesterday.",
        "trigger_keywords": ["convulsion", "fever", "seizure"],
    },
    {
        "id": "pneumonia-child-fast-breathing",
        "title_en": "Child with fast breathing and chest indrawing",
        "user_prompt": "Patient: male, age 2 years. Symptoms: cough for 4 days, breathing very fast, chest pulling in when breathing, fever 38.8C, won't eat. Respiratory rate counted at 55 breaths per minute.",
        "trigger_keywords": ["cough", "breathing", "chest"],
    },
    {
        "id": "pneumonia-elderly-confusion",
        "title_en": "Elderly pneumonia with altered mental status",
        "user_prompt": "Patient: female, age 72. Symptoms: cough with green-yellow mucus for 6 days, fever 38.2C, now confused and difficult to wake, breathing rapidly. Family says she was fine last week.",
        "trigger_keywords": ["confused", "cough", "wake"],
    },
    {
        "id": "diarrhoea-severe-dehydration-infant",
        "title_en": "Infant severe dehydration from acute diarrhoea",
        "user_prompt": "Patient: female, age 10 months. Symptoms: watery diarrhoea more than 8 times today, vomited 3 times, sunken eyes, skin pinch goes back very slowly, no tears when crying, lethargic. Last wet nappy was 6 hours ago.",
        "trigger_keywords": ["watery", "diarrhoea", "sunken"],
    },
    {
        "id": "diarrhoea-mild-child",
        "title_en": "Child mild diarrhoea, drinking well",
        "user_prompt": "Patient: male, age 3 years. Symptoms: loose stool 3 times today, no blood, drinking ORS when offered, mild stomach cramps. Still playful. No fever. Mother prepared ORS correctly.",
        "trigger_keywords": ["loose stool", "ors"],
    },
    {
        "id": "malnutrition-severe-wasting",
        "title_en": "Severe acute malnutrition with bilateral oedema",
        "user_prompt": "Patient: male, age 18 months. MUAC measured at 10.2 cm. Both feet have pitting oedema. Child is very weak, barely responds, has dry peeling skin. Mother says he stopped eating 2 weeks ago. No recent illness reported.",
        "trigger_keywords": ["muac", "pitting"],
    },
    {
        "id": "malnutrition-moderate-monitor",
        "title_en": "Moderate acute malnutrition, stable, for follow-up",
        "user_prompt": "Patient: female, age 2 years. MUAC 11.8 cm, no oedema, eating small amounts when encouraged, no acute illness. Mother reports child has been thin for 3 months. Weight-for-height Z-score estimated at minus 2.",
        "trigger_keywords": ["muac", "thin"],
    },
    {
        "id": "obstetric-postpartum-haemorrhage",
        "title_en": "Postpartum haemorrhage after home delivery",
        "user_prompt": "Patient: female, age 26, delivered at home 2 hours ago. Symptoms: heavy bleeding that has soaked through 3 cloths, feeling dizzy and weak, heart beating fast, skin pale and cold. Baby delivered normally but placenta not yet passed.",
        "trigger_keywords": ["delivered", "bleeding", "placenta"],
    },
    {
        "id": "obstetric-eclampsia-pregnant",
        "title_en": "Pregnant woman with headache, high BP, and fits",
        "user_prompt": "Patient: female, age 22, 8 months pregnant. Symptoms: severe headache since this morning, blurry vision, swollen face and hands, then sudden convulsion lasting 2 minutes. She is 34 weeks by last menstrual period.",
        "trigger_keywords": ["pregnant", "convulsion", "headache"],
    },
    {
        "id": "snakebite-adult-limb",
        "title_en": "Adult snakebite with fang marks, limb swelling",
        "user_prompt": "Patient: male, age 35. Bitten on right foot by a snake in the field 45 minutes ago. Two fang marks visible, foot and ankle swelling rapidly, severe local pain. Patient feels nauseous. Snake not identified but described as brown and large.",
        "trigger_keywords": ["snake", "fang", "swelling"],
    },
    {
        "id": "meningitis-child-classic",
        "title_en": "Child with stiff neck, photophobia, and fever",
        "user_prompt": "Patient: male, age 7. Symptoms: fever 39.8C, very stiff neck, cries when bright light is shone in eyes, severe headache, vomited twice. Symptoms developed suddenly over 12 hours. No recent travel. Not vaccinated against meningitis.",
        "trigger_keywords": ["stiff neck", "fever", "headache"],
    },
    {
        "id": "trauma-road-accident-unconscious",
        "title_en": "Road accident victim, head injury, unconscious",
        "user_prompt": "Patient: male, age 19. Involved in motorcycle accident 20 minutes ago. Not wearing helmet. Currently unconscious, bleeding from head wound, breathing irregularly, does not respond to voice. Bystanders say he was conscious briefly right after crash.",
        "trigger_keywords": ["unconscious", "accident", "helmet"],
    },
    {
        "id": "trauma-wound-adult-routine",
        "title_en": "Clean laceration from farm tool, low risk",
        "user_prompt": "Patient: female, age 34. Cut her forearm on a hoe blade while working 3 hours ago. Wound is about 4 cm long, bled initially but now stopped with cloth pressure. Wound edges are clean. Patient is alert, no fever, tetanus vaccination status unknown.",
        "trigger_keywords": ["wound", "cut", "tetanus"],
    },
    {
        "id": "swahili-homa-mtoto",
        "title_en": "Swahili: child fever and vomiting (Kiswahili prompt)",
        "user_prompt": "Mgonjwa: mtoto wa kike, miaka 3. Dalili: homa kali, joto la mwili 39C kwa siku moja, kutapika mara mbili, anakataa kunywa. Anaishi karibu na bwawa la maji. Mama anasema mtoto analala sana na hana nguvu.",
        "trigger_keywords": ["homa", "kutapika", "mtoto"],
    },
    {
        "id": "swahili-ngono-ujauzito",
        "title_en": "Swahili: pregnant woman, abdominal pain (Kiswahili prompt)",
        "user_prompt": "Mgonjwa: mwanamke, umri miaka 30, mjamzito miezi 7. Dalili: maumivu makali ya tumbo yanayoanza na kuacha, damu kidogo ukeni, kichwa kinauma. Mtoto hajahisi kucheza tangu asubuhi.",
        "trigger_keywords": ["mjamzito", "maumivu", "damu"],
    },
    {
        "id": "french-paludisme-enfant",
        "title_en": "French: child malaria symptoms (French prompt)",
        "user_prompt": "Patient : garçon, 5 ans. Symptômes : fièvre à 39,8°C depuis deux jours, frissons, vomissements à trois reprises, refuse de boire. Vit dans une zone de paludisme. Test rapide non disponible au village. L'enfant est fatigué et pleure beaucoup.",
        "trigger_keywords": ["fièvre", "paludisme", "vomissements"],
    },
    {
        "id": "french-diarrhee-adulte",
        "title_en": "French: adult diarrhoea, moderate dehydration (French prompt)",
        "user_prompt": "Patient : homme, 42 ans. Symptômes : diarrhée liquide depuis hier soir, huit selles dans la nuit, légèrement étourdi, lèvres sèches, boit encore un peu d'eau. Pas de sang dans les selles. Pas de fièvre. Travaille aux champs sous forte chaleur.",
        "trigger_keywords": ["diarrhée", "selles", "étourdi"],
    },
    {
        "id": "hausa-zazzabi-jariiri",
        "title_en": "Hausa: infant fever and refusal to feed (Hausa prompt)",
        "user_prompt": "Majiyyaci: yaro, watanni 6. Alamomi: zazzabi mai tsanani, kin sha nono, kuka ba ya tsayawa, jiki na zafi sosai. Uwa ta ce yaro bai yi barci dare baki dayan ba. Ana zaune kusa da ruwa mai tsayawa.",
        "trigger_keywords": ["zazzabi", "zafi", "yaro"],
    },
    {
        "id": "malaria-adult-uncomplicated-monitor",
        "title_en": "Adult uncomplicated malaria, RDT positive, treated",
        "user_prompt": "Patient: male, age 28. RDT positive for malaria. Fever 38.4C, mild headache and body aches, eating small amounts, drinking water. Started artemisinin-based treatment yesterday per CHW protocol. No danger signs present. Asks if he can continue working.",
        "trigger_keywords": ["malaria", "rdt", "treatment"],
    },
]

# ── 8. Expected urgency tier (for curation validation) ──────────────────────
# Used to flag model outputs that deviate. These are clinical ground-truth.

EXPECTED_URGENCY = {
    "malaria-pediatric-fever":           "URGENT",
    "malaria-infant-convulsion":         "EMERGENCY",
    "pneumonia-child-fast-breathing":    "URGENT",
    "pneumonia-elderly-confusion":       "EMERGENCY",
    "diarrhoea-severe-dehydration-infant": "EMERGENCY",
    "diarrhoea-mild-child":              "MONITOR",
    "malnutrition-severe-wasting":       "EMERGENCY",
    "malnutrition-moderate-monitor":     "MONITOR",
    "obstetric-postpartum-haemorrhage":  "EMERGENCY",
    "obstetric-eclampsia-pregnant":      "EMERGENCY",
    "snakebite-adult-limb":              "EMERGENCY",
    "meningitis-child-classic":          "EMERGENCY",
    "trauma-road-accident-unconscious":  "EMERGENCY",
    "trauma-wound-adult-routine":        "ROUTINE",
    "swahili-homa-mtoto":                "URGENT",
    "swahili-ngono-ujauzito":            "EMERGENCY",
    "french-paludisme-enfant":           "URGENT",
    "french-diarrhee-adulte":            "URGENT",
    "hausa-zazzabi-jariiri":             "URGENT",
    "malaria-adult-uncomplicated-monitor": "ROUTINE",
}

URGENCY_COLOR = {
    "EMERGENCY": "red",
    "URGENT":    "orange",
    "ROUTINE":   "yellow",
    "MONITOR":   "green",
}

# ── 9. Generation loop ───────────────────────────────────────────────────────

print("\n" + "=" * 60)
print(f"GENERATING {len(SCENARIOS_BASE)} SCENARIOS — model: {MODEL_ID}")
print("=" * 60)

results = []
curation_flags = []
total_start = time.time()

for i, sc in enumerate(SCENARIOS_BASE):
    print(f"\n[{i+1:02d}/{len(SCENARIOS_BASE)}] {sc['id']}")

    user_text = sc["user_prompt"]

    # Primary
    p_text, p_dt, p_tok = _generate(PRIMARY_PROMPT, user_text, max_new_tokens=100)
    primary = _parse_json(p_text)
    if primary is None:
        print(f"  PRIMARY PARSE FAIL — raw: {p_text[:200]}")
        primary = {
            "urgency":            "URGENT",
            "urgency_color":      "orange",
            "recommended_action": "Unable to parse response. Escalate to clinic.",
            "confidence":         "low",
            "_parse_failed":      True,
        }
    print(f"  primary  {p_dt:.1f}s  urgency={primary.get('urgency','?')}")

    # Detail
    d_text, d_dt, d_tok = _generate(DETAIL_PROMPT, user_text, max_new_tokens=280)
    detail = _parse_json(d_text)
    if detail is None:
        print(f"  DETAIL PARSE FAIL — raw: {d_text[:200]}")
        detail = {
            "primary_concern":  "Unable to parse response.",
            "warning_signs":    ["Consult a nurse or doctor."],
            "questions_to_ask": ["What are the main symptoms?"],
            "do_not_do":        ["Do not delay referral."],
            "language_detected": "English",
            "_parse_failed":    True,
        }
    print(f"  detail   {d_dt:.1f}s  lang={detail.get('language_detected','?')}")

    # Validation flags
    expected = EXPECTED_URGENCY.get(sc["id"])
    got = primary.get("urgency", "").upper()
    if got != expected:
        flag = f"URGENCY MISMATCH  {sc['id']}: expected {expected}, got {got}"
        print(f"  ⚠ {flag}")
        curation_flags.append(flag)

    lang = detail.get("language_detected", "")
    if sc["id"].startswith("swahili") and lang not in ("Swahili", "Kiswahili"):
        flag = f"LANG MISMATCH  {sc['id']}: expected Swahili, got {lang!r}"
        print(f"  ⚠ {flag}")
        curation_flags.append(flag)
    if sc["id"].startswith("french") and "French" not in lang:
        flag = f"LANG MISMATCH  {sc['id']}: expected French, got {lang!r}"
        print(f"  ⚠ {flag}")
        curation_flags.append(flag)
    if sc["id"].startswith("hausa") and "Hausa" not in lang:
        flag = f"LANG MISMATCH  {sc['id']}: expected Hausa, got {lang!r}"
        print(f"  ⚠ {flag}")
        curation_flags.append(flag)

    # Enforce correct color if urgency parses correctly
    if got in URGENCY_COLOR:
        primary["urgency_color"] = URGENCY_COLOR[got]

    results.append({
        "id":               sc["id"],
        "title_en":         sc["title_en"],
        "user_prompt":      sc["user_prompt"],
        "trigger_keywords": sc["trigger_keywords"],
        "primary_response": primary,
        "detail_response":  detail,
        "_meta": {
            "primary_s":   round(p_dt, 2),
            "detail_s":    round(d_dt, 2),
            "primary_tok": p_tok,
            "detail_tok":  d_tok,
        },
    })

total_s = time.time() - total_start
print(f"\nGeneration complete: {total_s:.0f}s total  "
      f"({total_s/len(SCENARIOS_BASE):.0f}s/scenario)")

# ── 10. Build output JSON ────────────────────────────────────────────────────

output = {
    "version":      "2",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "model_id":     MODEL_ID,
    "scenarios":    results,
    "gen_meta": {
        "gpu":            torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
        "vram_gb":        round(vram_gb, 1) if torch.cuda.is_available() else 0,
        "transformers":   __import__("transformers").__version__,
        "total_seconds":  round(total_s, 1),
        "avg_primary_s":  round(avg_p, 2),
        "avg_detail_s":   round(avg_d, 2),
    },
    "curated_at":     "",
    "curation_note":  "PENDING — review curation flags below before setting this field",
}

out_path = Path("/kaggle/working/scenarios_gemma4_raw.json")
out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
print(f"\nSaved: {out_path}")
print("Download from Kaggle notebook Output tab.")

# ── 11. Curation report ──────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("CURATION REPORT")
print("=" * 60)

urgency_counts = {}
parse_failures = []
for sc in results:
    u = sc["primary_response"].get("urgency", "UNKNOWN")
    urgency_counts[u] = urgency_counts.get(u, 0) + 1
    if sc["primary_response"].get("_parse_failed") or sc["detail_response"].get("_parse_failed"):
        parse_failures.append(sc["id"])

print("\nUrgency distribution:")
for tier, n in sorted(urgency_counts.items()):
    expected_n = sum(1 for v in EXPECTED_URGENCY.values() if v == tier)
    print(f"  {tier:12s} {n:2d}  (expected {expected_n})")

if parse_failures:
    print(f"\nParse failures ({len(parse_failures)}):")
    for s in parse_failures:
        print(f"  {s}")

if curation_flags:
    print(f"\nFlags requiring manual review ({len(curation_flags)}):")
    for f in curation_flags:
        print(f"  ⚠  {f}")
else:
    print("\n✓ No urgency or language flags. Quick review still recommended.")

print("""
NEXT STEPS
──────────
1. Download /kaggle/working/scenarios_gemma4_raw.json
2. Fix any flagged urgency mismatches in primary_response
3. Fix any language_detected mismatches in detail_response
4. Review do_not_do entries — they must be prohibitions ("Do not X"),
   not actions ("Assess for X"). Rewrite any that read as instructions.
5. Set "curated_at" to today's date (YYYY-MM-DD)
6. Update "curation_note" to describe what you changed
7. Remove all "_meta" and "_parse_failed" keys from the JSON
8. Replace app/scenarios.json with the curated file
9. Update server.py:  MODEL_ID = "{model_id}"
10. Run verify: python -c "import json; d=json.load(open('scenarios.json')); \\
    print(len(d['scenarios']), 'scenarios, model:', d['model_id'])"
""".format(model_id=MODEL_ID))
