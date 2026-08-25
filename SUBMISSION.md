# Project narrative — CHW Companion

**What this is:** an offline-capable clinical triage PWA for Community Health Workers, with a Flask wrapper around Gemma 4.
**Author:** Solo build (no team)
**License:** Apache 2.0
**Origin:** Built for the Gemma 4 Good Hackathon (Kaggle × Google DeepMind), which closed 2026-05-18. The hackathon placement is unknown and is not claimed here.

This file used to be the hackathon submission write-up. It is kept as the project narrative so a portfolio reader can see what shipped, what was learned, and what the honest scope is.

---

## The problem

There are an estimated **1.5 million Community Health Workers worldwide**, serving roughly **2 billion people without reliable access to clinical care**. Most are the only clinical contact in their catchment. Most have intermittent connectivity. None of them have a clinical decision-support tool designed for their specific context — local language, low literacy in clinical English, no specialist backup, a queue of patients who need triaging right now.

Fatima, a CHW in rural Tanzania, looks at a four-year-old boy: high fever, refusing to drink, day two. The nearest doctor is four hours away. She has to make a triage call right now. Get it wrong and that child does not make it to care in time.

CHW Companion exists for that moment.

## The solution

CHW Companion is a Gemma-powered clinical triage assistant. The CHW types a symptom description in plain language — in any language Gemma supports — and the app returns a structured triage decision in two phases:

1. **Primary verdict in ≈3 seconds**: urgency tier (EMERGENCY/URGENT/ROUTINE/MONITOR), urgency colour, recommended action, confidence. The CHW has a decision in hand immediately.
2. **Clinical detail streaming behind it (≈20 s)**: primary concern, warning signs to watch, questions to ask the caregiver, things not to do. The CHW reads while it fills in — no waiting on a spinner.

A **triage queue** ranks all assessed patients by urgency so a worker juggling several cases sees who needs attention first. A **permanent safety disclaimer** sits on every screen — this is decision support, not diagnosis.

A **cached-scenario layer** pre-generates responses for 20 canonical CHW presentations across 8 conditions (malaria, pneumonia, diarrhoea, malnutrition, obstetric emergencies, snake bite, meningitis, trauma) and 5 languages (English, Swahili, French, Hausa, plus an English fallback). Cache hits return instantly and work without a network. Common presentations always work; novel cases fall back to live inference when connectivity allows.

## How Gemma is used

Gemma is the entire clinical-reasoning layer.

- **Production model:** Gemma 4 (E4B, or the text-only E2B variant where latency permits), served from a Kaggle T4 GPU instance via a thin Flask wrapper. Two endpoints — `/triage/primary` (≈50 output tokens, ≈7 s warm on E4B) and `/triage/detail` (≈300 output tokens, ≈25 s warm, streams behind the primary result). Both return validated JSON the frontend renders field-by-field.
- **Multilingual capability** comes from Gemma 4 natively — 140+ languages, no translation step, no language routing. A CHW writing in Swahili, Hausa, or French gets a clinically appropriate response in that language from the same model that handles English.
- **Cached scenarios** are bundled with the app as static JSON. The same architecture handles online and offline; the cache is a deterministic shortcut for the cases CHWs see most often. The checked-in file was generated 2026-04-28 with `google/gemma-3-1b-it` and then curated. `regen_scenarios_gemma4.py` rebuilds it on Gemma 4; that regeneration is not in the tree yet.
- **Open weights and Apache 2.0** are not incidental — they are why this can be deployed by a regional NGO without a paid API contract, why the cached scenarios can ship as static JSON, and why the impact pathway below is realistic rather than aspirational.

This is Gemma 4 doing what large API-only models cannot: running on infrastructure a community-health programme can actually afford, in languages they actually speak, with a build cost that fits a solopreneur's evening.

## What was built and what was learned

The build is honest about the architecture that works versus the marketing version:

- **The original concept** said "runs offline on a $50 Android phone." That was wrong. Gemma 4 E4B fp16 weights are ~16 GB; on-device inference at acceptable latency is not feasible on low-end hardware. Hardware testing on Apr 22–27 measured E4B at 25.86 s for full-schema inference on a T4 — unusable as a single call.
- **The architecture that works**, and what shipped: a two-phase split (fast urgency verdict + slow detail) plus a 20-scenario cache layer for offline coverage. The two-phase split puts the critical urgency decision in front of the CHW in ≈7 s on E4B; the text-only E2B variant is expected to cut that to ≈3–4 s. The cache makes the 20 most common presentations work instantly with zero network.
- **The cached scenarios needed clinician-style curation.** First-pass generation collapsed 14/20 scenarios to URGENT/red regardless of true severity, and tagged Hausa as "Filipino." A manual review pass corrected urgency tiers, urgency colours, language tags, recommended actions, and trigger keywords. Curation is a permanent part of the cache build pipeline — `regen_scenarios_gemma4.py` includes a validation report that flags mismatches automatically.
- **Frontend lives in one file** — `app/index.html`, no build, vanilla HTML/CSS/JS. The cached JSON is inlined as a `<script type="application/json">` block so the cache works on `file://` (browsers block `fetch()` on the file: origin — fixed by inlining).

## Honest scope

This is what the project is and isn't:

- **It is** a working web app + Flask backend + cached-scenario layer that demonstrates the architecture end-to-end.
- **It is** open source under Apache 2.0, immediately forkable by any organisation.
- **It is** designed so someone can read the whole stack in an afternoon — a CHW programme administrator, a clinical reviewer, or a regulator.
- **It is not** a medical device. No FDA, EMA, or WHO pre-qualification.
- **It is not** clinically validated. That requires a pilot study, not a prototype.
- **It is not** running on edge phones. The phone is a thin client; inference lives on a shared GPU tier.

A demo of the architecture: three scenarios via the cache (instant, offline), the two-phase live inference path against Kaggle T4, the permanent safety banner, the triage queue ranking patients. No staged demos, no fake response times.

## Impact pathway

A working public prototype is step zero of a multi-year arc:

1. **Open-source the codebase** (already done, Apache 2.0).
2. **Pilot with a CHW organisation** — partner with a single regional NGO or ministry-of-health programme to deploy in a defined catchment area. Validate triage agreement against trained nurses on the same cases. Expand the cached-scenario library to that region's disease profile and dominant local languages.
3. **Clinical validation study** — measure CHW decision agreement, time-to-referral, and patient outcomes against a baseline-care arm. This is the bar required for WHO digital-health pre-qualification.
4. **Scale-up** — WHO Digital Health Atlas listing, ministry-of-health endorsement in pilot countries, regional cached-scenario libraries for additional disease profiles.

Each step is realistic at a budget a small NGO can fund. None of it requires Anthropic-or-OpenAI-tier API spend. That is the point of using an open Gemma model with a strong cache layer rather than a frontier API.

## Why this architecture

The project sits at the intersection of an open model and an underserved problem:

- The user is underserved (CHWs in low-resource settings have no decision-support tooling).
- The architecture only works because the model is open (cache pre-generation, on-prem deployment, regional fine-tuning all require open weights).
- The licensing matches the cause (Apache 2.0 fork-friendly).
- The constraints match the field (intermittent connectivity, multilingual, low-end client devices, audit-ready stack).

This is not "an LLM wrapped in a UI" — it is a careful split of cache + small-model live inference + safety layer + auditable code, designed for a user who actually needs the tradeoffs we made.

## What's in the repo

- Code: this repository, Apache 2.0
- Documentation: `README.md`, `ARCHITECTURE.md`, `SAFETY.md`, this file
- Hardware-validation notebooks: `test_gemma4_hardware_v2.py`, `test_gemma4_hardware_1b.py` (Kaggle T4 reference paths)
- Cache pipeline: `regen_scenarios_gemma4.py`, `inline_scenarios.py`
- Optional live-inference tunnel: `kaggle_inference_server.py`

## Acknowledgements

Built with [Gemma](https://ai.google.dev/gemma) (Google DeepMind), [Hugging Face Transformers](https://huggingface.co/docs/transformers), Flask, and vanilla HTML/CSS/JS. Inference tier provided by Kaggle's free T4 GPU during development. Solo build, no team — see `README.md` for the constraints that shaped the design and `SAFETY.md` for the safety design rationale.
