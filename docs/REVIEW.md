# Review — SLM Productization Docs vs Code

**Reviewed:** 2026-09-13 (Phase 1–2 engineering pass)  
**Code root:** `c:\Repos\MLOmega\MLOmega\chw-companion\`  
**Docs set:** `docs/SLM_STRATEGY.md`, `SLM_DATA_PIPELINE.md`, `SLM_ARCHITECTURE.md`, `SLM_BUILD_ROADMAP.md`, `SLM_EVAL.md`, `SAFETY_AND_COMPLIANCE.md`, `PUBLISH.md`, this file  

---

## 1. Accuracy check (docs ↔ code)

| Claim area | Verdict | Evidence |
|------------|---------|----------|
| Two-phase `/triage/primary` + `/triage/detail` | Accurate | `backend/server.py` |
| Default live model `google/gemma-4-e4b-it` | Accurate | `MODEL_ID` env default |
| Cache is `google/gemma-3-1b-it`, curated | Accurate | `app/scenarios.json` |
| 20 scenarios; urgency 10/6/2/2 | Accurate | Counted from JSON |
| Languages in cache EN15 / SW2 / FR2 / HA1 | Accurate | `language_detected` tallies |
| Keyword AND-match, first wins | Accurate | `matchCachedScenario` |
| Inline JSON for `file://` | Accurate | `#cached-scenarios-data` |
| Emergency override client-side | Accurate | `EMERGENCY_TRIGGERS`, `applyEmergencyOverride` |
| Queue in `localStorage` with symptoms | Accurate | `chw_queue_v1` |
| PWA shell (manifest + SW) | Accurate after this pass | `manifest.webmanifest`, `sw.js` |
| Footer / comments claim Gemma 4 cache or 35+ parity | **Fixed** | Honest footer + cache comments |
| Held-out eval + scorer | Accurate after this pass | `eval/eval_core.json`, `eval/score_urgency.py` |

---

## 2. PWA + SLM stance (this pass)

1. **Primary product** = installable PWA with curated offline scenario cache (SLM-*like* CDS, no on-device weights).  
2. **Optional** = live Gemma/server when online.  
3. **Later optional** = on-device WebGPU SLM — **not** required for Phase 1–2.  
4. Never claim on-device Gemma or offline full generative triage unless measured and shipped.

---

## 3. Gaps remaining

1. Public GitHub Pages URL — human publish (`docs/PUBLISH.md`).  
2. Cache still `gemma-3-1b-it` vs live Gemma 4 — regen deferred (no weight download this phase).  
3. Scenario library still demo **20** (not 50–100).  
4. Multilingual eval thin (1 SW / 1 FR / 1 HA) — report separately; no parity claim.  
5. Full `eval_adversarial` / teacher GPU baselines not yet run.  
6. Queue PII still plaintext in `localStorage` (warning UI added).

---

## 4. Fixes applied this pass

1. PWA: `manifest.webmanifest`, `icon.svg`, `sw.js`, register SW; Pages workflow paths updated.  
2. Disclaimer text aligned to canonical SAFETY wording; queue shared-phone note.  
3. Removed misleading “Gemma 4 cache” / “35+ languages” marketing from footer/comments.  
4. `eval/eval_core.json` + `eval/score_urgency.py` (override floor gates).  
5. `docs/PUBLISH.md`; roadmap / strategy / eval docs updated for Phase 1–2 + PWA stance.  
6. CI step runs override eval with `--fail-on-gate`.

### Explicitly not done

- Distillation / weight downloads  
- Claiming medical-device validation  
- Weakening `applyEmergencyOverride`

---

## 5. Next step

**Human:** extract/publish Pages per `docs/PUBLISH.md`.  
**Engineering (optional next):** expand scenarios toward 50 with “demo 20 + draft N” labeling; grow multilingual / adversarial eval sets — still no training.
