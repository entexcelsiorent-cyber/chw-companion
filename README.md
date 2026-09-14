# CHW Companion

**An AI-assisted clinical triage tool for Community Health Workers (CHWs) in low-resource settings.**

Built for the Gemma 4 Good Hackathon (Kaggle × Google DeepMind, 2026). Apache 2.0.

---

## What it is

CHW Companion is a **mobile-first Progressive Web App (PWA)** that helps frontline health workers make a triage decision quickly when no doctor is in the room. The CHW types or pastes a symptom description in plain language and the app returns a structured assessment in two phases:

1. **Primary verdict** (cache: sub-ms; live Gemma when online: ≈7 s warm on T4): urgency tier, urgency colour, recommended action, model confidence.
2. **Clinical detail** (streams in behind the verdict): primary concern, warning signs to watch, questions to ask the caregiver, things not to do.

A **safety disclaimer is permanently visible** on every screen — this is decision support, not diagnosis.

A **triage queue** ranks each assessed patient by urgency so a worker juggling several cases can see who needs attention first. Queue entries persist in browser `localStorage` until cleared (shared-phone caution).

### PWA product model (portfolio story)

| Path | What ships | Offline? |
|------|------------|----------|
| **Curated scenario cache** | 20 keyword-matched cards inlined in the PWA | **Yes** — primary offline CDS |
| **Optional live Gemma 4** | Flask `/triage/*` when `window.CHW_BACKEND` is set | No — needs network + GPU host |
| **Future on-device WebGPU SLM** | Not in this build | — later phase only |

**Do not read this as on-device Gemma or offline full generative triage.** Offline coverage today is the curated cache + emergency override floor.

The file currently in `app/scenarios.json` was generated 2026-04-28 with `google/gemma-3-1b-it` and then curated. Live inference (when configured) is Gemma 4. Regenerating the cache with `regen_scenarios_gemma4.py` is the path to a same-family cache; that regeneration has not been checked in yet. Demo languages in the cache: English, Swahili, French, Hausa — **not** measured clinical parity across Gemma’s marketed language counts.

## Who it's for

Community Health Workers in rural and underserved settings — about 1.5 million globally — who:

- See patients without a doctor on site
- Have intermittent or no internet connectivity
- Work in their local language, not always English
- Need a structured second opinion to back a referral decision

It is **not** a replacement for clinical training, a medical device, or a diagnosis tool. See `SAFETY.md` for the design rationale behind that boundary.

## How Gemma 4 is used

Two complementary surfaces — **cache-first PWA**, optional live teacher:

- **Cached responses (offline PWA path)**: 20 canonical scenarios bundled as inline JSON. Sub-millisecond, works offline after install/`file://`. Tagged `google/gemma-3-1b-it` (generated 2026-04-28, curated). This is the primary portfolio demo path — **not** on-device generative Gemma.
- **Live inference (optional, online)**: Gemma 4 (E4B or text-only E2B) via Flask on a GPU host. Primary ≈7 s warm / detail ≈25 s warm on T4. Set `window.CHW_BACKEND` in the browser console after starting `kaggle_inference_server.py` or `backend/server.py`.

Gemma markets broad multilingual capability; this prototype only ships curated demo coverage in EN/SW/FR/HA. **Do not treat 35+ or 140+ as measured CHW-clinical parity.**

The honest division: **cache for common presentations always; live inference for novel cases when online**. A future on-device WebGPU SLM is optional and out of Phase 1–2 scope.

## Live demo

**Public PWA:** https://entexcelsiorent-cyber.github.io/chw-companion/

Cache-first offline triage UX (curated scenarios + emergency override). Live Gemma is optional and not required for the demo. Publish notes: [`docs/PUBLISH.md`](docs/PUBLISH.md).

Local fallback:

```bash
python -m http.server 8765 --directory app
# http://127.0.0.1:8765/
```

The cached-scenario demos (three sample chips) work without any backend. After first load over HTTPS/localhost, the service worker keeps the PWA shell available offline.

For optional **live Gemma 4** (novel cases beyond the cache):

1. Run `kaggle_inference_server.py` in a Kaggle notebook (GPU T4, Internet ON, `HF_TOKEN` + `NGROK_TOKEN` secrets), or local `backend/server.py` with GPU.
2. In the browser console: `window.CHW_BACKEND = "https://…";`
3. Assess a non-cached vignette — primary ~7 s warm when the backend is healthy.

### Urgency / override eval (no GPU)

```bash
python eval/score_urgency.py --sut override --fail-on-gate
# see eval/README.md
```


---

## How to run it

### Frontend only (no setup, no backend, runs anywhere)

Commands assume this directory is the project root (after extraction, or after `cd` into it).

```bash
# Open directly in any modern browser
app/index.html
```

Or serve over HTTP (recommended for a polished demo — some browsers add restrictions on `file://`):

```bash
python -m http.server 8765 --directory app
# Then open http://127.0.0.1:8765/
```

The frontend ships with the cached-scenario JSON inlined, so it works fully without a backend. Three sample-patient chips load canonical cases in one tap.

### With live Gemma inference

The backend is designed for Kaggle T4 (or any CUDA GPU host). Local CPU inference is too slow to be useful (~30–60 s per call) and the server falls back to mock mode when no GPU is detected.

```bash
pip install -r backend/requirements.txt
export HF_TOKEN=your_huggingface_token   # required to fetch Gemma 4 weights
python backend/server.py   # Flask on :5000; defaults to google/gemma-4-e4b-it
```

Endpoints:

```bash
curl http://localhost:5000/health
curl -X POST http://localhost:5000/triage/primary \
     -H 'Content-Type: application/json' \
     -d '{"symptoms":"4 year old, fever 39C, vomiting, malaria zone"}'
curl -X POST http://localhost:5000/triage/detail \
     -H 'Content-Type: application/json' \
     -d '{"symptoms":"4 year old, fever 39C, vomiting, malaria zone"}'
```

To force mock mode (useful for offline development): `export CHW_MOCK_ONLY=1`.

### Regenerating cached scenarios

The cache file `app/scenarios.json` is generated by a Kaggle notebook running Gemma 4 on T4 and then manually curated for clinical correctness. To regenerate:

1. Run `regen_scenarios_gemma4.py` on Kaggle (T4 GPU, internet on, `HF_TOKEN` secret attached). The script tries text-only E2B → text-only E4B → E2B → E4B in order.
2. Download `scenarios_gemma4_raw.json` from the notebook's output tab.
3. Spot-check each scenario manually using the printed curation report: (a) `urgency` tier and `urgency_color` match the clinical severity (small models can collapse responses to URGENT/red — the curation pass corrects this); (b) `language_detected` matches the input language; (c) `do_not_do` entries read as prohibitions ("Do not X"), not instructions.
4. Set `curated_at` and `curation_note` in the JSON, then replace `app/scenarios.json`.
5. Re-inline into `app/index.html` (the file:// path requires inline JSON, not a separate fetch).

## Hardware requirements

| Path | Hardware | Latency | Notes |
|------|----------|---------|-------|
| Cached scenarios | Any browser, any device | <1 ms | Works offline; covers 20 canonical presentations |
| Live primary phase | Kaggle T4 (or equivalent CUDA GPU) | ≈7 s warm | Gemma 4 E4B fp16, ≈50 output tokens |
| Live detail phase | Kaggle T4 (or equivalent CUDA GPU) | ≈25 s warm | Gemma 4 E4B fp16, ≈300 output tokens, streams behind primary |
| Local CPU (any) | Mock responses only | Instant (mock) | CPU inference of Gemma 4 is too slow; mock mode is the dev path |

We do not claim CHW Companion runs on a $50 Android phone. Gemma 4 E4B weights are ~16 GB; running them at acceptable latency requires a datacenter-class GPU. The production model is hosted on a shared inference tier (Kaggle T4); the app on the CHW's phone is a thin web client, with the cache layer providing offline coverage of the most common cases. This is the architecture that actually works under real bandwidth constraints — not the marketing version.

## Impact pathway

There are an estimated 1.5 million CHWs globally serving roughly 2 billion people who lack reliable access to clinical care. Most of them have a smartphone and intermittent connectivity. None of them have a clinical decision support tool designed for their specific context — local language, low literacy in clinical English, no specialist backup, a queue of patients who need triaging.

The path from this working prototype to that impact:

1. **Keep the codebase public** (Apache 2.0, already done) so any organisation can fork and adapt.
2. **Pilot with a CHW organisation** — partner with a single regional NGO or ministry-of-health programme to deploy in a defined catchment area. Validate triage agreement against trained nurses on the same cases.
3. **Clinical validation study** — measure CHW decision agreement, time-to-referral, and patient outcomes against a baseline-care arm. This is the bar required for WHO digital-health pre-qualification.
4. **Scale-up pathway** — WHO Digital Health Atlas listing, ministry-of-health endorsement in pilot countries, local-language scenario libraries for additional regions.

That is a multi-year arc. This repo is step zero — proof that the technical pieces fit together honestly. The Gemma 4 Good Hackathon (closed 2026-05-18) is how the prototype was built; the placement is unknown and is not claimed here.

## Project layout

```
├── app/
│   ├── index.html          Mobile-first PWA (scenarios inlined)
│   ├── scenarios.json      20 curated cached scenarios
│   ├── manifest.webmanifest
│   ├── sw.js               Offline app-shell service worker
│   └── icon.svg
├── backend/
│   ├── server.py           Flask wrapper for Gemma 4 E4B (T4 path)
│   └── requirements.txt
├── eval/
│   ├── eval_core.json      Held-out urgency / override fixtures
│   ├── score_urgency.py    Scorer (critical under-call, override recall)
│   └── README.md
├── docs/                   SLM strategy, eval, safety, PUBLISH.md
├── .github/workflows/
│   ├── pages.yml           GitHub Pages deploy
│   └── test.yml            Smoke + override eval gates
├── README.md
├── SAFETY.md
└── PROJECT.md              Deprecated concept doc (historical only)
```

## License

Apache 2.0 — required by the Gemma 4 Good Hackathon rules and intentional. Open weights, open code, open to fork by any organisation that needs it.

## Acknowledgements

Built with [Gemma](https://ai.google.dev/gemma) (Google DeepMind), [Hugging Face Transformers](https://huggingface.co/docs/transformers), Flask, and vanilla HTML/CSS/JS. Inference tier provided by Kaggle's free T4 GPU during development. Solo build, no team — see `SUBMISSION.md` for the constraints that shaped the design.
