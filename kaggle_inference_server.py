"""
CHW Companion — Kaggle T4 Inference Server
==========================================
Run this in a Kaggle notebook (GPU T4, Internet ON, HF_TOKEN secret).

It starts the Flask backend + an ngrok tunnel so the frontend at
app/index.html can call the live Gemma 4 endpoints from any browser.

Usage in a Kaggle notebook cell:
    !pip install -q flask flask-cors pyngrok transformers accelerate
    exec(open("/kaggle/input/chw-companion-backend/kaggle_inference_server.py").read())

Or paste each section into its own cell.

Public URL is printed as:
    BACKEND_URL = https://xxxx.ngrok-free.app
Point the frontend at this URL by editing the BACKEND_URL line in index.html,
OR paste it into the browser console:
    window.CHW_BACKEND = "https://xxxx.ngrok-free.app";

Endpoints exposed:
    GET  /health
    POST /triage/primary    (~7s  warm, Gemma 4 E4B)
    POST /triage/detail     (~25s warm, streams behind primary)
    GET  /languages
"""

# ── Cell 1: Install dependencies ────────────────────────────────────────────
import subprocess
subprocess.run([
    "pip", "install", "-q",
    "flask", "flask-cors", "pyngrok",
    "transformers>=4.51", "accelerate",
], check=True)

# ── Cell 2: Auth ─────────────────────────────────────────────────────────────
import os

try:
    from kaggle_secrets import UserSecretsClient
    secrets = UserSecretsClient()
    os.environ["HF_TOKEN"] = secrets.get_secret("HF_TOKEN")
    print("HF_TOKEN loaded from Kaggle secrets")
except Exception as e:
    print(f"Kaggle secrets unavailable ({e}); falling back to env HF_TOKEN")

assert os.environ.get("HF_TOKEN"), (
    "HF_TOKEN not set. Kaggle: Add-ons → Secrets → add 'HF_TOKEN'."
)

# ngrok auth token — get a free one at https://dashboard.ngrok.com/
# Add it to Kaggle secrets as NGROK_TOKEN
try:
    NGROK_TOKEN = secrets.get_secret("NGROK_TOKEN")
    os.environ["NGROK_TOKEN"] = NGROK_TOKEN
    print("NGROK_TOKEN loaded from Kaggle secrets")
except Exception:
    NGROK_TOKEN = os.environ.get("NGROK_TOKEN", "")
    if not NGROK_TOKEN:
        print("WARNING: NGROK_TOKEN not set — public URL will not be created.")
        print("  Get a free token at https://dashboard.ngrok.com/ and add as Kaggle secret.")

# ── Cell 3: Import the Flask app from server.py ─────────────────────────────
# server.py must be uploaded to the Kaggle dataset or pasted inline.
# Either way, it registers the Flask routes. We just start it differently.

import sys
import importlib.util
from pathlib import Path

SERVER_PATH = Path("/kaggle/input/chw-companion-backend/server.py")
if SERVER_PATH.exists():
    spec = importlib.util.spec_from_file_location("server", SERVER_PATH)
    server_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_mod)
    app = server_mod.app
    print(f"Loaded Flask app from {SERVER_PATH}")
else:
    # Fallback: inline a minimal version of server.py
    print(f"server.py not found at {SERVER_PATH}. Using inline server.")
    print("Upload backend/server.py as a Kaggle dataset named 'chw-companion-backend'.")

    import json
    import re
    from flask import Flask, request, jsonify
    from flask_cors import CORS

    app = Flask(__name__)
    CORS(app)

    MODEL_ID = os.environ.get("CHW_MODEL_ID", "google/gemma-4-e4b-it")

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

    SAFETY_DISCLAIMER = (
        "Decision support tool only. Not a diagnosis. "
        "Always use your clinical judgment. When uncertain, escalate urgency."
    )

    _model = _tokenizer = None
    _load_failed = False

    def load_gemma():
        global _load_failed
        if _load_failed:
            return None, None
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM
            if not torch.cuda.is_available():
                print("No CUDA GPU. Using mock mode.")
                _load_failed = True
                return None, None
            print(f"Loading {MODEL_ID}...")
            tok = AutoTokenizer.from_pretrained(MODEL_ID, token=os.environ.get("HF_TOKEN"))
            mdl = AutoModelForCausalLM.from_pretrained(
                MODEL_ID, token=os.environ.get("HF_TOKEN"),
                device_map="auto", dtype=torch.float16,
            )
            print("Gemma 4 loaded.")
            return mdl, tok
        except Exception as e:
            print(f"Load failed: {e}. Using mock mode.")
            _load_failed = True
            return None, None

    def get_model():
        global _model, _tokenizer
        if _model is None and not _load_failed:
            _model, _tokenizer = load_gemma()
        return _model, _tokenizer

    def _generate_json(system_prompt, user_text, max_new_tokens):
        model, tok = get_model()
        if model is None:
            return None
        import torch
        msgs = [{"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_text}]
        try:
            inputs = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt")
        except Exception:
            merged = [{"role": "user", "content": system_prompt + "\n\n" + user_text}]
            inputs = tok.apply_chat_template(merged, add_generation_prompt=True, return_tensors="pt")
        if isinstance(inputs, dict):
            inputs = {k: v.to(model.device) for k, v in inputs.items() if hasattr(v, "to")}
        else:
            inputs = {"input_ids": inputs.to(model.device)}
        prompt_len = inputs["input_ids"].shape[1]
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=max_new_tokens,
                                 do_sample=False, pad_token_id=tok.eos_token_id)
        text = tok.decode(out[0][prompt_len:], skip_special_tokens=True)
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            return None

    def mock_primary(s):
        s = s.lower()
        if any(w in s for w in ["convuls", "unconscious", "not breathing", "heavy bleed"]):
            return {"urgency": "EMERGENCY", "urgency_color": "red",
                    "recommended_action": "Refer immediately.", "confidence": "high"}
        if any(w in s for w in ["fever", "malaria", "vomit", "diarrhea", "diarrhoea"]):
            return {"urgency": "URGENT", "urgency_color": "orange",
                    "recommended_action": "Refer to clinic within 4 hours.", "confidence": "medium"}
        return {"urgency": "ROUTINE", "urgency_color": "yellow",
                "recommended_action": "Assess and treat per CHW protocol.", "confidence": "medium"}

    def mock_detail(s):
        return {"primary_concern": "Assessment required",
                "warning_signs": ["Worsening symptoms", "New fever"],
                "questions_to_ask": ["How long have symptoms been present?"],
                "do_not_do": ["Do not dismiss without full assessment"]}

    @app.route("/health")
    def health():
        m, _ = get_model()
        return jsonify({"status": "ok", "model": MODEL_ID,
                        "mode": "gemma4" if m else "mock"})

    @app.route("/triage/primary", methods=["POST"])
    def triage_primary():
        data = request.get_json(silent=True) or {}
        symptoms = (data.get("symptoms") or "").strip()
        if len(symptoms) < 5:
            return jsonify({"error": "Please describe symptoms in more detail"}), 400
        result = _generate_json(PRIMARY_PROMPT, f"Patient symptoms: {symptoms}", 100) \
                 or mock_primary(symptoms)
        result["disclaimer"] = SAFETY_DISCLAIMER
        return jsonify(result)

    @app.route("/triage/detail", methods=["POST"])
    def triage_detail():
        data = request.get_json(silent=True) or {}
        symptoms = (data.get("symptoms") or "").strip()
        if len(symptoms) < 5:
            return jsonify({"error": "Please describe symptoms in more detail"}), 400
        result = _generate_json(DETAIL_PROMPT, f"Patient symptoms: {symptoms}", 280) \
                 or mock_detail(symptoms)
        result["disclaimer"] = SAFETY_DISCLAIMER
        return jsonify(result)

    @app.route("/languages")
    def languages():
        return jsonify({"supported": ["English", "French", "Swahili", "Hausa", "Arabic",
                                       "Hindi", "Portuguese", "Amharic", "Yoruba", "Zulu"],
                        "note": "Gemma 4 handles 140+ languages natively."})

# ── Cell 4: Start Flask + ngrok tunnel ───────────────────────────────────────
import threading
from pyngrok import ngrok, conf

PORT = 5000

def run_flask():
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)

# Start Flask in background thread
flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()
print(f"Flask started on port {PORT}")

# Create ngrok tunnel
if os.environ.get("NGROK_TOKEN"):
    conf.get_default().auth_token = os.environ["NGROK_TOKEN"]
    tunnel = ngrok.connect(PORT, "http")
    BACKEND_URL = tunnel.public_url
    print(f"\n{'='*60}")
    print(f"BACKEND_URL = {BACKEND_URL}")
    print(f"{'='*60}")
    print(f"\nPaste this in your browser console to connect the frontend:")
    print(f'  window.CHW_BACKEND = "{BACKEND_URL}";')
    print(f"\nOr test directly:")
    print(f"  curl {BACKEND_URL}/health")
    print(f"  curl -X POST {BACKEND_URL}/triage/primary \\")
    print(f'       -H "Content-Type: application/json" \\')
    print(f'       -d \'{{"symptoms":"4yr girl, fever 39C, vomiting, malaria zone"}}\'')
else:
    print("\nNo NGROK_TOKEN — Flask is running locally on this Kaggle kernel.")
    print("To expose publicly: add NGROK_TOKEN secret and re-run.")
    print(f"Local test: curl http://localhost:{PORT}/health")

# ── Cell 5: Keep alive (run last, blocks the cell) ───────────────────────────
# Uncomment the line below if you want the notebook to stay alive indefinitely.
# import time; [time.sleep(60) for _ in iter(int, 1)]
