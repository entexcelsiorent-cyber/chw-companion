# Safety and Compliance — Productization Guide

**Relation to shipped doc:** This expands and clarifies `../SAFETY.md` for SLM productization, portfolio claims, and any future pilot.  
**If they conflict on UX design intent, prefer `SAFETY.md` for the prototype’s rationale; prefer this file + `REVIEW.md` for accuracy of *current code behavior* and external claims.**

---

## 1. Regulatory posture (default)

CHW Companion is:

- A **clinical decision-support prototype** for trained Community Health Workers
- **Not** a medical device
- **Not** a diagnostic product
- **Not** cleared/approved/authorized by FDA, EMA, or other regulators
- **Not** WHO pre-qualified

No SLM distill, cache expansion, or pilot pilot-study result changes that posture until a deliberate regulatory strategy and submission exist.

### Intended use statement (portfolio-safe)

> Helps a trained CHW organize symptom information into a structured triage suggestion (urgency tier and next-step considerations). It does not diagnose, prescribe, or replace clinical judgment, local protocols (e.g. IMCI/IMNCI), or emergency referral pathways.

### Intended user

Trained CHWs (and reviewers/demo audiences). **Not** untrained laypersons seeking self-diagnosis.

---

## 2. Human-in-the-loop (non-negotiable)

| Rule | Implementation today | Productization note |
|------|----------------------|---------------------|
| CHW decides | UI presents suggestion; no auto-referral dispatch | Keep — never add autonomous ambulance dispatch without governance |
| Disclaimer always visible | Non-dismissible banner in `app/index.html` | Localize only with clinician translation review |
| Escalate when uncertain | Prompts + curation bias + mocks + override | Student models inherit same bias |
| Honest failure | Offline badge; mocks; parse→mock | Prefer explicit “unavailable” for OOD over confident fiction as library grows |

The app must **not** block a CHW from acting against a suggestion after clinical assessment (`SAFETY.md`).

---

## 3. Persistent disclaimer

Canonical English text (UI + `SAFETY_DISCLAIMER` in `backend/server.py`):

> Decision support tool only. Not a diagnosis. Always use your clinical judgment. When uncertain, escalate urgency.

### Design rules (from `SAFETY.md`, still in force)

- No close button / “don’t show again”
- Visible with the urgency verdict
- Short, plain language

### Productization additions

- Version the disclaimer string (`disclaimer_id`)
- Track translations in a reviewed table; unreviewed languages keep English
- Screenshots for portfolio must show the banner

---

## 4. Urgency system and conservative bias

Tiers (WHO IMCI-coloured):

| Tier | Colour | Meaning |
|------|--------|---------|
| EMERGENCY | red | Life-threatening — refer NOW |
| URGENT | orange | Serious — refer within hours |
| ROUTINE | yellow | Needs treatment — can be today |
| MONITOR | green | Home care with instructions |

**Bias:** when uncertain, escalate. Cost asymmetry: unnecessary referral ≪ missed emergency.

### Layered controls (all remain required)

1. Prompt text in `PRIMARY_PROMPT` / `DETAIL_PROMPT` (`backend/server.py`)
2. Manual cache curation (`app/scenarios.json`, `regen_scenarios_gemma4.py` report)
3. Frontend `mockPrimary` red-flag keywords
4. Backend `mock_primary` red-flag keywords (narrower set — see `REVIEW.md`)
5. Deterministic `applyEmergencyOverride` / `EMERGENCY_TRIGGERS` in `app/index.html`

---

## 5. What must never be claimed

### Absolute prohibitions in marketing, README badges, pitch decks, or model cards

- “Diagnoses …” / “detects disease with X% accuracy” (unless a specific cleared study — none today)
- “FDA/EMA/WHO approved/cleared/pre-qualified”
- “Replace your doctor / CHW training”
- “Safe autonomous care”
- “Clinically validated” without naming protocol, partner, and limitations
- “Runs full Gemma 4 offline on any Android / $50 phone” (disproven; `PROJECT.md` deprecated)
- Hackathon “winner / placed #N” when placement is unknown (`SUBMISSION.md`, `HANDOVER.md`)
- “140+ language clinical parity” based only on base-model marketing
- “We never store symptoms” — **false today** (`localStorage` queue stores symptom text)

### Claims that require evidence first

| Claim | Evidence needed |
|-------|-----------------|
| Nurse–model urgency agreement = X% | Prospective or retrospective labeled study |
| Multilingual parity | Per-language eval tables (`SLM_EVAL.md`) |
| On-device SLM latency &lt; N s | Named device measurement |
| Improves referral timeliness | Controlled pilot outcomes |

---

## 6. Data protection and logging

### Current prototype

- No analytics/telemetry pipeline in code
- Server does not implement durable symptom logging
- **Triage queue persists in `localStorage` (`chw_queue_v1`)** including free-text symptoms, age, sex — survives reload until cleared
- Shared-phone risk: next user may see prior queue entries

### Compliance-minded rules for pilots

1. Default **off** for any remote logging of free text  
2. Written retention limits; encryption at rest if synced  
3. No training on pilot transcripts without consent/ethics  
4. Prefer on-device or on-prem inference in sensitive catchments  
5. Document cross-border transfer if cloud GPU used  
6. Demo mode: synthetic patients only

Apache 2.0 code license ≠ permission to process real patient data without local law compliance (e.g. PDPA-like regimes, health privacy rules).

---

## 7. Model and content boundaries

### Allowed outputs

- Urgency suggestion + referral timing language
- General danger signs and assessment questions
- Protocol pointers (“per CHW protocol”, “RDT if available”)
- Explicit prohibitions (no aspirin in children, no tourniquet for snake bite, etc.)

### Disallowed outputs

- Specific drug doses / concentration calculations
- Definitive diagnosis statements
- Instructions that increase harm (unsafe delivery interventions beyond scope, violence, etc.)
- Ranking patients by protected attributes (queue ranks by urgency only — keep it that way)
- Sexual content involving minors; any CSAM — refuse and stop

### SLM training boundary

Do not fine-tune on data that teaches disallowed outputs. See exclusions in `SLM_DATA_PIPELINE.md`.

---

## 8. Change control (lightweight)

Before shipping a new `scenarios.json`, model id, or override list:

1. Diff review of urgency changes on EMERGENCY ids  
2. Re-run trigger self-match + inline sync (`inline_scenarios.py`, CI)  
3. Run override fixture suite  
4. Update `curation_note` / model card snippet  
5. Bump `version` field in scenarios JSON  

Emergency override trigger edits require dual review: false negatives are unacceptable; document new false-positive risk.

---

## 9. Incident categories (pilot)

| Severity | Example | Response |
|----------|---------|----------|
| S1 | Under-call contributing to delayed emergency referral | Disable live/student path; cache+protocols only; root-cause |
| S2 | Dosing advice emitted | Hotfix prompts/model; add lint gate |
| S3 | Disclaimer missing in a build | Block release |
| S4 | Cache wrong language tag | Curate and reship JSON |

---

## 10. Portfolio vs production checklist

### Before posting a public demo link

- [ ] Banner visible in first screenshot  
- [ ] README “not a medical device” near top  
- [ ] No fake accuracy / placement claims  
- [ ] Sample chips use fictional vignettes only  

### Before any real-CHW pilot

- [ ] Partner + ethics path  
- [ ] Localized disclaimer review  
- [ ] Logging DPA  
- [ ] Training curriculum emphasizing override of the tool  
- [ ] Kill switch for live inference  

---

## 11. Cross-references

| Topic | File |
|-------|------|
| Prototype safety design narrative | `../SAFETY.md` |
| Architecture & failure modes | `../ARCHITECTURE.md`, `SLM_ARCHITECTURE.md` |
| Eval safety metrics | `SLM_EVAL.md` |
| Accuracy fixes vs code | `REVIEW.md` |
| Impact / validation pathway | `../README.md` (Impact pathway) |
