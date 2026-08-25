"""
Gemma 4 Hardware Validation — 1B variant
Run in: Kaggle notebook with GPU T4 + Internet ON + HF_TOKEN secret

Forked from test_gemma4_hardware_v2.py (Apr 24 — E4B FAIL at 25.86s).
Tests gemma-4-1b-it on the same v2 production path:
  - Same SYSTEM_PROMPT (full clinical decision support)
  - Same chat-template path via tokenizer.apply_chat_template
  - Same max_new_tokens=512
  - Same decision gate: <5s PASS / 5-15s MARGINAL / >15s FAIL

Hypothesis (Apr 24 retro): gemma-4-1b-it on T4 fp16 should hit ~6-8s warm
inference for full schema. If PASS, Phase 4 ships with 1B for edge tier
and E4B for the premium tier (cached scenarios bridging the gap).

If MARGINAL → add bitsandbytes 4-bit quant fallback.
If FAIL → cached canonical scenarios are the only path to <8s perceived latency.
"""

import os
import time
import json
from pathlib import Path

# --- 1. Auth ---------------------------------------------------------------
try:
    from kaggle_secrets import UserSecretsClient
    os.environ["HF_TOKEN"] = UserSecretsClient().get_secret("HF_TOKEN")
    print("HF_TOKEN loaded from Kaggle secrets")
except Exception as e:
    print(f"Kaggle secrets unavailable ({e}); falling back to env HF_TOKEN")

assert os.environ.get("HF_TOKEN"), (
    "HF_TOKEN not set. Kaggle: Add-ons -> Secrets -> add 'HF_TOKEN'."
)

# --- 2. Imports ------------------------------------------------------------
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

print(f"torch {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
else:
    print("WARNING: running on CPU — inference will be 10-30x slower")

# --- 3. Model selection (1B-led fallback chain) ----------------------------
# Lead with gemma-4-1b-it; fall through to gemma-3-1b-it then 4b variants
# only if 4 isn't gated to this account yet.
CANDIDATES = [
    "google/gemma-4-1b-it",
    "google/gemma-3-1b-it",
    "google/gemma-4-e4b-it",   # last resort — known FAIL at 25.86s on T4
]

model, tokenizer, model_id = None, None, None
load_start = time.time()
for candidate in CANDIDATES:
    try:
        print(f"\nAttempting to load {candidate}...")
        tokenizer = AutoTokenizer.from_pretrained(
            candidate, token=os.environ["HF_TOKEN"]
        )
        model = AutoModelForCausalLM.from_pretrained(
            candidate,
            token=os.environ["HF_TOKEN"],
            device_map="auto",
            dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )
        model_id = candidate
        break
    except Exception as e:
        print(f"  failed: {type(e).__name__}: {e}")
        continue

assert model is not None, "All candidate models failed. Check HF access approval."
load_time = time.time() - load_start
print(f"\nLoaded {model_id} in {load_time:.1f}s")

# --- 4. PRODUCTION prompt — copied verbatim from v2 (which copies server.py)
SYSTEM_PROMPT = """You are a clinical decision support assistant for Community Health Workers (CHWs)
in low-resource, remote settings. You operate fully offline. Your role is to help CHWs
make safe triage decisions based on patient symptom descriptions.

CRITICAL RULES:
- Be conservative. When uncertain, escalate urgency.
- Never make a definitive diagnosis.
- Always support — never replace — clinical judgment.
- If symptoms suggest danger, say so clearly.

PATIENT CONTEXT: You are helping a CHW assess patients in a rural/remote community.
Common presentations include: malaria, pneumonia, diarrhoea/dehydration, malnutrition,
trauma, obstetric emergencies, snake bite, meningitis.

Respond ONLY with a valid JSON object in this exact format (no other text):
{
  "urgency": "EMERGENCY",
  "urgency_color": "red",
  "primary_concern": "Suspected severe malaria with danger signs",
  "recommended_action": "Refer immediately to nearest health facility. Give pre-referral rectal artesunate if available.",
  "warning_signs": ["High fever with convulsions", "Unconsciousness", "Severe vomiting"],
  "questions_to_ask": ["Is the child able to drink?", "Any convulsions in last 24 hours?", "How long has fever lasted?"],
  "do_not_do": ["Do not wait to see if fever resolves", "Do not give aspirin to children"],
  "confidence": "high",
  "language_detected": "English"
}

Urgency levels:
- EMERGENCY: Life-threatening, refer NOW (red)
- URGENT: Serious, refer within hours (orange)
- ROUTINE: Needs treatment, can be today (yellow)
- MONITOR: Home care with instructions (green)
"""

USER_PROMPT = (
    "Patient: female, age 4. Symptoms: fever 39.5C for 2 days, vomiting, "
    "refuses to drink, lives in malaria-endemic zone."
)

MESSAGES = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": USER_PROMPT},
]


def _apply_template(messages):
    out = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, return_tensors="pt"
    )
    if isinstance(out, torch.Tensor):
        out = {"input_ids": out}
    else:
        out = dict(out)
    return {k: v.to(model.device) for k, v in out.items() if hasattr(v, "to")}


def build_inputs():
    try:
        return _apply_template(MESSAGES)
    except Exception as e:
        print(f"  chat template rejected system role ({e}); merging into user turn")
        merged = [{"role": "user", "content": SYSTEM_PROMPT + "\n\n" + USER_PROMPT}]
        return _apply_template(merged)


def run_inference(max_new_tokens=512):
    inputs = build_inputs()
    input_ids = inputs["input_ids"]
    prompt_len = input_ids.shape[1]
    t0 = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )
    dt = time.time() - t0
    n_new = outputs.shape[1] - prompt_len
    text = tokenizer.decode(outputs[0][prompt_len:], skip_special_tokens=True)
    return dt, n_new, text, prompt_len


# --- 5. Cold + warm timing -------------------------------------------------
print("\nCold inference (first call, production chat template, 512 tokens)...")
cold_dt, cold_tokens, cold_text, prompt_len = run_inference()
print(f"  prompt: {prompt_len} tokens")
print(f"  cold:   {cold_dt:.2f}s, {cold_tokens} new tokens "
      f"({cold_tokens/cold_dt:.1f} tok/s)")

print("\nWarm inference (steady state — DECISION GATE)...")
warm_dt, warm_tokens, warm_text, _ = run_inference()
print(f"  warm:   {warm_dt:.2f}s, {warm_tokens} new tokens "
      f"({warm_tokens/warm_dt:.1f} tok/s)")

# --- 6. Check JSON parseability --------------------------------------------
import re
json_match = re.search(r"\{.*\}", warm_text, re.DOTALL)
structured_ok = False
parsed = None
if json_match:
    try:
        parsed = json.loads(json_match.group())
        required = {"urgency", "urgency_color", "primary_concern",
                    "recommended_action", "warning_signs",
                    "questions_to_ask", "confidence"}
        missing = required - set(parsed.keys())
        structured_ok = not missing
        if missing:
            print(f"\nJSON parsed but missing required keys: {missing}")
    except json.JSONDecodeError as e:
        print(f"\nJSON match found but parse failed: {e}")
else:
    print("\nNo JSON object found in output.")

print("\nSample response (first 600 chars):")
print(warm_text[:600])

# --- 7. Decision gate ------------------------------------------------------
if warm_dt < 5:
    verdict = "PASS"
    action = (
        f"{model_id} ships as the production model for chw-companion. "
        "Update server.py default + memory entries."
    )
elif warm_dt < 15:
    verdict = "MARGINAL"
    action = (
        f"{model_id} usable with streaming UX (perceived latency < real). "
        "Add 4-bit quant if first-token latency > 2s."
    )
else:
    verdict = "FAIL"
    action = (
        f"{model_id} too slow even at 1B. Pivot to cached canonical "
        "scenarios + 4-bit quant; 1B/E4B both not viable as live inference."
    )

output_ok_note = (
    "structured JSON output OK" if structured_ok
    else "STRUCTURED OUTPUT FAILED — model may need different prompt strategy"
)

print(f"\n{'='*60}")
print(
    f"  VERDICT: {verdict}  (warm inference {warm_dt:.2f}s with "
    f"production prompt + 512 tokens, model={model_id})"
)
print(f"  Output: {output_ok_note}")
print(f"  Action: {action}")
print(f"{'='*60}")

# --- 8. Save result --------------------------------------------------------
result = {
    "date": time.strftime("%Y-%m-%d"),
    "test_version": "1b_production_path",
    "venue": "kaggle_notebook",
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
    "vram_gb": (
        torch.cuda.get_device_properties(0).total_memory / 1e9
        if torch.cuda.is_available() else 0
    ),
    "model_id": model_id,
    "load_time_s": round(load_time, 2),
    "prompt_tokens": prompt_len,
    "max_new_tokens": 512,
    "cold_inference_s": round(cold_dt, 2),
    "cold_tokens_per_s": round(cold_tokens / cold_dt, 1),
    "warm_inference_s": round(warm_dt, 2),
    "warm_tokens_per_s": round(warm_tokens / warm_dt, 1),
    "structured_output_ok": structured_ok,
    "verdict": verdict,
    "action": action,
    "sample_response": warm_text[:1500],
    "parsed_json": parsed if structured_ok else None,
}
out_path = Path("/kaggle/working/gemma4_hardware_test_1b.json")
out_path.write_text(json.dumps(result, indent=2))
print(f"\nSaved full result to {out_path}")
print("Download from Kaggle notebook Output tab and keep with the project.")
