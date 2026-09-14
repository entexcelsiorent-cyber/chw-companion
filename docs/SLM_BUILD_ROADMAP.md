# SLM Build Roadmap — Hackathon → Portfolio → Optional Pilot

**Scope:** Phased plan to productize an SLM around CHW Companion without overclaiming clinical readiness.  
**Constraint:** Docs/strategy phase first; no weight downloads or training required to complete a phase gate unless explicitly staffed.

---

## Phase 0 — Hackathon prototype (DONE)

**Timeframe:** Built for Gemma 4 Good Hackathon (closed 2026-05-18).

### Delivered

- Single-file PWA: `app/index.html`
- 20 curated scenarios: `app/scenarios.json` (+ inline)
- Flask Gemma 4 path: `backend/server.py`
- Safety banner + emergency override + mocks
- Architecture / safety / submission narratives
- Hardware validation scripts (`test_gemma4_hardware*.py`); warm ~4.74s cited in `HANDOVER.md` for an earlier gate
- CI smoke: `.github/workflows/test.yml`

### Explicit non-deliverables

- Clinical validation study
- Regulatory clearance
- On-device Gemma 4
- Public GitHub Pages URL (still blocked on publish — `HANDOVER.md`)
- Gemma 4–generated cache checked in (regen script exists only)

### Acceptance criteria (retrospective)

| Criterion | Status |
|-----------|--------|
| End-to-end triage UX with two-phase results | Met |
| Offline cache path works on `file://` | Met (inline JSON) |
| Persistent disclaimer | Met |
| Honest docs about GPU requirement | Met in README/ARCHITECTURE; contradicted only by deprecated `PROJECT.md` |
| Same-family cache as live model | **Not met** |

---

## Phase 1 — Demo portfolio asset (IN PROGRESS → engineering-ready)

**Goal:** Public, forkable, demable **PWA** — cache-first offline CDS, not on-device Gemma. Aligned with `HANDOVER.md`, `docs/PUBLISH.md`, and `PORTFOLIO_ONEPAGER.md`.

### Workstreams

| ID | Work | Owner type | Status |
|----|------|------------|--------|
| P1.1 | Commit + subtree-split + GitHub repo + Pages (`pages.yml`) | Human publish | **Blocked on human** — `docs/PUBLISH.md` |
| P1.2 | Keep docs accurate; SAFETY ↔ localStorage agree | Docs | Done |
| P1.3 | Optional: regenerate `scenarios.json` on Gemma 4 + curation | Kaggle GPU | Deferred (no weights this phase) |
| P1.4 | Record / refresh demo using `VIDEO_SCRIPT.md` against Pages URL | Human | After Pages URL |
| P1.5 | Eval JSON + scorer (`eval/`, `SLM_EVAL.md`) | Engineering | Done (Phase 2 foundation) |
| P1.6 | Portfolio one-pager link to live demo + safety posture | Human | After Pages |
| P1.7 | PWA shell: manifest + service worker + honest footer/disclaimer | Engineering | Done |

### Acceptance criteria — Phase 1

- [ ] Public repo with Apache 2.0 license visible *(human)*
- [ ] GitHub Pages serves `app/`; sample chips work offline/cache *(human; workflow ready)*
- [x] README does not claim hackathon placement or fake demo URL
- [x] `SAFETY.md` / `docs/SAFETY_AND_COMPLIANCE.md` agree with localStorage queue behavior
- [x] SLM strategy docs present under `docs/` with **PWA + SLM stance**
- [ ] CI smoke green on standalone repo *(workflow ready; needs extracted repo)*
- [x] Portfolio path says “decision support prototype,” not “medical device”
- [x] No claim of on-device Gemma / offline full generative triage

### Exit

Recruiters / partners can click a live demo, read safety boundaries, and understand the PWA-first SLM roadmap in &lt;15 minutes.

---

## Phase 2 — SLM-ready data & eval harness (FOUNDATION LANDED)

**Goal:** Make distillation *possible* with honest measurement — still **no** student training. Eval stays **outside** the PWA bundle.

### Workstreams

| ID | Work | Status |
|----|------|--------|
| P2.1 | Expand curated scenarios toward 50–100 | Open (demo remains **20**) |
| P2.2 | Author held-out `eval_core` (+ multilingual / adversarial later) | **`eval/eval_core.json` landed** |
| P2.3 | Automate lint: urgency↔colour, trigger self-match, `do_not_do`, no mg doses | Partial (CI + scorer dosing check) |
| P2.4 | Teacher batch generation script | Exists; not run this phase |
| P2.5 | Baseline metrics on override floor + FE mock | **`eval/score_urgency.py`** |
| P2.6 | Queue PII minimization | Open (UI warns on shared-phone storage) |

### Acceptance criteria — Phase 2

- [ ] ≥50 shipped curated scenarios OR clearly labeled “demo 20 + draft N” — **demo 20 labeled; expand open**
- [x] Held-out eval set with contamination policy documented (`eval_core.json`)
- [x] Reproducible eval script reports urgency accuracy, override recall, critical under-call
- [x] Multilingual metrics reported **separately** (thin SW/FR/HA — **no parity claim**)
- [ ] Full safety exclusion pack (`eval_adversarial`) — dosing probe only for now
- [x] Still **no** “clinically validated” language
- [x] `applyEmergencyOverride` remains hard floor (scorer mirrors client)

### Exit

You can train a student later without inventing labels under deadline pressure — while keeping the **PWA cache-first** product path.

---

## Phase 3 — Distill & compare (optional engineering)

**Goal:** Produce a smaller model that approaches teacher quality on triage schema for in-distribution cases.

### Workstreams

| ID | Work |
|----|------|
| P3.1 | Choose student class (urgency-only vs full JSON) |
| P3.2 | Train off-repo / private workspace; **do not** commit giant weights to this tree |
| P3.3 | Wrap student behind same Flask contract as `server.py` |
| P3.4 | A/B: cache vs student vs teacher on `eval_core` |
| P3.5 | Latency gate on target hardware (define device explicitly) |
| P3.6 | Keep emergency override mandatory in client |

### Acceptance criteria — Phase 3

| Gate | Bar (initial proposal) |
|------|-------------------------|
| Urgency exact-match vs clinician gold on `eval_core` | ≥ teacher − 5 pp, and ≥ 85% if gold exists |
| Dangerous under-call (gold EMERGENCY → pred ROUTINE/MONITOR) | **0** on `eval_override` + gold EMERGENCY slice |
| JSON schema validity | ≥ 99% parseable |
| Override recall | 100% on `EMERGENCY_TRIGGERS` fixtures |
| Latency | Documented p50/p95 on named hardware; no phone claim without measurement |
| Refusal set | No assistance on dosing/harm exclusions |

If gates fail: ship cache+teacher only; keep student experimental.

### Exit

Optional `CHW_MODEL_ID` pointing at student with documented scorecard.

---

## Phase 4 — Optional validated pilot (partner-gated)

**Goal:** Measure agreement with trained nurses / clinicians in a defined catchment — **not** automatic scale-up.

### Preconditions (all required)

- Written partner agreement (NGO / MoH programme)
- Ethics / IRB or local equivalent determination
- Clinician-reviewed language pack for disclaimer + UI strings
- Data processing agreement; logging policy from `SLM_ARCHITECTURE.md`
- Training for CHWs: tool is support, escalation rules unchanged
- Incident response: how to disable model path and fall back to protocols

### Workstreams

| ID | Work |
|----|------|
| P4.1 | Regional scenario pack + disease prior without suppressing red flags |
| P4.2 | Prospective shadow mode (model suggests; CHW decides; outcomes logged de-identified) |
| P4.3 | Agreement study design (primary endpoint: urgency tier agreement / safe referral) |
| P4.4 | Human factors: literacy, connectivity, queue workflow |
| P4.5 | Go/no-go for any wider deployment |

### Acceptance criteria — Phase 4

- [ ] Protocol registered or partner-approved study plan
- [ ] Pre-specified safety stopping rules (e.g., under-escalation events)
- [ ] Results reported with confidence intervals and subgroup (language) analysis
- [ ] Regulatory pathway explicitly still “not cleared” unless a submission exists
- [ ] Public claims updated only to what the study supports

### Exit

Evidence pack for WHO Digital Health Atlas–style listing **discussion** — not a promise of listing.

---

## Phase 5 — Scale-up (aspirational; out of near-term scope)

Per `README.md` impact pathway:

- Ministry endorsement
- Multi-region scenario libraries
- Formal quality management / change control for model updates
- Possible medical-device pathway **only if** intentionally pursued with counsel — default remains non-device CDS

No acceptance criteria here until Phase 4 succeeds.

---

## Cross-phase invariants

1. **PWA-first** — cache-first offline CDS; SLM work must not abandon the PWA surface.
2. **Human in the loop** — CHW final decision.
3. **Escalate when uncertain** — product bias.
4. **No dosing / no definitive diagnosis.**
5. **Disclaimer always visible.**
6. **Emergency override remains client-side and deterministic.**
7. **Open-weight preference** for offline cache regeneration.
8. **Do not commit secrets** (`HF_TOKEN`, ngrok tokens).
9. **Do not claim placement, clearance, on-device Gemma, or offline full generative triage you do not have.**

---

## Suggested timeline (solopreneur-realistic)

| Phase | Calendar (indicative) | Dependency |
|-------|----------------------|------------|
| 1 Portfolio publish | Days–2 weeks | Human GitHub |
| 2 Data/eval harness | 2–6 weeks part-time | After or parallel to P1 |
| 3 Distill experiment | 2–8 weeks | GPU hours + P2 |
| 4 Pilot | Months–years | Partner |
| 5 Scale | Multi-year | P4 evidence |

---

## Decision gates (walk-away)

| Gate | Walk away if |
|------|----------------|
| Portfolio | Cannot keep safety claims honest |
| Distill | Student increases under-escalation vs teacher |
| Pilot | Partner requires “diagnosis app” marketing |
| On-device | Latency/quality fail on real CHW hardware class |
