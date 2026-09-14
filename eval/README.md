# Eval harness (Phase 2)

Held-out fixtures + urgency/override scorer for CHW Companion.  
**Not** clinical validation. **Not** a medical-device study.

## Files

| File | Role |
|------|------|
| `eval_core.json` | Held-out vignettes with urgency gold + `expects_override` |
| `score_urgency.py` | Scorer: exact match, under-escalation, critical under-call, override recall |

## Run

From the `chw-companion` repo root:

```bash
python eval/score_urgency.py
python eval/score_urgency.py --sut fe_mock
python eval/score_urgency.py --sut override --fail-on-gate --json-out eval/metrics_latest.json
```

Default SUT `override` applies a deliberate MONITOR under-call, then the same hard floor as `applyEmergencyOverride` in `app/index.html` (triggers parsed from that file). Portfolio gate: **critical under-call = 0** and **override recall = 100%** on `expects_override` items.

## Multilingual

`eval_core` includes thin SW/FR/HA slices. Metrics are printed **per language**. Do not claim parity with English or with Gemma’s marketed language counts.

## PWA note

This harness lives **outside** the PWA bundle. The shipped app remains cache-first offline CDS; the scorer does not download weights.
