# Publish — GitHub Pages demo (Phase 1)

**Goal:** Public clickable PWA demo of the **cache-first offline** triage UX.  
**Not required:** live Gemma, weight downloads, or on-device generative SLM.

**Status (2026-09-14 publish):** Live Pages URL: https://entexcelsiorent-cyber.github.io/chw-companion/  
Repo: https://github.com/entexcelsiorent-cyber/chw-companion (GitHub Actions Pages). Eval gates previously green (override + fe_mock).

---

## What the demo proves

| Path | Works on Pages? | Notes |
|------|-----------------|-------|
| Sample chips + curated cache | Yes | Inlined `scenarios.json`; works offline after first load (service worker) |
| Emergency override floor | Yes | Client-side in `index.html` |
| Safety disclaimer banner | Yes | Always visible |
| Live Gemma 4 inference | No (unless you set backend) | Optional: set `window.CHW_BACKEND` in console after starting Kaggle/Flask |

Portfolio story: **installable PWA + offline curated CDS**, not “Gemma on the phone.”

---

## In-repo readiness (automatable — done 2026-09-14)

| Check | Result |
|-------|--------|
| `app/` PWA shell (`index.html`, `sw.js`, `manifest.webmanifest`, `icon.svg`, `scenarios.json`) | Present |
| Scenarios inlined in `index.html` (`cached-scenarios-data`) | **20** scenarios, `model_id=google/gemma-3-1b-it` |
| Emergency override + decision-support banner markers | Present |
| `.github/workflows/pages.yml` + `test.yml` | Present (paths assume **repo root** = this tree) |
| README “Live demo” | Honest — **no invented github.io URL** |
| Eval: `python eval/score_urgency.py --sut override --fail-on-gate` | **PASS** |
| Eval: `python eval/score_urgency.py --sut fe_mock --fail-on-gate` | **PASS** |
| Public GitHub repo named for CHW Companion | **https://github.com/entexcelsiorent-cyber/chw-companion** |
| Nested under `MLOmega/MLOmega/chw-companion` | Source tree yes; **extracted** standalone repo is live |
| Live demo URL | **https://entexcelsiorent-cyber.github.io/chw-companion/** |

---

## Prerequisites (human / GitHub)

1. Standalone public repo with this tree at **repository root** (`app/`, `backend/`, `.github/workflows/`).
2. Apache 2.0 `LICENSE` visible (already in tree).
3. GitHub Actions enabled.

If this folder still lives under a monorepo, Pages will **not** pick up nested workflows until you subtree-split / extract (see `HANDOVER.md`).

---

## Exact publish steps (human — do not force-push)

`gh` is authenticated locally as `entexcelsiorent-cyber`, but **no commit/push was performed** in the 2026-09-14 ops pass (prefer explicit human publish).

```bash
# From MLOmega repo root (after committing chw-companion/** if needed)
cd c:\Repos\MLOmega\MLOmega

# 1) Commit only chw-companion paths when you are ready (optional if already committed)
# git add chw-companion/
# git commit -m "chw-companion: PWA Pages-ready assets and docs"

# 2) Subtree-split to a branch with app/ at root
git branch -D chw-companion-extracted 2>nul
git subtree split --prefix=chw-companion -b chw-companion-extracted

# 3) Create empty public repo (once)
gh repo create chw-companion --public --description "CHW Companion — cache-first triage PWA" --confirm

# 4) Push extracted branch as main (first push only; never --force unless you intend history rewrite)
git push -u https://github.com/entexcelsiorent-cyber/chw-companion.git chw-companion-extracted:main

# 5) Repo → Settings → Pages → Source: GitHub Actions
# 6) Actions → Deploy to GitHub Pages → confirm success
# 7) Copy the real Pages URL into README “Live demo” (do not invent a URL before it exists)
```

Alternate if the split branch already exists and files were previously untracked: commit first, then re-run subtree split (untracked files are invisible to `git subtree split`).

---

## Blockers (in-repo vs human)

| Blocker | Owner | Status 2026-09-14 |
|---------|--------|-------------------|
| Nested monorepo (workflow not at GitHub root) | Human extract / subtree-split | **Done** (extracted to standalone repo) |
| No public `chw-companion` GitHub repo | Human `gh repo create` | **Done** |
| Pages source not set to Actions | Human GitHub Settings | **Done** (`build_type=workflow`) |
| Fake `github.io` URL in README | Fixed — README must not invent a URL until Pages exists | **Live URL pasted** |
| Cache tagged `gemma-3-1b-it` while live is Gemma 4 | Documented honesty; optional later regen on Kaggle | OK |
| Commit of local chw-companion changes | Human (ops pass did not commit) | **Done** for Pages publish |

---

## Local demo (no Pages)

```bash
python -m http.server 8765 --directory app
# open http://127.0.0.1:8765/
```

`file://` still works for inlined cache (no service worker on most browsers for `file://`).

---

## After publish

- Paste the real Pages URL into README “Live demo” and portfolio one-pager.
- Record video per `VIDEO_SCRIPT.md` against that URL.
- Do **not** claim clinical validation or medical-device status.
