# 🏥 CHW Companion — Offline AI Triage Assistant
### Gemma 4 Good Hackathon 2026 | Kaggle × Google DeepMind

> **Empowering 1.5 million Community Health Workers with offline AI clinical decision support.**

---

## The Problem
2 billion people live without reliable access to healthcare. 1.5 million Community Health 
Workers operate daily in remote areas with zero clinical decision support. A CHW sees a 
child with a fever and a rash — no doctor, no internet, no guidance. Wrong decisions cost 
lives. Right decisions save them.

## The Solution
CHW Companion runs **Gemma 4 E4B entirely on-device** — no internet required. A CHW 
describes symptoms in plain language (any of 35+ supported languages). The app returns a 
structured triage decision, urgency level, and clear next action in seconds.

## Why Gemma 4?
- **Offline-first**: Edge 4B model runs on a $50 Android device
- **Multilingual**: 35+ languages natively — no translation API needed
- **Open weights**: Apache 2.0 license, deployable in restricted environments
- **Safe by design**: Tuned for helpful, conservative, non-harmful outputs

---

## Demo
[🎥 Video Demo] | [🌐 Live Demo]

**Scenario**: 4-year-old girl, fever for 2 days, vomiting, refuses to drink.
**Output**: URGENT — Suspected malaria. Perform RDT. Refer within 4 hours.

---

## Quick Start

### Run the UI (no setup needed)
Open `app/index.html` in any mobile browser. Works offline immediately with built-in 
Gemma 4 simulation for demo purposes.

### Run with real Gemma 4

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Start backend (downloads Gemma 4 E4B on first run ~2.5GB)
python backend/server.py

# Open app/index.html in browser
```

### Kaggle Notebook
See `kaggle/notebook.ipynb` for the full Kaggle submission notebook running Gemma 4 
inference in the Kaggle environment.

---

## Impact

| Metric | Value |
|---|---|
| Target users | 1.5M Community Health Workers globally |
| Underserved population | 2 billion people |
| Storage requirement | ~2.5GB (Gemma 4 E4B) |
| Inference time | <5 seconds on CPU |
| Languages supported | 35+ |
| Internet required | ❌ Never |

---

## Technical Architecture

```
[CHW Phone]
    │
    ├── PWA Frontend (HTML/CSS/JS)
    │       └── Offline-installable, mobile-first
    │
    └── Gemma 4 E4B (local)
            └── Structured JSON triage output
                    ├── Urgency level (EMERGENCY/URGENT/ROUTINE/MONITOR)
                    ├── Primary concern
                    ├── Recommended action
                    ├── Warning signs
                    ├── Questions to ask
                    └── Confidence level
```

---

## Built With
- [Gemma 4](https://ai.google.dev/gemma) — Google DeepMind open model
- Python + Flask — lightweight backend
- Vanilla HTML/CSS/JS — zero dependencies, works offline
- HuggingFace Transformers — model loading

---

## License
Apache 2.0 — fully open source as required by Gemma 4 Good Hackathon rules.

---

*Built for the Gemma 4 Good Hackathon — Kaggle × Google DeepMind, April 2026*
