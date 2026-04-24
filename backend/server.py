"""
CHW Companion - Gemma 4 Backend
Two-phase triage: primary (fast, ~7s on Kaggle T4) + detail (slow, ~25s).

Deployment note: local CPU inference of Gemma 4 E4B is too slow to be useful
(~30-60s per call). Local runs default to MOCK mode. The real-inference path
is for a Kaggle notebook session or a self-hosted GPU instance.
"""

import json
import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SAFETY_DISCLAIMER = (
    "Decision support tool only. Not a diagnosis. "
    "Always use your clinical judgment. When uncertain, escalate urgency."
)

MODEL_ID = os.environ.get("CHW_MODEL_ID", "google/gemma-4-e4b-it")

# ── Prompts ──────────────────────────────────────────────────────────────────
# Primary: 4 fields, ~60 output tokens, target ~7s warm on Kaggle T4.
# Used for the initial emergency decision the CHW sees first.

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

# Detail: 4 fields, ~160 output tokens, target ~20s warm. Streams in behind
# the primary response while the CHW reads the urgency decision.

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
  "do_not_do": ["Do not wait to see if fever resolves", "Do not give aspirin to children"]
}
"""

# ── Gemma 4 loader (Kaggle/GPU path) ────────────────────────────────────────

_model = None
_tokenizer = None
_load_failed = False


def load_gemma():
    """Load Gemma 4 via AutoModelForCausalLM + auto-dispatch.
    Returns (model, tokenizer) or (None, None) if loading fails.
    Validated config (Apr 24 2026): device_map='auto' + fp16 + CPU offload on T4.
    Bails immediately without network calls if CHW_MOCK_ONLY is set or no CUDA GPU
    is present (CPU inference on E4B takes 30-60s per call - not useful)."""
    global _load_failed
    if _load_failed:
        return None, None
    if os.environ.get("CHW_MOCK_ONLY"):
        print("CHW_MOCK_ONLY set; skipping Gemma 4 load.")
        _load_failed = True
        return None, None
    try:
        import torch
    except ImportError:
        print("torch not installed; using MOCK mode.")
        _load_failed = True
        return None, None
    if not torch.cuda.is_available():
        print("No CUDA GPU; Gemma 4 E4B needs a GPU to be usable. Using MOCK mode.")
        _load_failed = True
        return None, None
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        hf_token = os.environ.get("HF_TOKEN")
        print(f"Loading {MODEL_ID} (device_map=auto, fp16)...")
        tok = AutoTokenizer.from_pretrained(MODEL_ID, token=hf_token)
        mdl = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            token=hf_token,
            device_map="auto",
            dtype=torch.float16,
        )
        print("Gemma 4 loaded.")
        return mdl, tok
    except Exception as e:
        print(f"Gemma 4 load failed: {e}")
        print("Falling back to MOCK mode.")
        _load_failed = True
        return None, None


def get_model():
    global _model, _tokenizer
    if _model is None and not _load_failed:
        _model, _tokenizer = load_gemma()
    return _model, _tokenizer


def _apply_template(tok, model, messages):
    """Normalise apply_chat_template across transformers versions."""
    out = tok.apply_chat_template(
        messages, add_generation_prompt=True, return_tensors="pt"
    )
    import torch
    if isinstance(out, torch.Tensor):
        out = {"input_ids": out}
    else:
        out = dict(out)
    return {k: v.to(model.device) for k, v in out.items() if hasattr(v, "to")}


def _generate_json(system_prompt: str, user_text: str, max_new_tokens: int) -> dict | None:
    """Run one Gemma 4 inference call. Returns parsed JSON or None."""
    model, tok = get_model()
    if model is None:
        return None
    import torch
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    try:
        inputs = _apply_template(tok, model, messages)
    except Exception:
        # Gemma variants that reject system role: merge into user turn
        merged = [{"role": "user", "content": system_prompt + "\n\n" + user_text}]
        inputs = _apply_template(tok, model, merged)
    prompt_len = inputs["input_ids"].shape[1]
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tok.eos_token_id,
        )
    text = tok.decode(outputs[0][prompt_len:], skip_special_tokens=True)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


# ── Mock responses (local dev + fallback) ───────────────────────────────────

def mock_primary(symptoms: str) -> dict:
    s = symptoms.lower()
    if any(w in s for w in ["convuls", "unconscious", "not breathing", "bleed heavily"]):
        return {
            "urgency": "EMERGENCY",
            "urgency_color": "red",
            "recommended_action": "Refer immediately to nearest health facility. Do not delay.",
            "confidence": "high",
        }
    if any(w in s for w in ["fever", "malaria", "vomit", "diarrhea", "diarrhoea"]):
        return {
            "urgency": "URGENT",
            "urgency_color": "orange",
            "recommended_action": (
                "Perform RDT for malaria if available. Assess hydration. "
                "Refer to clinic within 4 hours if RDT positive or signs of dehydration."
            ),
            "confidence": "medium",
        }
    return {
        "urgency": "ROUTINE",
        "urgency_color": "yellow",
        "recommended_action": "Complete full assessment. Treat per CHW protocols. Follow up in 2 days.",
        "confidence": "medium",
    }


def mock_detail(symptoms: str) -> dict:
    s = symptoms.lower()
    if any(w in s for w in ["fever", "malaria", "vomit"]):
        return {
            "primary_concern": "Suspected febrile illness - possible malaria or gastrointestinal infection",
            "warning_signs": ["Unable to drink", "Sunken eyes", "Fever >38.5C", "Vomiting repeatedly"],
            "questions_to_ask": [
                "How long has the fever been present?",
                "Is the patient able to drink fluids?",
                "Any recent travel to malaria-endemic area?",
            ],
            "do_not_do": [
                "Do not give aspirin to children under 12",
                "Do not withhold fluids",
            ],
        }
    if any(w in s for w in ["convuls", "unconscious"]):
        return {
            "primary_concern": "Potential life-threatening emergency",
            "warning_signs": ["Loss of consciousness", "Convulsions", "Severe bleeding"],
            "questions_to_ask": ["Is the patient breathing?", "Any known medical conditions?"],
            "do_not_do": ["Do not leave patient alone", "Do not give food/water if unconscious"],
        }
    return {
        "primary_concern": "Non-emergency presentation requiring assessment",
        "warning_signs": ["Worsening symptoms", "New fever", "Unable to eat or drink"],
        "questions_to_ask": [
            "How long have symptoms been present?",
            "Any other household members affected?",
            "Current medications?",
        ],
        "do_not_do": ["Do not dismiss symptoms without full assessment"],
    }


# ── Inference orchestration ─────────────────────────────────────────────────

def run_primary(symptoms: str) -> dict:
    result = _generate_json(PRIMARY_PROMPT, f"Patient symptoms: {symptoms}", max_new_tokens=100)
    return result or mock_primary(symptoms)


def run_detail(symptoms: str) -> dict:
    result = _generate_json(DETAIL_PROMPT, f"Patient symptoms: {symptoms}", max_new_tokens=280)
    return result or mock_detail(symptoms)


def _request_context():
    data = request.get_json(silent=True) or {}
    symptoms = (data.get("symptoms") or "").strip()
    if len(symptoms) < 5:
        return None, None, (jsonify({"error": "Please describe symptoms in more detail"}), 400)
    age = data.get("patient_age", "unknown")
    sex = data.get("patient_sex", "unknown")
    return symptoms, {"age": age, "sex": sex, "symptoms_reported": symptoms}, None


# ── API Routes ───────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Fast health check - never triggers a model load. Reports whatever
    state the model is currently in (loaded / failed / not yet attempted)."""
    if _model is not None:
        mode = "gemma4"
    elif _load_failed:
        mode = "mock"
    else:
        mode = "not_loaded"
    return jsonify({
        "status": "ok",
        "model": MODEL_ID,
        "mode": mode,
    })


@app.route("/triage/primary", methods=["POST"])
def triage_primary():
    """Fast path: urgency decision in ~7s on Kaggle T4, instant in mock mode."""
    symptoms, ctx, err = _request_context()
    if err:
        return err
    result = run_primary(f"{ctx['sex']}, age {ctx['age']}. Symptoms: {symptoms}")
    result["patient_context"] = ctx
    result["disclaimer"] = SAFETY_DISCLAIMER
    return jsonify(result)


@app.route("/triage/detail", methods=["POST"])
def triage_detail():
    """Slow path: primary_concern + warnings + questions + do_not_do (~25s on T4)."""
    symptoms, ctx, err = _request_context()
    if err:
        return err
    result = run_detail(f"{ctx['sex']}, age {ctx['age']}. Symptoms: {symptoms}")
    result["patient_context"] = ctx
    result["disclaimer"] = SAFETY_DISCLAIMER
    return jsonify(result)


@app.route("/triage", methods=["POST"])
def triage_combined():
    """Backward-compat: returns primary + detail merged. ~32s on T4 real inference."""
    symptoms, ctx, err = _request_context()
    if err:
        return err
    full_symptoms = f"{ctx['sex']}, age {ctx['age']}. Symptoms: {symptoms}"
    primary = run_primary(full_symptoms)
    detail = run_detail(full_symptoms)
    merged = {**primary, **detail, "patient_context": ctx, "disclaimer": SAFETY_DISCLAIMER}
    return jsonify(merged)


@app.route("/languages", methods=["GET"])
def languages():
    return jsonify({
        "supported": [
            "English", "French", "Spanish", "Portuguese", "Swahili",
            "Hausa", "Arabic", "Hindi", "Bengali", "Amharic",
            "Yoruba", "Igbo", "Zulu", "Somali", "Tigrinya",
        ],
        "note": "Gemma 4 handles 35+ languages natively. Type in any language.",
    })


if __name__ == "__main__":
    print("CHW Companion Backend - starting")
    print(f"Model: {MODEL_ID}")
    print("Endpoints: /health, /triage/primary, /triage/detail, /triage, /languages")
    print("Mode: mock by default; real Gemma 4 if transformers + HF_TOKEN + GPU available")
    app.run(host="0.0.0.0", port=5000, debug=True)
