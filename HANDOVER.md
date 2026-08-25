# HANDOVER — chw-companion · lane owner: **Cursor**

**Last updated: 2026-08-22 by Cursor**
**Read `../HANDOVER.md` first.** Especially the git safety notice — never run
`git clean`, `git checkout .`, or `git reset --hard` in this repo.

---

## Read this before you start: the purpose has changed

This was built for the **Gemma 4 Good Hackathon, which closed 2026-05-18**. It was
submitted; the outcome is unknown. **Do not treat anything here as pre-deadline
work.** There is no submission to prepare and no judge to impress.

The remaining value is as a **public portfolio asset**: a standalone repo with a
live demo, demonstrating an offline-capable clinical triage PWA on Gemma 4. That
matters because the agreed objective across the whole repo is capability and
public portfolio, not prize money (`../OMEGA_FINAL_BRIEF.md` §2).

The extraction runbook's Step 4 says "use the URL as your hackathon submission
link." **That step is void.** Everything before it still applies.

---

## What this is

Offline-first PWA for community health workers doing symptom triage, plus a Flask
backend wrapping Gemma 4.

```
app/index.html          Single-file PWA, no build step. Open directly.
app/scenarios.json      Cached scenarios, inlined into index.html for offline use.
backend/server.py       Flask on :5000 — /triage and /health
backend/requirements.txt Flask + Gemma inference pins (torch, transformers, accelerate)
test_gemma4_hardware*.py Kaggle GPU validation scripts (3 variants)
kaggle_inference_server.py, inline_scenarios.py, regen_scenarios_gemma4.py
PROJECT.md, ARCHITECTURE.md, README.md, SAFETY.md, SUBMISSION.md, VIDEO_SCRIPT.md
LICENSE                 Apache 2.0
.github/workflows/pages.yml, test.yml
```

Run frontend: `start app/index.html` from this directory (Windows). Works offline
against cached scenarios; live inference needs `window.CHW_BACKEND` set in the
browser console.

Run backend: `pip install -r backend/requirements.txt && python backend/server.py`

**Hardware validation result (already established, don't redo):** 4.74s warm
inference on Kaggle T4 = PASS against the <5s gate. Local Windows torch was
blocked at the time; the 12GB local GPU may now change that, but this is not on
any critical path.

---

## Session 2026-08-18 — what changed

Docs now read as a **standalone project root** (no `chw-companion/` prefixes in
run commands, no `omega_platform` / `kaggle_platform` / `results/` pointers in
the project docs). `SUBMISSION.md` is a post-hackathon project narrative: the
hackathon placement is explicitly unknown and not claimed.

`pages.yml` paths (`app/index.html`, `app/scenarios.json`) and the inline-JSON
assertion are correct **for the extracted layout**. Local check: 20 scenarios
inlined, `model_id=google/gemma-3-1b-it`. Keyword self-match and index.html
safety markers (`applyEmergencyOverride`) re-checked 2026-08-18 — OK.

**Gemma 4 cache regen was skipped.** `regen_scenarios_gemma4.py` is a Kaggle T4
inference job: it loads a 4–15 GB Gemma 4 checkpoint, generates 20 scenarios,
then needs manual curation before replacing `app/scenarios.json` and re-running
`inline_scenarios.py`. Local `HF_TOKEN` is unset. That is a long GPU run, not a
short hygiene check. Cache remains `google/gemma-3-1b-it` (2026-04-28, curated).
Do it later on Kaggle T4 + Internet + `HF_TOKEN` if the standalone repo should
ship a same-family cache.

**Not committed.** Root `HANDOVER.md` and the user git rule both say commit only
when asked, and only this lane. The working tree has the doc/path fixes; Sean
commits `chw-companion/**` (never `git add -A`).

**Subtree split was not re-run.** `git subtree split` only sees committed files.
Local branch `chw-companion-extracted` is still `34a1ae4` (runbook-era). Re-run
after the commit:

```bash
git branch -D chw-companion-extracted
git subtree split --prefix=chw-companion -b chw-companion-extracted
```

Then verify against
`docs/superpowers/runbooks/2026-04-30-chw-companion-standalone-extraction.md`
§"Verification of the extracted branch". Expected file count will be higher than
the runbook's 14 — untracked-at-the-time files (`pages.yml`, `VIDEO_SCRIPT.md`,
`inline_scenarios.py`, `kaggle_inference_server.py`, `regen_scenarios_gemma4.py`)
are now in the tree and should appear after they are committed.

---

## Claims in the previous HANDOVER that were wrong

1. **`backend/requirements.txt` is not Flask-only.** It already pins
   `transformers`, `torch`, `accelerate`, `sentencepiece`, `protobuf`. The
   "Gemma deps live only in the repo-root `requirements.txt`" gotcha is stale.
   A standalone repo can install from `backend/requirements.txt` as written.
2. **"Checked and clean: no stale forward-looking hackathon references"** was
   stale on 2026-08-12. README still had `chw-companion/` prefixes, "Win or
   place" as impact step 1, and `SUBMISSION.md` was still a submission packet.
   That is what this session fixed.
3. **The cache is not a Gemma 4 cache.** `app/scenarios.json` is
   `google/gemma-3-1b-it`, generated 2026-04-28, then curated. Live inference is
   Gemma 4. `regen_scenarios_gemma4.py` is the rebuild path; it has not been
   checked in as a new `scenarios.json`. Docs now say this explicitly.

---

## Session 2026-08-22 — what changed

Local hygiene only. `test.yml` now asserts that `app/scenarios.json` is inlined into
`index.html` (same check `pages.yml` already ran, plus count/`model_id` match against
disk). README no longer links a fake `github.io` Pages URL. Gemma 4 cache regen still
skipped. Subtree split / GitHub publish still blocked on Sean.

## Remaining — blocked on Sean

Creating the GitHub repo and pushing are outward-facing. **Sean's hands only:**

- Commit `chw-companion/**` (this session's working tree)
- Re-run the subtree split
- Create the empty public GitHub repo
- `git push chw chw-companion-extracted:main`
- Enable GitHub Pages

Prepare everything up to that line, then stop.

Optional later (not blocking extraction): regenerate `scenarios.json` on Gemma 4
via `regen_scenarios_gemma4.py` (Kaggle T4 + `HF_TOKEN`) and re-run
`inline_scenarios.py`. Skipped 2026-08-18 — see session note.

---

## Authority

**`docs/superpowers/runbooks/2026-04-30-chw-companion-standalone-extraction.md`**
is the authority on extraction mechanics — including its Anti-patterns and
Rollback sections. Do not invent an alternative extraction approach.

---

## Gotchas

- **Subtree split rewrites history**, so syncing the standalone repo later needs a
  force-push. The runbook covers this in §Maintenance.
- **`app/index.html` is a single file with scenarios inlined.** If you edit
  `app/scenarios.json` you must re-run `inline_scenarios.py` or the offline path
  silently serves stale data.
- **No build step. Do not add one.** The zero-dependency single-file design is the
  point — it's what makes it work offline on a low-end device.
- Line endings: git warns LF→CRLF on these files. Harmless, but don't "fix" it by
  reformatting whole files — it destroys reviewable diffs.
