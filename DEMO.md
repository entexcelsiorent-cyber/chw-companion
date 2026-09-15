# CHW Companion — Demo recording guide (portfolio)

**Live URL:** https://entexcelsiorent-cyber.github.io/chw-companion/  
**Goal:** 60–90 s screen recording that proves **cache-first PWA triage**, not on-device Gemma.

Use this instead of archived `VIDEO_SCRIPT.md` (hackathon-era; overclaims Gemma-4 cache / 140 languages).

---

## Honesty checklist (say / show)

| Do say | Do not say |
|--------|------------|
| Decision support; not a medical device | FDA/WHO validated / diagnosis tool |
| Curated offline cache (gemma-3 tagged) | On-device Gemma / offline generative SLM |
| Emergency override floor | Clinically validated across 140 languages |
| Demo languages EN / SW / FR / HA | Measured clinical parity in every UI language |
| Live Gemma 4 optional (backend) | Live model required for the Pages demo |

---

## Shot list (≈75 s)

1. **Open live Pages** (5 s) — show safety banner + “CACHE-FIRST” badge + demo-story strip.
2. **Airplane mode** (optional, 5 s) — prove shell still works after first HTTPS load.
3. **Tap “Malaria · child”** (15 s) — instant primary urgency; detail fills; badge may flash **CACHED**.
4. **Tap “Mtoto · Swahili”** (15 s) — multilingual cache demo (not “140 languages”).
5. **Queue tab** (10 s) — ranked patients; mention localStorage + clear on shared phones.
6. **Close** (10 s) — “Cache for common cases; optional live Gemma when a GPU backend is set.”

---

## Recording tips

- Chrome DevTools → iPhone-width viewport, 1080p screen capture.
- Prefer the **live Pages URL** so SW/install story is real.
- Do not attach `window.CHW_BACKEND` unless you intentionally demo the live path.
- Keep the non-dismissible disclaimer visible in frame.

Eval (optional, before claiming override safety):  
`python eval/score_urgency.py --sut override --fail-on-gate`
