"""
Inline scenarios.json into app/index.html.

Run this after every scenarios.json update (post-curation) to keep the
<script type="application/json" id="cached-scenarios-data"> block in sync.

Usage:
    python inline_scenarios.py                 # uses default paths
    python inline_scenarios.py --dry-run       # prints diff, does not write

The inline block is required because browsers block fetch() on file:// origins.
Without inlining, the cache does not work when opening index.html directly.
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT_SCENARIOS = HERE / "app" / "scenarios.json"
DEFAULT_HTML      = HERE / "app" / "index.html"

OPEN_TAG  = '<script type="application/json" id="cached-scenarios-data">'
CLOSE_TAG = "</script>"


def load_and_strip(scenarios_path: Path) -> dict:
    data = json.loads(scenarios_path.read_text(encoding="utf-8"))
    clean_scenarios = []
    for sc in data.get("scenarios", []):
        sc = dict(sc)
        sc.pop("_meta", None)
        primary = dict(sc.get("primary_response", {}))
        primary.pop("_parse_failed", None)
        detail = dict(sc.get("detail_response", {}))
        detail.pop("_parse_failed", None)
        sc["primary_response"] = primary
        sc["detail_response"]  = detail
        clean_scenarios.append(sc)
    data["scenarios"] = clean_scenarios
    return data


def inline(scenarios_path: Path, html_path: Path, dry_run: bool = False) -> None:
    data   = load_and_strip(scenarios_path)
    html   = html_path.read_text(encoding="utf-8")
    blob   = json.dumps(data, indent=2, ensure_ascii=False)
    replacement = f"{OPEN_TAG}\n{blob}\n{CLOSE_TAG}"

    pattern = re.compile(
        re.escape(OPEN_TAG) + r".*?" + re.escape(CLOSE_TAG),
        re.DOTALL,
    )
    if not pattern.search(html):
        print("ERROR: could not find inline JSON block in index.html", file=sys.stderr)
        print(f"  Expected open tag:  {OPEN_TAG}", file=sys.stderr)
        sys.exit(1)

    new_html = pattern.sub(replacement, html, count=1)

    if dry_run:
        old_block = pattern.search(html).group()
        print("DRY RUN — would replace:")
        print(f"  OLD model_id: {_extract_model_id(old_block)}")
        print(f"  NEW model_id: {data.get('model_id', '?')}")
        print(f"  Scenarios: {len(data['scenarios'])}")
        print("No files written.")
        return

    html_path.write_text(new_html, encoding="utf-8")
    print(f"Updated {html_path}")
    print(f"  model_id:  {data.get('model_id', '?')}")
    print(f"  scenarios: {len(data['scenarios'])}")
    print(f"  version:   {data.get('version', '?')}")
    print(f"  generated: {data.get('generated_at', '?')}")
    if data.get("curated_at"):
        print(f"  curated:   {data['curated_at']}")
    else:
        print("  WARNING: curated_at is empty — run curation pass before submitting")


def _extract_model_id(block: str) -> str:
    m = re.search(r'"model_id"\s*:\s*"([^"]+)"', block)
    return m.group(1) if m else "unknown"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--html",      type=Path, default=DEFAULT_HTML)
    parser.add_argument("--dry-run",   action="store_true")
    args = parser.parse_args()

    if not args.scenarios.exists():
        print(f"ERROR: {args.scenarios} not found", file=sys.stderr)
        sys.exit(1)
    if not args.html.exists():
        print(f"ERROR: {args.html} not found", file=sys.stderr)
        sys.exit(1)

    inline(args.scenarios, args.html, dry_run=args.dry_run)
