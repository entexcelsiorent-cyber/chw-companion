# SLM Architecture — CHW Companion

**Purpose:** Describe the inference topology as shipped and how a smaller specialized SLM fits without breaking safety floors or offline UX.  
**Shipped references:** `ARCHITECTURE.md`, `app/index.html`, `backend/server.py`, `kaggle_inference_server.py`.

---

## 1. Architecture today (authoritative)

```
CHW browser (app/index.html)
        │
        ├─► matchCachedScenario(symptoms)     # all trigger_keywords ⊆ input
        │         │ HIT
        │         └─► cached primary + detail (+ artificial 600ms/1400ms delay)
        │                   │
        │                   └─► applyEmergencyOverride(primary, symptoms)
        │
        └─► MISS
                  ├─► POST {API_BASE}/triage/primary   # Gemma 4 or mock
                  ├─► POST {API_BASE}/triage/detail    # parallel
                  │         │ failure / timeout
                  │         └─► mockPrimary / mockDetail (frontend)
                  └─► applyEmergencyOverride on primary before render
```

`API_BASE` = `window.CHW_BACKEND` if set; else `http://localhost:5000` on `file:`; else empty relative (same-origin Pages host would need a backend elsewhere).

### Components

| Component | Path | Role |
|-----------|------|------|
| PWA UI | `app/index.html` | Single-file client; banner; queue; override; mocks |
| Scenario cache | `app/scenarios.json` | Curated offline responses |
| Inliner | `inline_scenarios.py` | Keeps inline JSON = disk JSON for `file://` |
| Flask API | `backend/server.py` | `/health`, `/triage/primary`, `/triage/detail`, `/triage`, `/languages` |
| Kaggle wrapper | `kaggle_inference_server.py` | Demo hosting path (ngrok + T4) |
| Cache regen | `regen_scenarios_gemma4.py` | Teacher regeneration on GPU |

---

## 2. Three reasoning modes (productization view)

| Mode | Latency | Connectivity | Model | Auditability |
|------|---------|--------------|-------|--------------|
| **A. Cached scenarios** | &lt;1 ms compute (+ UX delay) | None | Precomputed teacher output, curated | Highest — static JSON |
| **B. Live teacher (Gemma 4)** | ~7 s primary / ~25 s detail (E4B T4 warm) | Required | `CHW_MODEL_ID` default `google/gemma-4-e4b-it` | Medium — prompts + logs policy |
| **C. Distilled SLM** (future) | Target: sub-second–few seconds | On-device or small GPU | Specialized student | Medium — needs eval gates |

Mode C does **not** replace Mode A for canonical cases until the SLM matches curated gold on those ids. Prefer: **cache first, SLM second, teacher third**.

### Recommended routing after SLM exists

```
input
  → emergency override check (can short-circuit display even if model disagrees)
  → cache keyword match? → serve curated
  → on-device / edge SLM available & confidence gate? → SLM JSON
  → network + teacher available? → Gemma 4 two-phase
  → else mock / unavailable message (never silent hallucination of “live”)
```

---

## 3. Cached scenarios vs live Gemma vs smaller distill

### Cached scenarios

- **Match rule:** case-insensitive; **every** keyword in `trigger_keywords` must appear; first match wins (`matchCachedScenario`).
- **Not semantic search.** Intentional for auditability at N≈20; revisit only at hundreds of scenarios (`ARCHITECTURE.md` trade-offs).
- **UX:** artificial delays preserve two-phase feel for demos.
- **Family mismatch today:** cache `model_id` is `google/gemma-3-1b-it`; live is Gemma 4. Product docs and UI status text should not imply the cache is Gemma 4 until regen lands. (Inline comments in `index.html` now state gemma-3-1b-it explicitly.)

### Live Gemma (Flask)

- Loads only if CUDA present and `CHW_MOCK_ONLY` unset; else mock (`load_gemma` in `backend/server.py`).
- Greedy decoding (`do_sample=False`); JSON extracted via regex `\{.*\}`.
- Parse failure → mock response (no HTTP 500 to CHW).
- Two-phase split exists because full-schema E4B ~25 s was unacceptable for urgency (`ARCHITECTURE.md`).

**Not true token streaming:** detail endpoint returns after full generation; frontend “streams” only in the UX sense (primary card first).

### Smaller distill

Fit options:

1. **Urgency head only** — classify 4 tiers; fill action text from templates keyed by condition hints. Smallest, easiest to certify behaviorally.
2. **Full schema seq2seq** — drop-in replacement for `/triage/primary` (+ optional detail).
3. **Speculative decoding / assisted** — SLM draft + teacher verify (pilot-scale; complex).

Hardware honesty from README: do not claim E4B-class models on low-end phones. A 1B-class quantized student *might* be on-device later; treat as experiment with a pass/fail gate.

---

## 4. On-device vs Flask GPU

| Deployment | Who runs weights | When appropriate |
|------------|------------------|------------------|
| **Browser-only + cache** | No weights | Portfolio demo, offline common cases |
| **Flask on Kaggle T4 / cloud GPU** | Gemma 4 teacher | Hackathon demo, novel-case live path |
| **Flask on local 12GB GPU** | Possible for smaller variants | Dev; not assumed for CHW field |
| **On-device SLM (future)** | Phone NPU/CPU GGUF etc. | Only after latency + quality gates |
| **Mock-only** | None | CI (`.github/workflows/test.yml` uses `CHW_MOCK_ONLY=1`), local without GPU |

Portfolio positioning (`PORTFOLIO_ONEPAGER.md`): “offline clinical-triage PWA” is true via **cache + single-file app**, not via on-device Gemma 4.

---

## 5. Fallback UX (ordered by safety)

1. **Emergency override** — forces EMERGENCY/red on red-flag substrings/regexes regardless of cache/model/mock (`applyEmergencyOverride`, `EMERGENCY_TRIGGERS` in `app/index.html`). Tags `_override_applied: true` when changing tier.
2. **Cache hit** — curated clinical content.
3. **Live primary/detail** — teacher JSON.
4. **Frontend mock** — keyword conservative path when fetch fails/times out (`PRIMARY_TIMEOUT_MS=20000`, `DETAIL_TIMEOUT_MS=45000`).
5. **Backend mock** — if model missing/parse fails (`mock_primary` / `mock_detail` in `server.py`).
6. **Honest unavailable** — preferred when neither cache nor mocks should invent clinical detail for out-of-distribution text (productization should tighten this; today mocks are fairly eager on fever/cough keywords).

Permanent banner text (also `SAFETY_DISCLAIMER` in `server.py`):

> Decision support tool only. Not a diagnosis. Always use your clinical judgment. When uncertain, escalate urgency.

---

## 6. Logging without PII

### Current behavior

| Location | What is stored | PII-like? |
|----------|----------------|-----------|
| Server durable logs | No dedicated symptom logger in `server.py` | Low if process logs are default Flask |
| API response | Echoes `patient_context` with symptoms | In transit to client only |
| Browser `localStorage` key `chw_queue_v1` | age, sex, **full symptoms**, primary/detail | **Yes — on device, survives reload** |
| Console | Cache load messages; no intentional symptom telemetry | Low |

`SAFETY.md` historically said the queue “lives in browser memory and is wiped on reload.” **That is inaccurate vs code** — see `REVIEW.md`. Architecture productization must use the localStorage truth.

### Target logging policy (portfolio → pilot)

| Event | Allowed fields | Forbidden |
|-------|----------------|-----------|
| Client analytics (optional, off by default) | cache_hit bool, latency bucket, urgency tier, override bool, language pack id | raw symptoms, free text, GPS, names |
| Server metrics | request count, mode (gemma4/mock), latency, parse_fail rate | raw symptoms body |
| Pilot quality review | De-identified vignettes under DPA/ethics | unrestricted cloud sync of PHI |

### Implementation guidance (future code — not this docs phase)

- Add `CHW_LOG_SYMPTOMS=0` default on server; never log request JSON at INFO.
- Queue export should support “clear” (already) and optionally store **hashes** of symptoms instead of plaintext for demos.
- Status badge already distinguishes LIVE · GEMMA 4 / LIVE · MOCK / OFFLINE (CACHED) / CACHED — keep operational signal without patient text.

---

## 7. Safety floors outside the model

These remain mandatory regardless of SLM swap:

1. Non-dismissible disclaimer UI  
2. Conservative system prompts (`PRIMARY_PROMPT` / `DETAIL_PROMPT`)  
3. Curated cache for ship scenarios  
4. `EMERGENCY_TRIGGERS` + `applyEmergencyOverride`  
5. Mock keyword escalation for unconscious / convuls / not breathing  
6. No dosing / no definitive diagnosis in prompts  

An SLM that scores well on accuracy but weak on refusal must **not** ship without floors 1, 4, 5.

---

## 8. Frontend deployment topology

| Host | Backend | Notes |
|------|---------|-------|
| GitHub Pages (`pages.yml`) | None by default | Cache demos work; live needs console `window.CHW_BACKEND` |
| Local `python -m http.server` | Optional Flask :5000 | Dev |
| `file://` | localhost:5000 default API_BASE | Inline cache required |
| NGO intranet static + on-prem GPU | Flask behind TLS | Pilot shape |

No service worker complexity for offline in the prototype — offline = inlined cache, not full PWA asset SW strategy (`ARCHITECTURE.md`).

---

## 9. Interface contract (stable for SLM drop-in)

Any student model behind Flask should preserve:

**Primary JSON**

```json
{
  "urgency": "EMERGENCY|URGENT|ROUTINE|MONITOR",
  "urgency_color": "red|orange|yellow|green",
  "recommended_action": "string",
  "confidence": "high|medium|low"
}
```

**Detail JSON**

```json
{
  "primary_concern": "string",
  "warning_signs": ["string"],
  "questions_to_ask": ["string"],
  "do_not_do": ["string"]
}
```

Plus server-added `disclaimer` and optional `patient_context`. Frontend override may add `_override_applied`.

---

## 10. Summary diagram (target product)

```
                 ┌────────────────────────────┐
                 │     Safety banner (UI)     │
                 └─────────────┬──────────────┘
                               │
                 ┌─────────────▼──────────────┐
                 │  Emergency override floor  │
                 └─────────────┬──────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   Curated cache         Distilled SLM         Gemma 4 teacher
   (scenarios.json)      (optional)            (Flask GPU)
          │                    │                    │
          └────────────────────┼────────────────────┘
                               ▼
                    Render primary → detail
                    Queue (minimize PII)
```
