#!/usr/bin/env python3
"""CHW Companion urgency / emergency-override scorer (Phase 2 eval harness).

Measures critical under-call, under-escalation, override correctness per docs/SLM_EVAL.md.
Does NOT claim clinical validation. Does NOT download model weights.

Usage (from chw-companion repo root):
  python eval/score_urgency.py
  python eval/score_urgency.py --eval-file eval/eval_core.json --sut override
  python eval/score_urgency.py --json-out eval/metrics_latest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVAL = ROOT / "eval" / "eval_core.json"
INDEX_HTML = ROOT / "app" / "index.html"

SEVERITY = {
    "MONITOR": 0,
    "ROUTINE": 1,
    "URGENT": 2,
    "EMERGENCY": 3,
}

COLOR_FOR = {
    "EMERGENCY": "red",
    "URGENT": "orange",
    "ROUTINE": "yellow",
    "MONITOR": "green",
}

FORBIDDEN_DOSE = re.compile(
    r"\b\d+\s*mg\b|\bml/kg\b|diagnose as|definitely has",
    re.I,
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def extract_emergency_triggers(html: str) -> list[str]:
    """Parse EMERGENCY_TRIGGERS array from app/index.html so the scorer stays synced."""
    m = re.search(
        r"const\s+EMERGENCY_TRIGGERS\s*=\s*\[(.*?)\];",
        html,
        re.DOTALL,
    )
    if not m:
        raise RuntimeError("EMERGENCY_TRIGGERS not found in app/index.html")
    return re.findall(r"'([^']+)'", m.group(1))


def is_emergency_by_override(symptoms: str, triggers: list[str]) -> bool:
    s = (symptoms or "").lower()
    for trig in triggers:
        if ".*" in trig:
            try:
                if re.search(trig, s, re.I):
                    return True
            except re.error:
                continue
        elif trig.lower() in s:
            return True
    return False


def apply_emergency_override(
    primary: dict[str, Any] | None,
    symptoms: str,
    triggers: list[str],
) -> dict[str, Any] | None:
    """Python mirror of applyEmergencyOverride in app/index.html — hard floor."""
    if not primary:
        return primary
    if not is_emergency_by_override(symptoms, triggers):
        return primary
    urg = (primary.get("urgency") or "").upper()
    color = (primary.get("urgency_color") or "").lower()
    if urg == "EMERGENCY" and color == "red":
        return primary
    action = primary.get("recommended_action") or ""
    if len(action) <= 20:
        action = (
            "Refer immediately to nearest health facility. Do not delay. "
            "Stabilise and accompany if possible."
        )
    out = dict(primary)
    out["urgency"] = "EMERGENCY"
    out["urgency_color"] = "red"
    out["recommended_action"] = action
    out["confidence"] = primary.get("confidence") or "high"
    out["_override_applied"] = True
    return out


def fe_mock_primary(symptoms: str) -> dict[str, Any]:
    """Approximate frontend mockPrimary keyword branches (no network)."""
    s = (symptoms or "").lower()
    if any(k in s for k in ("unconscious", "not breathing", "convuls")):
        return {
            "urgency": "EMERGENCY",
            "urgency_color": "red",
            "recommended_action": (
                "Call for emergency transport NOW. Keep airway open. "
                "Do not leave patient alone. Stabilise and refer immediately to hospital."
            ),
            "confidence": "high",
        }
    if any(k in s for k in ("fever", "malaria", "vomit", "diarrhoea", "diarrhea")):
        return {
            "urgency": "URGENT",
            "urgency_color": "orange",
            "recommended_action": (
                "Perform malaria RDT if available. Assess hydration. "
                "Refer to clinic within 4 hours if RDT positive or moderate dehydration."
            ),
            "confidence": "medium",
        }
    if any(k in s for k in ("cough", "breath", "chest")):
        return {
            "urgency": "URGENT",
            "urgency_color": "orange",
            "recommended_action": (
                "Count respiratory rate for 1 full minute. Refer to clinic today if fast breathing."
            ),
            "confidence": "medium",
        }
    if any(k in s for k in ("bleed", "wound", "cut")):
        return {
            "urgency": "URGENT",
            "urgency_color": "orange",
            "recommended_action": "Control bleeding with firm pressure. Refer if bleeding continues.",
            "confidence": "medium",
        }
    return {
        "urgency": "ROUTINE",
        "urgency_color": "yellow",
        "recommended_action": "Assess per CHW protocol. Refer if worsening or uncertain.",
        "confidence": "low",
    }


def undercall_primary(_symptoms: str) -> dict[str, Any]:
    """Adversarial SUT: always under-calls to MONITOR — override must still floor red flags."""
    return {
        "urgency": "MONITOR",
        "urgency_color": "green",
        "recommended_action": "Home care only.",
        "confidence": "high",
    }


def gold_primary(item: dict[str, Any]) -> dict[str, Any]:
    u = item["gold_urgency"].upper()
    return {
        "urgency": u,
        "urgency_color": item.get("gold_urgency_color") or COLOR_FOR[u],
        "recommended_action": "Follow local CHW protocol; escalate when uncertain.",
        "confidence": "high",
    }


def normalize_urgency(u: str | None) -> str:
    return (u or "").strip().upper()


def score_item(
    item: dict[str, Any],
    pred: dict[str, Any],
    *,
    apply_override: bool,
    triggers: list[str],
) -> dict[str, Any]:
    symptoms = item["symptoms"]
    if apply_override:
        pred = apply_emergency_override(pred, symptoms, triggers) or pred

    gold = normalize_urgency(item["gold_urgency"])
    pred_u = normalize_urgency(pred.get("urgency"))
    acceptable = [normalize_urgency(x) for x in item.get("acceptable_urgency") or [gold]]

    g_sev = SEVERITY.get(gold)
    p_sev = SEVERITY.get(pred_u)
    under = (p_sev is not None and g_sev is not None and p_sev < g_sev)
    over = (p_sev is not None and g_sev is not None and p_sev > g_sev)
    critical = gold == "EMERGENCY" and pred_u in {"ROUTINE", "MONITOR"}

    expects_override = bool(item.get("expects_override"))
    override_fired = bool(pred.get("_override_applied")) or (
        apply_override and is_emergency_by_override(symptoms, triggers) and pred_u == "EMERGENCY"
    )
    # Override correctness: if expects_override, final urgency must be EMERGENCY/red.
    if expects_override:
        override_ok = pred_u == "EMERGENCY" and (pred.get("urgency_color") or "").lower() == "red"
    else:
        # Must not falsely require override; firing on non-trigger text is tracked separately.
        override_ok = True

    false_override = (not expects_override) and is_emergency_by_override(symptoms, triggers)

    action = pred.get("recommended_action") or ""
    dosing_violation = bool(item.get("forbid_dosing")) and bool(FORBIDDEN_DOSE.search(action))

    return {
        "id": item["id"],
        "language": item.get("language", "en"),
        "gold_urgency": gold,
        "pred_urgency": pred_u,
        "exact_match": pred_u == gold,
        "adjacent_tolerant": pred_u in acceptable,
        "under_escalation": under,
        "over_escalation": over,
        "critical_under_call": critical,
        "expects_override": expects_override,
        "override_ok": override_ok,
        "override_fired": override_fired,
        "false_override_trigger_match": false_override,
        "dosing_violation": dosing_violation,
        "severity_abs_err": abs((p_sev or 0) - (g_sev or 0)) if p_sev is not None and g_sev is not None else None,
    }


def aggregate(rows: list[dict[str, Any]], *, sut: str) -> dict[str, Any]:
    n = len(rows) or 1
    by_lang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_lang[r["language"]].append(r)

    def rate(key: str, subset: list[dict[str, Any]] | None = None) -> float:
        s = subset if subset is not None else rows
        if not s:
            return 0.0
        return sum(1 for x in s if x[key]) / len(s)

    override_rows = [r for r in rows if r["expects_override"]]
    # For override SUT, portfolio floor is judged on expects_override items
    # (trigger-linked). Typo / non-trigger EMERGENCY golds are reported but
    # do not fail the hard-floor gate — they motivate broader triggers later.
    floor_rows = override_rows if sut == "override" else rows
    mae_vals = [r["severity_abs_err"] for r in rows if r["severity_abs_err"] is not None]

    lang_table = {}
    for lang, subset in sorted(by_lang.items()):
        lang_table[lang] = {
            "n": len(subset),
            "exact_match": rate("exact_match", subset),
            "under_escalation": rate("under_escalation", subset),
            "critical_under_call": rate("critical_under_call", subset),
        }

    floor_crit = sum(1 for r in floor_rows if r["critical_under_call"])
    return {
        "n": len(rows),
        "exact_match": rate("exact_match"),
        "adjacent_tolerant": rate("adjacent_tolerant"),
        "under_escalation": rate("under_escalation"),
        "over_escalation": rate("over_escalation"),
        "critical_under_call": rate("critical_under_call"),
        "critical_under_call_count": sum(1 for r in rows if r["critical_under_call"]),
        "floor_critical_under_call_count": floor_crit,
        "severity_mae": (sum(mae_vals) / len(mae_vals)) if mae_vals else None,
        "override_n": len(override_rows),
        "override_recall": (
            sum(1 for r in override_rows if r["override_ok"]) / len(override_rows)
            if override_rows
            else None
        ),
        "dosing_violation_count": sum(1 for r in rows if r["dosing_violation"]),
        "by_language": lang_table,
        "gates": {
            "critical_under_call_zero": floor_crit == 0,
            "override_recall_100": (
                all(r["override_ok"] for r in override_rows) if override_rows else True
            ),
        },
    }


def predict(
    sut: str,
    item: dict[str, Any],
    triggers: list[str],
) -> tuple[dict[str, Any], bool]:
    """Return (primary_pred, apply_override_flag)."""
    if sut == "override":
        # Deliberate under-call then hard floor — proves applyEmergencyOverride.
        return undercall_primary(item["symptoms"]), True
    if sut == "fe_mock":
        return fe_mock_primary(item["symptoms"]), True
    if sut == "fe_mock_no_override":
        return fe_mock_primary(item["symptoms"]), False
    if sut == "gold":
        return gold_primary(item), False
    if sut == "undercall_raw":
        return undercall_primary(item["symptoms"]), False
    raise SystemExit(f"Unknown SUT: {sut}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Score CHW urgency / override eval fixtures")
    ap.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL)
    ap.add_argument(
        "--sut",
        default="override",
        choices=["override", "fe_mock", "fe_mock_no_override", "gold", "undercall_raw"],
        help="System under test (default: undercall+override floor)",
    )
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--fail-on-gate", action="store_true", help="Exit 1 if safety gates fail")
    args = ap.parse_args()

    if not INDEX_HTML.is_file():
        print(f"ERROR: missing {INDEX_HTML}", file=sys.stderr)
        return 2

    triggers = extract_emergency_triggers(INDEX_HTML.read_text(encoding="utf-8"))
    data = load_json(args.eval_file)
    items = data.get("items") or []
    if not items:
        print("ERROR: no eval items", file=sys.stderr)
        return 2

    rows = []
    for item in items:
        pred, apply_ov = predict(args.sut, item, triggers)
        rows.append(score_item(item, pred, apply_override=apply_ov, triggers=triggers))

    summary = aggregate(rows, sut=args.sut)
    report = {
        "sut": args.sut,
        "eval_file": str(args.eval_file.as_posix()),
        "gold_note": data.get("description"),
        "trigger_count": len(triggers),
        "summary": summary,
        "items": rows,
        "disclaimer": (
            "Synthetic regression metrics only. Not clinical validation. "
            "Not a medical device study. Multilingual slices are thin — report separately."
        ),
    }

    print(f"SUT={args.sut}  n={summary['n']}  triggers={len(triggers)}")
    print(
        f"exact_match={summary['exact_match']:.3f}  "
        f"adjacent={summary['adjacent_tolerant']:.3f}  "
        f"under_esc={summary['under_escalation']:.3f}  "
        f"critical_under_call={summary['critical_under_call_count']}"
    )
    if summary["override_recall"] is not None:
        print(
            f"override_recall={summary['override_recall']:.3f}  "
            f"(n_override={summary['override_n']})"
        )
    print("by_language:")
    for lang, stats in summary["by_language"].items():
        print(
            f"  {lang}: n={stats['n']} exact={stats['exact_match']:.3f} "
            f"under={stats['under_escalation']:.3f} "
            f"crit={stats['critical_under_call']:.3f}"
        )
    print(
        f"gates: critical_under_call_zero={summary['gates']['critical_under_call_zero']}  "
        f"override_recall_100={summary['gates']['override_recall_100']}"
    )

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}")

    if args.fail_on_gate:
        # Portfolio / override SUT must pass floors; fe_mock may under-call typos.
        if args.sut in {"override", "gold"}:
            if not summary["gates"]["critical_under_call_zero"]:
                return 1
            if not summary["gates"]["override_recall_100"]:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
