# SLM Strategy — CHW Companion Productization

**Status:** Strategy for portfolio / social-impact SLM productization of the existing CHW Companion **PWA**.  
**Codebase:** `c:\Repos\MLOmega\MLOmega\chw-companion\`  
**Audience:** Portfolio readers, potential NGO/pilot partners, future implementers.  
**Not:** A claim of regulatory clearance, clinical validation, or production health deployment readiness.

---

## 0. PWA + SLM stance (non-negotiable product shape)

CHW Companion **is a Progressive Web App**. Any SLM work must respect that shape — not replace it with a native-only or weight-first story.

| Layer | Role in the product | Phase |
|-------|---------------------|-------|
| **(1) Curated scenario cache in the PWA** | Primary offline “SLM-like” CDS: keyword-matched structured triage cards, no on-device weights | **Phase 0–2 / portfolio** |
| **(2) Optional live Gemma / server** | Novel cases when online (`window.CHW_BACKEND` / Flask) | Optional demo path |
| **(3) Future on-device WebGPU SLM** | Optional long-tail offline generative assist | **Later phase only** — not required for Phase 1–2 |

**Say this:** cache-first offline PWA triage UX + honest optional GPU teacher.  
**Do not say:** on-device Gemma, offline full generative triage, or “the SLM runs in the browser” unless a measured WebGPU path actually ships.

---

## 1. Product vision

**CHW Companion** helps Community Health Workers (CHWs) turn a plain-language symptom description into a structured **triage decision-support** card: urgency tier, recommended action, warning signs, questions to ask, and explicit “do not do” items.

The productized SLM path keeps that same clinical *surface* while making the reasoning layer:

- **Smaller and cheaper** than full Gemma 4 E4B live inference
- **More available** under intermittent connectivity
- **More auditable** for common presentations (deterministic cache + curated labels)
- **Explicitly bounded** as decision support — never diagnosis, never autonomous care

### What “productizing the SLM” means here

| Layer | Today (prototype) | SLM productization target |
|-------|-------------------|---------------------------|
| Offline common cases | 20 keyword-matched scenarios in `app/scenarios.json` (generated with `google/gemma-3-1b-it`, curated), served by the PWA | Expanded, clinician-reviewed scenario library (still PWA-first); optional tiny ranking/classifier later |
| Novel cases (online) | Gemma 4 via Flask (`backend/server.py`) on GPU (Kaggle T4 / equivalent) | Same teacher for distillation; optionally a distilled SLM for lower latency/cost **behind the same PWA API contract** |
| On-device generative | Explicitly **not** claimed (see `ARCHITECTURE.md`, `PROJECT.md` deprecation) | Optional later: WebGPU / quantized distill — never required for portfolio demo |
| Safety floor | Prompt conservatism + curated cache + `applyEmergencyOverride()` in `app/index.html` | Same floors retained; eval gates before any model swap |

The portfolio story is: *installable offline-capable triage **PWA** + curated cache as the specialized knowledge layer + honest GPU inference when online + a roadmap to a smaller model*, not “Gemma runs on a $50 phone.”


---

## 2. Why an SLM (not a frontier API)

### Offline / intermittent connectivity

CHWs often have intermittent or no signal. The prototype already separates:

1. **Cache hit** — instant, works on `file://` / offline (`app/scenarios.json` inlined into `app/index.html`)
2. **Cache miss + backend** — live Gemma 4 when `window.CHW_BACKEND` (or local Flask) is reachable
3. **Cache miss + no backend** — frontend `mockPrimary()` / `mockDetail()` with conservative keywords, or a clear “unavailable” path for honest failure

An SLM productization **amplifies** the offline path: larger curated libraries, optional on-device distill for long-tail cases, without depending on paid per-token APIs.

### Low cost

Live Gemma 4 E4B fp16 (~16 GB class weights) needs datacenter-class GPU for usable latency (`ARCHITECTURE.md`: ~7 s primary / ~25 s detail warm on T4). Frontier APIs are worse for NGO unit economics.

An SLM (or a **cached-response product** that *behaves* like a specialized model for the top-N presentations) keeps:

- Inference cost near zero for cache hits
- Distill/hosting cost in the $50–200/month GPU tier range already described in `README.md` / `SAFETY.md` for live novel cases

### Privacy

Symptom text is clinically sensitive. The prototype intentionally avoids a cloud analytics pipeline (`SAFETY.md`). Productization should prefer:

- On-device or on-prem inference for novel cases where possible
- No outbound logging of free-text symptoms by default
- Clear data-flow diagrams for any pilot partner (see `SLM_ARCHITECTURE.md`)

**Caveat (current code):** the triage queue persists age/sex/**full symptom strings** in `localStorage` (`chw_queue_v1` in `app/index.html`). That is on-device persistence, not a server log — but it is still PHI-like content on a shared phone. Portfolio and pilot docs must not claim “no symptom storage.”

---

## 3. Regulated-domain constraints (not a medical device)

CHW Companion is framed as **clinical decision support for trained CHWs**, not as:

- A medical device
- A diagnostic system
- A prescribing / dosing engine
- A replacement for IMCI/IMNCI training or clinician judgment

### Hard claims that must never appear in product marketing

- FDA / EMA / CE / WHO pre-qualification clearance
- “Diagnoses malaria / pneumonia / …”
- “Safe to use without a trained CHW”
- “Clinically validated” (unless a named study with ethics approval exists)
- “Runs full Gemma 4 offline on low-end Android” (explicitly disproven; `PROJECT.md` is historical only)

### Soft claims that *are* allowed (with caveats)

- “Decision-support prototype / portfolio demo”
- “Structured urgency suggestion aligned to EMERGENCY / URGENT / ROUTINE / MONITOR”
- “Offline coverage for curated canonical presentations”
- “Built on open Gemma weights; forkable under Apache 2.0”

See `SAFETY_AND_COMPLIANCE.md` and existing `SAFETY.md` for disclaimer UX and human-in-the-loop rules.

---

## 4. Positioning: portfolio vs production health use

Aligned with parent context (`PORTFOLIO_ONEPAGER.md`, `HANDOVER.md`, `CLAUDE.md`):

| Track | Goal | Success looks like |
|-------|------|--------------------|
| **Portfolio / social-impact SLM** (priority for this doc set) | Public proof you can ship responsible health-adjacent ML: safety floors, evals, honest architecture | Standalone repo, live Pages demo, clear SLM roadmap docs, eval harness stubs, no overclaim |
| **Optional validated pilot** | Partner NGO / MoH catchment; nurse agreement study | Ethics review, clinician-labeled eval set, expanded scenarios, logging policy, training materials |
| **Regulated scale** | WHO Digital Health Atlas / ministry endorsement | Multi-year; not this phase |

**Hackathon status:** Gemma 4 Good Hackathon closed 2026-05-18; placement unknown and must not be claimed (`SUBMISSION.md`, `HANDOVER.md`).

---

## 5. User and job-to-be-done

**Primary user:** CHW in a low-resource setting, often working in a local language, with a phone browser, intermittent connectivity, and a queue of patients.

**Job:** In under a minute of attention, get a **structured second opinion** that:

1. Surfaces urgency in WHO IMCI-familiar colours (red / orange / yellow / green)
2. Suggests next action (refer now / refer today / treat per protocol / monitor)
3. Lists warning signs and caregiver questions
4. Reminds what **not** to do (no aspirational drug dosing)

**Secondary users:** NGO programme leads, clinical reviewers, portfolio recruiters evaluating engineering judgment under safety constraints.

---

## 6. Why this problem fits an SLM specifically

1. **Output schema is narrow** — JSON fields already fixed in `backend/server.py` (`PRIMARY_PROMPT` / `DETAIL_PROMPT`). Distillation targets are well-defined.
2. **Distribution is peaked** — malaria, pneumonia, diarrhoea, malnutrition, obstetric emergencies, snake bite, meningitis, trauma dominate the cache design in `README.md`. A small specialized model + large cache beats a general LLM for the common path.
3. **Conservative escalation is rule-compatible** — `applyEmergencyOverride()` in `app/index.html` shows that hard safety floors can sit *outside* the model. An SLM should inherit those floors, not replace them.
4. **Open weights enable the offline cache** — `regen_scenarios_gemma4.py` exists specifically to regenerate the cache from Gemma-family teachers.

---

## 7. Strategic bets (ordered)

1. **Expand + clinician-curate the scenario library** before training anything. Highest ROI for offline reliability and portfolio demos.
2. **Treat Gemma 4 as the teacher** for synthetic labels and live novel-case fallback (`backend/server.py`, `kaggle_inference_server.py`).
3. **Distill a triage SLM** only after eval sets and safety exclusions exist (`SLM_DATA_PIPELINE.md`, `SLM_EVAL.md`).
4. **On-device deployment** only after latency/quality gates on real mid-tier Android — never as a marketing precondition.
5. **Pilot** only with a partner, ethics path, and explicit “not a device” packaging.

---

## 8. Non-goals (this productization phase)

- Full product rewrite of the PWA
- Downloading or training large weights in-repo
- Claiming multilingual clinical parity beyond what the cache + Gemma actually demonstrate
- Auto-localizing the English safety disclaimer without clinician translation review (`SAFETY.md`)
- Weaponization, patient-harm “optimization,” or adversarial attack recipes against care pathways

---

## 9. Source-of-truth map

| Topic | Authoritative file(s) |
|-------|------------------------|
| How the app works today | `README.md`, `ARCHITECTURE.md`, `app/index.html`, `backend/server.py` |
| Safety posture (shipped) | `SAFETY.md` |
| Portfolio framing | `HANDOVER.md`, `../PORTFOLIO_ONEPAGER.md` |
| Historical wrong claims | `PROJECT.md` (deprecated) |
| SLM productization (this set) | `docs/SLM_*.md`, `docs/SAFETY_AND_COMPLIANCE.md`, `docs/REVIEW.md` |

---

## 10. One-sentence strategy

**Productize CHW Companion as a safety-bounded, offline-first triage assistant whose “intelligence” is mostly curated specialized knowledge (cache + optional distilled SLM), with Gemma 4 as teacher and live long-tail fallback — positioned first as a portfolio / social-impact artifact, and only later as a clinically validated pilot under partner governance.**
