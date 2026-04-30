# Architecture

CHW Companion is a thin web frontend, a Flask backend wrapping Gemma 3 1B, and a pre-generated cache layer that bypasses inference for canonical cases. The whole system is designed so that a CHW with intermittent connectivity always gets a useful response — instant for cached cases, and a few seconds plus a streaming detail block for novel cases when online.

## End-to-end flow

```
                         ┌───────────────────────────────┐
                         │   CHW phone / browser         │
                         │   chw-companion/app/index.html│
                         │   (PWA, mobile-first)         │
                         └──────────────┬────────────────┘
                                        │
                                        │  symptoms typed in any language
                                        ▼
                         ┌───────────────────────────────┐
                         │  Cache layer (in-app)         │
                         │  app/scenarios.json (inlined) │
                         │  20 canonical scenarios       │
                         │  trigger_keywords match       │
                         └──────┬───────────────┬────────┘
                                │ HIT           │ MISS
                                │               │
                                │               ▼
                                │  ┌───────────────────────────────┐
                                │  │  Flask backend                │
                                │  │  chw-companion/backend/       │
                                │  │  server.py                    │
                                │  │                               │
                                │  │  POST /triage/primary  (~3s)  │
                                │  │  POST /triage/detail   (~20s) │
                                │  │  GET  /health                 │
                                │  └──────────────┬────────────────┘
                                │                 │
                                │                 ▼
                                │  ┌───────────────────────────────┐
                                │  │  Gemma 3 1B  (fp16)           │
                                │  │  Hugging Face Transformers    │
                                │  │  Kaggle T4 GPU instance       │
                                │  └──────────────┬────────────────┘
                                │                 │
                                ▼                 ▼
                         ┌───────────────────────────────┐
                         │  Render in app                │
                         │  ┌──────────────────────────┐ │
                         │  │ Primary card             │ │
                         │  │  urgency, colour, action │ │  3.3s warm
                         │  ├──────────────────────────┤ │
                         │  │ Detail block (streams)   │ │
                         │  │  concern, warnings,      │ │  20s warm
                         │  │  questions, do_not_do    │ │
                         │  └──────────────────────────┘ │
                         │  Triage queue (ranked)        │
                         │  Permanent safety banner      │
                         └───────────────────────────────┘
```

Cache-hit path: ≈600 ms primary card + ≈800 ms detail (artificial delays preserve the two-phase UX feel; real inference time is sub-millisecond).
Cache-miss path: ≈3.3 s primary + ≈20 s detail streaming behind it.

## Two-phase rationale

Single-call full-schema inference does not clear an acceptable-latency bar on the hardware we have access to — measured 19.96 s for a 299-token clinical schema on T4 (Apr 27 hardware test). A CHW staring at a spinner for 20 seconds for an emergency case is a worse experience than a doctor's office.

Splitting the schema into a fast primary phase (≈50 tokens) and a slow detail phase (≈300 tokens) gets the urgency decision in front of the worker in a few seconds. The detail block is information they need but can read while it fills in. The architecture pays a small total-latency cost for a much better perceived-latency story.

| Phase | Output tokens | Latency on T4 | Schema |
|-------|---------------|---------------|--------|
| Primary | ≈50 | ≈3.3 s | `urgency`, `urgency_color`, `recommended_action`, `confidence` |
| Detail | ≈300 | ≈20 s | `primary_concern`, `warning_signs[]`, `questions_to_ask[]`, `do_not_do[]` |

## Cache layer

The cache covers presentations CHWs see most often, generated once on Kaggle T4 and then manually curated for clinical correctness (the 1B model collapsed all 20 to URGENT/red on first generation; a clinician-style review pass corrected urgency tiers, urgency colours, language tags, and trigger keywords). After curation:

- 20 scenarios across 8 conditions and 5 languages
- Urgency distribution: 10 EMERGENCY / 6 URGENT / 2 ROUTINE / 2 MONITOR
- Each scenario carries 2–3 trigger keywords that are guaranteed substring-present in its own user prompt (verified 20/20 self-match) and unique against its siblings (no false positives across the set)

The frontend inlines `scenarios.json` as a `<script type="application/json">` block in `index.html` so the cache works on `file://` (browsers block `fetch()` on the file: origin). This was the bug that initially broke the sample-patient chips — fixed by switching from a fetch to inline JSON.

Match rule: case-insensitive substring; **all** trigger keywords for a scenario must appear in the input. First match wins. No vector similarity, no embeddings — overkill at 20 scenarios, and a deterministic keyword rule is auditable in a way semantic match isn't.

When the cache misses and connectivity is available, the frontend calls the Flask backend; when both miss, the user sees a clean message ("inference unavailable, try when signal returns") rather than a console error.

## Backend (Flask)

`backend/server.py` is intentionally small. Three routes (`/health`, `/triage/primary`, `/triage/detail`), a single Gemma loader, and mock-response fallbacks for local CPU development. The loader bails to mock mode if `CHW_MOCK_ONLY` is set or no CUDA GPU is present — local CPU inference of Gemma 3 1B is ≈70 s and not useful for live work.

Model loading uses `device_map="auto"` and `dtype=torch.float16` — the configuration that was empirically validated on Kaggle T4 (Apr 24, see `docs/superpowers/notes/2026-04-27-gemma4-status.md`). The chat template is normalised across transformers versions; a fallback merges the system prompt into the user turn for Gemma variants that reject the system role.

JSON extraction is a regex `\{.*\}` followed by `json.loads`; on parse failure the route returns a deterministic mock response so the frontend never sees a 500. This is by design: a CHW should never be blocked by a model parse failure.

## Frontend (vanilla)

`app/index.html` is a single file — no build, no framework. Why:

- Zero dependencies → works in any browser the CHW's phone happens to ship with
- Single file → trivially deployable as a PWA, easy to inline the cache JSON
- Plain `fetch` calls → no service-worker complexity for the offline path; the cache lives in-app
- Auditable → judges and pilot partners can read the entire client in one sitting

The structure: a permanent safety banner, a chief-complaint card with sample-patient chips for one-tap demo cases, a result screen split into primary card + streaming detail block, and a triage queue card that ranks all assessed patients by urgency.

## Trade-offs we explicitly accepted

- **Not on-device.** Gemma 3 1B fp16 is ≈2 GB and even quantised forms underperform on a typical $50 Android. Inference lives on a GPU tier; the phone runs the cache + UI. The honest framing matches the actual working architecture.
- **Cache layer is keyword-matched, not semantic.** With 20 scenarios, deterministic rules win on auditability. Semantic match becomes worth the cost at hundreds of scenarios.
- **No streaming SSE for the detail phase.** The detail endpoint waits for the full generation, then returns. True token-by-token rendering would require rewriting both ends; the current "primary first, detail second" UX gets most of the benefit at a fraction of the cost.
- **Manual curation of the cached scenarios.** The 1B model's first generation needed clinician-style review (10 EMERGENCY collapsed to URGENT, language tags wrong on 3/20). Curation is part of the build pipeline, not a one-time accident.

## File reference

| File | Role |
|------|------|
| `app/index.html` | PWA entry, cache layer, sample chips, all UI |
| `app/scenarios.json` | 20 curated cached scenarios (inlined into index.html for `file://` support) |
| `backend/server.py` | Flask wrapper, two-phase Gemma 3 1B inference, mock fallbacks |
| `backend/requirements.txt` | Pinned Flask + transformers + torch versions |
| `test_gemma4_hardware_v2.py` | Reference path for Gemma 4 E4B hardware validation on Kaggle T4 |
| `test_gemma4_hardware_1b.py` | Reference path for Gemma 3 1B hardware validation on Kaggle T4 |
