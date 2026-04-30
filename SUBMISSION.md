# Submission Narrative — Gemma 4 Good Hackathon

**Project:** CHW Companion — clinical decision support for Community Health Workers
**Author:** Solo build (no team)
**License:** Apache 2.0
**Built in:** ~30 days, 1–2 hours per evening

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

- **Production model:** Gemma 3 1B Instruct, served from a Kaggle T4 GPU instance via a thin Flask wrapper. Two endpoints — `/triage/primary` (≈50 output tokens, ≈3.3 s warm) and `/triage/detail` (≈300 output tokens, ≈20 s warm). Both return validated JSON the frontend renders field-by-field.
- **Multilingual capability** comes from Gemma natively — the app does not run a translation step, swap languages, or route to a specialised model for non-English inputs. A CHW writing in Swahili gets a clinically appropriate Swahili response back from the same model that handles English.
- **Cached scenarios** are pre-generated Gemma 3 1B outputs (then clinician-style curated for tier and language correctness) bundled with the app. The same model handles online and offline; the cache is just a deterministic shortcut to its outputs for cases CHWs see most often.
- **Open weights and Apache 2.0** are not incidental — they are why this can be deployed by a regional NGO without a paid API contract, why the cached scenarios can ship as static JSON, and why the impact pathway below is realistic rather than aspirational.

This is Gemma doing what large API-only models cannot: running on infrastructure a community-health programme can actually afford, in languages they actually speak, with a build cost that fits a solopreneur's evening.

## What I built and what I learned

The build is honest about the architecture that works versus the marketing version:

- **The original concept** said "runs offline on a $50 Android phone." That was wrong. Gemma 3 1B fp16 is ≈2 GB; even quantised, it under-performs on low-end edge hardware. Hardware testing on Apr 22–27 ruled out single-shot full-schema inference under any latency budget that a CHW would tolerate (E4B fp16 on T4: 25.86 s; 3-1b-it fp16 on T4: 19.96 s).
- **The architecture that works**, and what shipped: a two-phase split (fast urgency verdict + slow detail) plus a 20-scenario cache layer for offline coverage. Hardware tests confirmed the primary phase clears 3.3 s on T4; the cache makes the most common cases work even when bandwidth doesn't.
- **The cached scenarios needed clinician-style curation.** First-pass Gemma 3 1B generation collapsed 14/20 scenarios to URGENT/red regardless of true severity, and tagged Hausa as "Filipino." A manual review pass corrected urgency tiers, urgency colours, language tags, recommended actions, and trigger keywords. Curation is now a permanent part of the cache build pipeline.
- **Frontend lives in one file** — `app/index.html`, no build, vanilla HTML/CSS/JS. The cached JSON is inlined as a `<script type="application/json">` block so the cache works on `file://` (browsers block `fetch()` on the file: origin — fixed by inlining).

## Honest scope

This is what the hackathon entry is and isn't:

- **It is** a working web app + Flask backend + cached-scenario layer that demonstrates the architecture end-to-end.
- **It is** open source under Apache 2.0, immediately forkable by any organisation.
- **It is** designed by someone who can read the whole stack in an afternoon — a CHW programme administrator, a clinical reviewer, or a regulator.
- **It is not** a medical device. No FDA, EMA, or WHO pre-qualification.
- **It is not** clinically validated. That requires a pilot study, not a hackathon.
- **It is not** running on edge phones. The phone is a thin client; inference lives on a shared GPU tier.

The submission video shows the architecture working honestly — three scenarios via the cache (instant, offline), the two-phase live inference path against Kaggle T4, the permanent safety banner, the triage queue ranking patients. No staged demos, no fake response times.

## Impact pathway

Hackathon win or place is step zero of a multi-year arc:

1. **Win or place** in the Gemma 4 Good Hackathon → visibility + small grant for next steps.
2. **Open-source the codebase** (already done, Apache 2.0).
3. **Pilot with a CHW organisation** — partner with a single regional NGO or ministry-of-health programme to deploy in a defined catchment area. Validate triage agreement against trained nurses on the same cases. Expand the cached-scenario library to that region's disease profile and dominant local languages.
4. **Clinical validation study** — measure CHW decision agreement, time-to-referral, and patient outcomes against a baseline-care arm. This is the bar required for WHO digital-health pre-qualification.
5. **Scale-up** — WHO Digital Health Atlas listing, ministry-of-health endorsement in pilot countries, regional cached-scenario libraries for additional disease profiles.

Each step is realistic at a budget a small NGO can fund. None of it requires Anthropic-or-OpenAI-tier API spend. That is the point of using an open Gemma model with a strong cache layer rather than a frontier API.

## Why this fits the "for good" framing

The Gemma 4 Good Hackathon is about open models meeting underserved problems. CHW Companion is built around exactly that intersection:

- The user is underserved (CHWs in low-resource settings have no decision-support tooling).
- The architecture only works because the model is open (cache pre-generation, on-prem deployment, regional fine-tuning all require open weights).
- The licensing matches the cause (Apache 2.0 fork-friendly).
- The constraints match the field (intermittent connectivity, multilingual, low-end client devices, audit-ready stack).

This is not "an LLM wrapped in a UI" — it is a careful split of cache + small-model live inference + safety layer + auditable code, designed for a user who actually needs the tradeoffs we made.

## Submission contents

- Code: this repository (`chw-companion/` directory in the parent OMEGA ML platform repo, Apache 2.0)
- Demo video: 90 s, no narration overlay, three scenarios (English malaria pediatric, Swahili snake bite, offline-cache demonstration). Recorded against the cached-scenario layer so all responses arrive in under 2 s and the full demo fits one take.
- Documentation: `README.md`, `ARCHITECTURE.md`, `SAFETY.md`, this file
- Hardware-validation notebooks: `test_gemma4_hardware_v2.py`, `test_gemma4_hardware_1b.py` (Kaggle T4 reference paths)

## Acknowledgements

Built with [Gemma](https://ai.google.dev/gemma) (Google DeepMind), [Hugging Face Transformers](https://huggingface.co/docs/transformers), Flask, and vanilla HTML/CSS/JS. Inference tier provided by Kaggle's free T4 GPU during development. Solo build, no team — see `README.md` for the constraints that shaped the design and `SAFETY.md` for the safety design rationale.
