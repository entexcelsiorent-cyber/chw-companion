"""
Gemma 4 Hardware Validation — Kaggle Notebook Cell
Run in: Kaggle notebook with GPU T4 accelerator + Internet ON
HF auth: add secret 'HF_TOKEN' via Kaggle Add-ons -> Secrets

Decision gate (per OMEGA_FINAL_BRIEF.md Phase 1):
  < 5s warm inference  -> PASS     (proceed with Gemma 4 as planned)
  5-15s warm inference -> MARGINAL (proceed, add loading UX)
  > 15s warm inference -> FAIL     (pivot to smaller variant or API)

The test separates three costs:
  1. Model load (one-time, amortized across a user session)
  2. Cold inference (first call, includes CUDA kernel compile)
  3. Warm inference (steady-state — this is the decision-gate number)
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
    "HF_TOKEN not set. Kaggle: Add-ons -> Secrets -> add 'HF_TOKEN'. "
    "Local: export HF_TOKEN=..."
)

# --- 2. Install / imports --------------------------------------------------
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

print(f"torch {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
else:
    print("WARNING: running on CPU — inference will be 10-30x slower")

# --- 3. Model selection (with availability fallback) -----------------------
# Primary: the ID referenced in chw-companion/backend/server.py.
# Fallback: Gemma 3 4B instruct — same size class, publicly released, gated but accessible.
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

assert model is not None, (
    "All candidate models failed. Check HF access approval at "
    "https://huggingface.co/google (Gemma models are gated)."
)
load_time = time.time() - load_start
print(f"\nLoaded {model_id} in {load_time:.1f}s")
if model_id != CANDIDATES[0]:
    print(f"NOTE: used fallback model. Update server.py MODEL_ID if this is the final choice.")

# --- 4. Clinical prompt (matches server.py system prompt intent) -----------
CLINICAL_PROMPT = (
    "You are a clinical decision support assistant for Community Health Workers "
    "in low-resource, remote settings. Respond in JSON with keys: urgency, "
    "urgency_color, primary_concern, recommended_action, warning_signs, "
    "questions_to_ask, confidence.\n\n"
    "Patient: female, age 4. Symptoms: fever 39.5C for 2 days, vomiting, "
    "refuses to drink, lives in malaria-endemic zone."
)

def run_inference(prompt, max_new_tokens=256):
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
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
    n_new = outputs.shape[1] - inputs["input_ids"].shape[1]
    text = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    return dt, n_new, text

# --- 5. Cold + warm timing -------------------------------------------------
print("\nCold inference (first call — includes kernel compile)...")
cold_dt, cold_tokens, cold_text = run_inference(CLINICAL_PROMPT)
print(f"  {cold_dt:.2f}s, {cold_tokens} new tokens ({cold_tokens/cold_dt:.1f} tok/s)")

print("\nWarm inference (steady state — DECISION GATE)...")
warm_dt, warm_tokens, warm_text = run_inference(CLINICAL_PROMPT)
print(f"  {warm_dt:.2f}s, {warm_tokens} new tokens ({warm_tokens/warm_dt:.1f} tok/s)")

print("\nSample response (first 400 chars):")
print(warm_text[:400])

# --- 6. Decision gate ------------------------------------------------------
if warm_dt < 5:
    verdict = "PASS"
    action = "Proceed with Gemma 4 strategy as planned."
elif warm_dt < 15:
    verdict = "MARGINAL"
    action = "Proceed + add loading UX; consider gemma-4-1b-it for edge deployment."
else:
    verdict = "FAIL"
    action = "Pivot: try gemma-4-1b-it with 4-bit quantisation, or restructure CHW around API + cached offline responses."

print(f"\n{'='*56}")
print(f"  VERDICT: {verdict}  (warm inference {warm_dt:.2f}s)")
print(f"  Action:  {action}")
print(f"{'='*56}")

# --- 7. Save results -------------------------------------------------------
result = {
    "date": "2026-04-22",
    "venue": "kaggle_notebook",
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU",
    "vram_gb": torch.cuda.get_device_properties(0).total_memory / 1e9 if torch.cuda.is_available() else 0,
    "model_id": model_id,
    "load_time_s": round(load_time, 2),
    "cold_inference_s": round(cold_dt, 2),
    "cold_tokens_per_s": round(cold_tokens / cold_dt, 1),
    "warm_inference_s": round(warm_dt, 2),
    "warm_tokens_per_s": round(warm_tokens / warm_dt, 1),
    "verdict": verdict,
    "action": action,
    "sample_response": warm_text[:800],
}
out_path = Path("/kaggle/working/gemma4_hardware_test.json")
out_path.write_text(json.dumps(result, indent=2))
print(f"\nSaved full result to {out_path}")
print("Download from the Kaggle notebook's Output tab, commit to results/ locally.")
