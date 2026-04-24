"""
Gemma 4 Hardware Validation — v2 (Production-Realistic)
Run in: Kaggle notebook with GPU T4 + Internet ON + HF_TOKEN secret

Differences from v1 (test_gemma4_hardware.py):
  v1 used a flat prompt string + max_new_tokens=256 and echoed the input.
  v2 uses tokenizer.apply_chat_template() with system+user messages and
  max_new_tokens=512, matching exactly what server.py's /triage endpoint
  will call in production.

Decision gate (same as v1, per OMEGA_FINAL_BRIEF.md Phase 1):
  < 5s warm inference  -> PASS
  5-15s warm inference -> MARGINAL
  > 15s warm inference -> FAIL

v1 result (Apr 22): 4.74s warm, narrow PASS. Open question: does the real
production path push latency above 5s? This script answers that.
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

# --- 3. Model selection (same fallback chain as v1) -----------------------
CANDIDATES = [
    "google/gemma-4-e4b-it",
    "google/gemma-3-4b-it",
]

model, tokenizer, model_id = None, None, None
load_start = time.time()
for candidate in CANDIDATES:
    try:
        print(f"\nAttempting to load {candidate}...")
        tokenizer = AutoTokenizer.from_pretrained(candidate, token=os.environ["HF_TOKEN"])
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

# --- 4. PRODUCTION prompt — copied verbatim from server.py -----------------
# This is the exact SYSTEM_PROMPT that server.py sends to /triage.
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

# Some Gemma variants don't accept a "system" role directly via chat template;
# fall back to prefixing the system prompt onto the user turn if that happens.
# Newer transformers returns a BatchEncoding from apply_chat_template when
# return_tensors is set — not a bare tensor — so we normalise to a dict.
def _apply_template(messages):
    out = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, return_tensors="pt"
    )
    if isinstance(out, torch.Tensor):
        out = {"input_ids": out}
    else:
        out = dict(out)  # BatchEncoding -> plain dict
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

# --- 5. Cold + warm timing (production path) -------------------------------
print("\nCold inference (first call, production chat template, 512 tokens)...")
cold_dt, cold_tokens, cold_text, prompt_len = run_inference()
print(f"  prompt: {prompt_len} tokens")
print(f"  cold:   {cold_dt:.2f}s, {cold_tokens} new tokens ({cold_tokens/cold_dt:.1f} tok/s)")

print("\nWarm inference (steady state — DECISION GATE)...")
warm_dt, warm_tokens, warm_text, _ = run_inference()
print(f"  warm:   {warm_dt:.2f}s, {warm_tokens} new tokens ({warm_tokens/warm_dt:.1f} tok/s)")

# --- 6. Check output is parseable JSON (this is what server.py needs) ------
import re
json_match = re.search(r"\{.*\}", warm_text, re.DOTALL)
structured_ok = False
parsed = None
if json_match:
    try:
        parsed = json.loads(json_match.group())
        required = {"urgency", "urgency_color", "primary_concern",
                    "recommended_action", "warning_signs", "questions_to_ask", "confidence"}
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

# --- 7. Decision gate (same thresholds as v1) ------------------------------
if warm_dt < 5:
    verdict = "PASS"
    action = "Production path latency confirmed under gate. Server.py can ship as-is."
elif warm_dt < 15:
    verdict = "MARGINAL"
    action = "Add loading UX to chw-companion/app/index.html (per Phase 1.3). Consider gemma-4-1b-it."
else:
    verdict = "FAIL"
    action = "Pivot: try gemma-4-1b-it with 4-bit quantisation, or cached offline responses."

output_ok_note = "structured JSON output OK" if structured_ok else "STRUCTURED OUTPUT FAILED — model may need different prompt strategy"

print(f"\n{'='*60}")
print(f"  VERDICT: {verdict}  (warm inference {warm_dt:.2f}s with production prompt + 512 tokens)")
print(f"  Output: {output_ok_note}")
print(f"  Action: {action}")
print(f"{'='*60}")

# --- 8. Save result for repo commit ---------------------------------------
result = {
    "date": time.strftime("%Y-%m-%d"),
    "test_version": "v2_production_path",
    "venue": "kaggle_notebook",
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
    "vram_gb": torch.cuda.get_device_properties(0).total_memory / 1e9 if torch.cuda.is_available() else 0,
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
out_path = Path("/kaggle/working/gemma4_hardware_test_v2.json")
out_path.write_text(json.dumps(result, indent=2))
print(f"\nSaved full result to {out_path}")
print("Download from Kaggle notebook Output tab, commit to results/ locally.")
