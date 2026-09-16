# CHW Demo Pack — checklist execution (2026-09-16)

**Live:** https://entexcelsiorent-cyber.github.io/chw-companion/  
**Guide:** [`DEMO.md`](../../DEMO.md)  
**Screenshots:** this folder

## Honesty checklist

| Check | Result |
|-------|--------|
| Safety banner visible (not a medical device) | PASS — live + screenshots |
| CACHE-FIRST badge (not LIVE Gemma by default) | PASS |
| Demo story strip: gemma-3 cache + optional Gemma 4 backend | PASS |
| Sample path uses curated cache | PASS — Malaria → URGENT + recommended action |
| Queue notes localStorage / shared-phone clear | PASS |
| No FDA/WHO / on-device Gemma claims in above-fold | PASS |

## Shot list execution

| Shot | Result | Artifact |
|------|--------|----------|
| 1. Above-fold / sample loaded | PASS | `01-sample-loaded.png` |
| 2. Malaria assess → urgency | PASS | `02-malaria-urgent-result.png` |
| 3. Queue ranked entry | PASS (pre-fix showed age unknown — fixed in `app/index.html`) | `03-queue-urgent.png` |
| 4. Swahili sample | Deferred to human video (`DEMO.md` shot 4) | — |
| 5. Airplane / offline | Deferred to human | — |

## Smoke / Pages

| Check | Result |
|-------|--------|
| Live Pages HTTP | PASS — title `CHW Companion — Triage AI` |
| `python eval/score_urgency.py --sut override --fail-on-gate` | PASS |
| `python eval/score_urgency.py --sut fe_mock --fail-on-gate` | PASS |

## Code polish applied this pass

- Sample + symptom chips → `<button type="button">` (keyboard/a11y)
- `loadSample` pre-fills age/sex from prompt (fixes queue “age unknown” on demo cases)
- Footer honesty: “Optional live Gemma 4 only with backend”

## Human remaining

- Record 60–90 s video per `DEMO.md` (optional)
- After push to Pages repo, re-grab queue screenshot to show age `4y`
