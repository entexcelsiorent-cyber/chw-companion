# SLM Data Pipeline — CHW Triage

**Purpose:** Define how training / eval / cache data should be produced for a specialized CHW triage SLM, grounded in the existing `app/scenarios.json` + Gemma teacher path.  
**Constraint:** This phase documents the pipeline only. Do not download multi-GB weights or run training from these docs alone.

---

## 1. Current data artifact (as shipped)

| Property | Value in repo |
|----------|----------------|
| Path | `app/scenarios.json` (also inlined into `app/index.html` via `inline_scenarios.py`) |
| Count | 20 scenarios |
| Generator model | `google/gemma-3-1b-it` (`model_id` field) |
| Generated | `2026-04-28T17:06:09Z` |
| Curated | `curated_at: 2026-04-29` — primary urgency / language tags manually fixed; detail fields largely preserved from generation |
| Urgency mix | 10 EMERGENCY / 6 URGENT / 2 ROUTINE / 2 MONITOR |
| Languages in `language_detected` | English 15, Swahili 2, French 2, Hausa 1 |
| Conditions covered | malaria, pneumonia, diarrhoea, malnutrition, obstetric, snakebite, meningitis, trauma (ids in JSON) |

**Important honesty gap:** Live inference is Gemma 4 (`backend/server.py` default `google/gemma-4-e4b-it`). The checked-in cache is still Gemma 3 1B. Same-family regeneration is `regen_scenarios_gemma4.py` (not yet applied to replace `scenarios.json`).

### Scenario record schema (canonical)

Each scenario in `app/scenarios.json` roughly contains:

- `id`, `title_en`, `user_prompt`
- `trigger_keywords[]` — **all** must substring-match input (`matchCachedScenario` in `app/index.html`)
- `primary_response`: `urgency`, `urgency_color`, `recommended_action`, `confidence`
- `detail_response`: `primary_concern`, `warning_signs[]`, `questions_to_ask[]`, `do_not_do[]`, `language_detected`

Smoke tests in `.github/workflows/test.yml` assert: ≥20 scenarios, self-match of triggers against `user_prompt`, inline sync with disk JSON.

---

## 2. Pipeline stages (target)

```
[A] Condition & language taxonomy
        │
        ▼
[B] Prompt / vignette authoring (templates + regional variants)
        │
        ▼
[C] Teacher generation (Gemma 4 family via regen script / Flask prompts)
        │
        ▼
[D] Automatic lint (urgency colour map, do_not_do shape, trigger self-match)
        │
        ▼
[E] Clinician / CHW-experienced review (labels + exclusions)
        │
        ├──────────────┬──────────────────┐
        ▼              ▼                  ▼
[F1] Ship cache    [F2] Distill set    [F3] Held-out eval
 scenarios.json     (train/val)         (never for training)
```

---

## 3. Expanding `scenarios.json`

### 3.1 Expansion dimensions

| Dimension | Prototype | Portfolio target | Pilot target |
|-----------|-----------|------------------|--------------|
| Scenario count | 20 | 50–100 curated | 200+ with regional packs |
| Conditions | 8 families | + TB suspect, HIV danger signs, neonatal sepsis flags, burns (still triage-only) | Partner disease profile |
| Languages | 4 tagged (+ EN-heavy) | Parity packs: ≥10 per language for EN/SW/FR/HA | Add partner L1 languages with clinician translation |
| Severity balance | Skews EMERGENCY (by design) | Keep escalation bias; add more ROUTINE/MONITOR for calibration | Match catchment prevalence *without* under-escalating red flags |
| Trigger strategy | Exact multi-keyword AND | Still deterministic for audit; optional embedding index later | Same |

### 3.2 Authoring rules

1. **Every `user_prompt` must contain all of its `trigger_keywords`** (already enforced in CI).
2. **Triggers must be unique enough** to avoid cross-scenario false hits (documented failure mode: “oedema” matching malnutrition when “no oedema” appears — see `SAFETY.md`).
3. **`do_not_do` must be prohibitions** (“Do not X”), not assessments or orders. First-pass 1B output sometimes violates this (e.g. assessment text in `do_not_do` for pediatric malaria) — curation must catch it.
4. **No drug doses** in recommended_action (protocol name OK: “per CHW protocol”; “give X mg” is out).
5. **No definitive diagnosis wording** (“has malaria”) — prefer “suspected / possible / consistent with danger signs for …”.
6. **Red-flag vignettes** should remain EMERGENCY even if a teacher model under-calls (align with `applyEmergencyOverride` trigger philosophy).

### 3.3 Regeneration procedure (existing tooling)

Documented in `README.md` and implemented in `regen_scenarios_gemma4.py`:

1. Run on Kaggle T4 + Internet + `HF_TOKEN`.
2. Model chain: text-only E2B → text-only E4B → full E2B → full E4B.
3. Download `scenarios_gemma4_raw.json`.
4. Use printed curation report; manually fix urgency, colours, language tags, `do_not_do`.
5. Set `curated_at` / `curation_note`; replace `app/scenarios.json`.
6. Run `python inline_scenarios.py` so `app/index.html` does not serve stale inline JSON.

Keep `PRIMARY_PROMPT` / `DETAIL_PROMPT` in the regen script synchronized with `backend/server.py` (comment in regen script already requires this).

---

## 4. Synthetic vs clinician-reviewed labels

| Label source | Use | Risk | Mitigation |
|--------------|-----|------|------------|
| **Synthetic (Gemma teacher)** | Bootstrap volume; draft detail prose; distill candidates | Severity collapse (observed: 14/20 → URGENT/red on 1B pass); wrong language tags; bad `do_not_do` | Automatic lint + mandatory human curation before ship |
| **Clinician / experienced CHW review** | Urgency tier, referral timing, dangerous omissions | Cost, scarcity, inter-rater variance | Dual review on EMERGENCY; adjudication protocol |
| **Hybrid (recommended)** | Teacher drafts → clinician accepts/edits urgency + action; detail can be lighter-touch | Still not a clinical trial | Version labels with reviewer id (pseudonymous) and date |

### Label fields that require clinician sign-off before any “validated” claim

- `urgency` / `urgency_color`
- `recommended_action` (referral timing + forbidden harmful actions)
- Presence/absence of critical warning signs for that vignette
- Language correctness of non-English prompts and outputs

### Label fields that may remain synthetic longer (portfolio)

- Phrasing polish of `questions_to_ask`
- Ordering of non-critical warning signs

---

## 5. Multilingual coverage

### Reality check vs marketing

- Gemma 4 marketing / README cite broad multilingual capability (README: “140+”; `/languages` note in `server.py`: “35+”). **Do not treat either number as measured CHW-clinical parity.**
- Shipped cache is **English-dominant** (15/20). Non-English scenarios are smoke coverage, not parity.

### Pipeline requirements for multilingual

1. **Parallel vignettes:** same clinical case authored in EN + target language (not machine-translate-only for EMERGENCY).
2. **Language tag audit:** `language_detected` must match input language (Hausa→“Filipino” bug already happened).
3. **Disclaimer policy:** English disclaimer remains until clinician-reviewed localization (`SAFETY.md`).
4. **Eval split by language** (`SLM_EVAL.md`) — report separately; never average away language gaps.
5. **Trigger keywords** for non-Latin / non-English prompts must be substrings of the *actual* prompt text (Swahili/French/Hausa scenarios already follow this pattern).

### Suggested portfolio language packs

| Pack | Min scenarios | Notes |
|------|---------------|-------|
| EN core | 40 | Severity-balanced |
| SW | 15 | East Africa CHW relevance |
| FR | 15 | West/Central Africa programmes |
| HA | 10 | Start from existing `hausa-zazzabi-jariiri` |

---

## 6. Distillation from Gemma (teacher → student)

### Teacher

- Preferred: same family as live path — Gemma 4 E2B/E4B text variants used in `regen_scenarios_gemma4.py` / `MODEL_ID` in `backend/server.py`.
- Teacher prompt: copy `PRIMARY_PROMPT` and `DETAIL_PROMPT` exactly for consistency.

### Student candidates (conceptual — not executed here)

| Student class | Role | Notes |
|---------------|------|-------|
| Urgency-only classifier / ranker (tiny) | Map vignette → 4-tier urgency | Easier to eval; compose with template actions |
| Full JSON seq2seq SLM (≤1–2B) | Mimic primary+detail schema | Needs strong JSON validity eval |
| Speculative: on-device GGUF | Novel cases offline | Only after hardware gate |

### Distillation data mix

1. **Curated scenarios** (high weight) — gold urgency
2. **Teacher generations on paraphrases** of curated prompts (medium weight) — only keep if urgency agrees with gold or reviewer
3. **Hard negatives / near-miss** — “fever without danger signs” vs “fever + convulsion”
4. **Refusal / out-of-scope** — non-health queries, requests for dosing, self-harm, violence (see safety exclusions)

### What not to distill

- Arbitrary internet medical text without triage framing
- Outputs that prescribe controlled substances or exact mg/kg doses
- Content that assists harm, weapons, or evasion of care

---

## 7. Evaluation sets

Hold out **before** expansion contamination:

| Split | Size (portfolio) | Contents | Used for |
|-------|------------------|----------|----------|
| `eval_core` | 40–60 | Stratified by urgency + condition | Primary accuracy |
| `eval_multilingual` | ≥5 per language | Parallel cases | Parity report |
| `eval_adversarial` | 20–40 | Typos, negation (“no oedema”), conflicting symptoms, jailbreak-ish “ignore disclaimer” | Safety / robustness |
| `eval_override` | All EMERGENCY trigger phrases from `EMERGENCY_TRIGGERS` in `app/index.html` | Override must fire | Floor integrity |

**Leakage rule:** No eval vignette may share `id` or near-duplicate `user_prompt` with train/cache ship set without marking `overlap=true`.

Detailed metrics: `SLM_EVAL.md`.

---

## 8. Safety exclusions (data must not teach)

Exclude or hard-refuse examples that:

| Category | Example | Desired behavior |
|----------|---------|------------------|
| Definitive diagnosis demand | “Tell me the disease for certain” | Supportive triage + disclaimer; no certainty claim |
| Dosing / prescription | “What mg of X for a 4yo?” | Refuse dose; refer to protocol / facility |
| Harmful procedures | Tourniquet misuse, unsafe delivery instructions beyond CHW scope | Prefer `do_not_do` + escalate |
| Non-care / malicious | Weaponization, how to fake symptoms for diversion | Refuse; no assistance |
| Child sexual content | Any | Refuse; out of domain |
| Identity-based triage | Rank by ethnicity/religion | Never collect; never label |

Exclusions belong in both **training filters** and **runtime refusal tests**.

---

## 9. PII and logging in the data path

| Stage | Rule |
|-------|------|
| Synthetic vignettes | Use fictional ages/sexes; no real patient text |
| Pilot transcripts | De-identify; separate ethics approval; never commit raw logs to git |
| Cache ship files | No real names, phone numbers, GPS |
| Distill corpora | Strip free-text that could re-identify a catchment |

Prototype server returns `patient_context` in JSON responses (`backend/server.py`) but does not implement durable server-side symptom logging. Keep it that way unless a pilot defines a retention policy.

---

## 10. Versioning and provenance

Every shipped `scenarios.json` should retain:

```json
{
  "version": "...",
  "generated_at": "...",
  "model_id": "...",
  "curated_at": "...",
  "curation_note": "...",
  "hardware": { }
}
```

Add when productizing:

- `label_protocol_version`
- `reviewer_count` / `review_status` (`synthetic` | `spot_checked` | `clinician_signed`)
- `eval_suite_commit` that gated the release

---

## 11. Immediate next data actions (no training required)

1. Run Gemma 4 regen on Kaggle when ready; curate; inline.
2. Fix known `do_not_do` quality issues in English core scenarios during that curation.
3. Author `eval_core` as a **separate** JSON (do not only reuse the 20 demo prompts).
4. Document reviewer checklist (urgency, colour, action, language, do_not_do shape, no dosing).
