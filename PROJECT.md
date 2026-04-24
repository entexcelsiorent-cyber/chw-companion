# 🏥 Community Health Worker Companion
## Gemma 4 Good Hackathon — Kaggle 2026

---

## Elevator Pitch
An offline-first AI triage assistant for frontline Community Health Workers (CHWs)
in low-resource settings. No internet required. Runs entirely on-device using Gemma 4.

---

## Problem Statement
- 2 billion people live without reliable access to healthcare
- 1.5 million CHWs operate in remote areas with zero clinical decision support
- A CHW sees a feverish child with a rash — no doctor, no internet, no guidance
- Wrong decisions cost lives. Right decisions save them.

---

## Solution
CHW Companion runs Gemma 4 (4B edge model) locally on a $50 Android phone.
A CHW describes symptoms in plain language (or their local language).
The app returns: a structured triage decision, urgency level, and next action.

---

## Stack

### Frontend
- Mobile-first HTML/CSS/JS Progressive Web App (PWA)
- Installable on Android — no app store needed
- Works fully offline after first install

### AI Engine
- Gemma 4 E4B (edge 4B model) via:
  - Kaggle submission: runs in notebook via transformers library
  - Production: Ollama on-device or llama.cpp
- Structured prompting for clinical triage output
- Multilingual — Gemma 4 handles 35+ languages natively

### Backend (optional for demo)
- Python Flask API wrapping Gemma 4
- Deployable locally — no cloud dependency

---

## Project Structure
```
chw-companion/
├── app/
│   ├── index.html          # PWA entry point
│   ├── app.js              # Main application logic
│   ├── styles.css          # Mobile-first styles
│   └── manifest.json       # PWA manifest
├── backend/
│   ├── server.py           # Flask API
│   ├── gemma_client.py     # Gemma 4 integration
│   ├── triage_prompt.py    # Structured triage prompts
│   └── requirements.txt
├── kaggle/
│   └── notebook.ipynb      # Kaggle submission notebook
├── docs/
│   ├── writeup.md          # Technical write-up
│   └── demo-script.md      # Video demo script
└── README.md
```

---

## Triage Logic (Gemma 4 Prompt Strategy)

### System Prompt
```
You are a clinical decision support assistant for Community Health Workers
in low-resource settings. You have no internet access. Your role is to help
CHWs make triage decisions based on symptom descriptions.

Always respond in this exact JSON structure:
{
  "urgency": "EMERGENCY | URGENT | ROUTINE | MONITOR",
  "urgency_color": "red | orange | yellow | green",
  "primary_concern": "string",
  "recommended_action": "string",
  "warning_signs": ["string"],
  "questions_to_ask": ["string"],
  "confidence": "high | medium | low"
}

Be conservative. When in doubt, escalate urgency.
Never diagnose definitively. Support, don't replace, clinical judgment.
```

---

## Judging Criteria Alignment

| Criterion | Our Score | How |
|---|---|---|
| Impact | ⭐⭐⭐⭐⭐ | 1.5M CHWs, 2B underserved people |
| Technical execution | ⭐⭐⭐⭐ | Gemma 4 edge model, offline PWA, structured output |
| Use case clarity | ⭐⭐⭐⭐⭐ | Specific user, specific problem, specific outcome |
| Demo quality | ⭐⭐⭐⭐⭐ | Child + fever scenario is emotionally clear |
| Gemma 4 utilisation | ⭐⭐⭐⭐⭐ | On-device, multilingual, edge model |

---

## 26-Day Timeline (1-2hrs/evening)

| Days | Task |
|---|---|
| 1-3 | UI built, project repo live, Gemma 4 local install |
| 4-8 | Flask backend + Gemma 4 triage prompt working |
| 9-14 | Full end-to-end flow, symptom → JSON → UI response |
| 15-18 | Multilingual input, voice input (optional) |
| 19-22 | Polish, edge cases, offline PWA |
| 23-24 | Technical write-up |
| 25 | Record video demo |
| 26 | Submit to Kaggle |
