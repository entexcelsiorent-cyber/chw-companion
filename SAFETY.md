# Safety Design

CHW Companion is a clinical decision-support tool, not a medical device, not a diagnostic system, and not a substitute for clinical judgement. The safety design follows from that posture: every layer is built to keep the human in charge of the decision and to fail in directions that escalate, not minimise.

## The boundary we are committed to

- The app **supports** a CHW's decision; it does not **replace** it.
- The app **never makes a definitive diagnosis**. Outputs are framed as triage decisions and recommended actions.
- The app **escalates when uncertain**. Conservatism beats false reassurance for this user.
- The app **always tells the worker when it can't help** (no signal + uncached case) rather than hallucinating a response.

The remainder of this document is the design choices that hold those commitments in place.

## Persistent safety disclaimer

A non-dismissible banner is rendered on every screen of the app:

> Decision support tool only. Not a diagnosis. Always use your clinical judgment. When uncertain, escalate urgency.

Design rules:

- **Cannot be hidden** by the user. There is no close button, no "don't show this again" toggle, no settings panel that disables it. This is intentional. A safety disclaimer that can be dismissed is a disclaimer the user has stopped reading.
- **Always in-frame** when a triage card is visible. On a 1080p browser at 110% zoom (the recording target for the demo video), the banner sits in the same view as the urgency verdict. The CHW sees the verdict and the disclaimer together, every time.
- **Plain language, short sentence.** No legalese. The wording was chosen so a CHW reading at second-language English speed can finish it before the urgency card has rendered.

Rationale: the worst failure mode for this kind of tool is a CHW treating it as authoritative — interpreting "URGENT, refer within 4 hours" as a medical instruction rather than a structured second opinion. The banner exists to prevent that habituation.

## Urgency tiering

Triage outputs use four tiers, mapped to a colour the CHW reads in under a second:

| Tier | Colour | Meaning |
|------|--------|---------|
| EMERGENCY | red | Life-threatening, refer NOW |
| URGENT | orange | Serious, refer within hours |
| ROUTINE | yellow | Needs treatment, can be today |
| MONITOR | green | Home care with instructions |

The mapping is conservative by design. Borderline cases between two tiers should land on the higher-urgency tier — the cost of an unnecessary referral is far smaller than the cost of a missed emergency. This is reflected both in the system prompt (`Be conservative — when uncertain, escalate urgency`) and in the cache curation pass (every scenario was reviewed for its tier; defaults skewed toward higher urgency).

The colour palette follows the WHO IMCI triage convention CHWs are already trained on, so the mapping is recognisable to anyone who has been through CHW training.

## Conservative-by-default urgency assignment

Four mechanisms keep urgency assignment biased toward escalation rather than reassurance, layered from soft to hard:

1. **Prompt-level conservatism.** The system prompts in `backend/server.py` instruct the model explicitly: *"Be conservative — when uncertain, escalate urgency. Never make a definitive diagnosis. Always support, never replace, clinical judgment."* This is the soft layer.
2. **Curated cache tiers.** The 20 cached scenarios were reviewed and their urgency tiers manually corrected. First-pass generation collapsed 14/20 scenarios to URGENT/red regardless of true severity; the curation pass set each scenario's tier to match its clinical severity. For canonical red-flag presentations (convulsion in an infant, postpartum haemorrhage, road-accident with unconsciousness, snake bite with systemic symptoms, pre-eclampsia signs), the cache encodes EMERGENCY directly.
3. **Mock-mode keyword fallback.** When the backend is unreachable or returns no parseable response, the frontend's `mockPrimary()` keyword check returns EMERGENCY/red on red-flag substrings. This guards the offline-degraded path.
4. **Render-layer EMERGENCY override** (deterministic, applied to *every* primary response before rendering — cache hit, live inference, or mock alike). For a defined trigger list, the urgency tier is forced to EMERGENCY/red **regardless of model output**. This is a hard override at the response-shaping layer (`applyEmergencyOverride()` in `app/index.html`), not a soft prompt instruction.

### Render-layer override triggers

The override fires on case-insensitive substring matches of any of the following in the CHW's symptom text. The list intentionally errs toward escalation:

- **Neurological:** `unconscious`, `unresponsive`, `not responding`, `convuls`, `seizure`, `fitting`, `altered consciousness`, `loss of consciousness`
- **Respiratory:** `not breathing`, `cannot breathe`, `severe difficulty breathing`, `gasping`, `turning blue`, `cyanosis`
- **Bleeding:** `severe bleeding`, `bleeding heavily`, `bleeding will not stop`, `haemorrhag*`, `hemorrhag*`, `postpartum bleeding`, `after delivery bleeding`
- **Cardiovascular:** `chest pain`, `crushing chest`
- **Obstetric:** `pregnant + convuls` (regex), `eclampsia`
- **Trauma:** `unconscious + accident` (regex), `snake + systemic|blurred|paralys` (regex)

When triggered, the override:
- Sets `urgency` to `EMERGENCY` and `urgency_color` to `red`
- Preserves the model's `recommended_action` if it is substantive (>20 characters), otherwise replaces it with a conservative referral instruction
- Tags the response with `_override_applied: true` for auditability

### Why hard-code rather than rely on the model

Open small models occasionally collapse to a wrong urgency tier — we observed exactly this in the first cache-generation pass, where the initial model mapped 14 of 20 scenarios to the same URGENT/red tier regardless of severity. A hard-coded floor on the most dangerous presentations means the worst-case model failure for those cases is "the model said routine, the app showed EMERGENCY anyway." That is the failure mode we want.

False-positive cost (an unnecessary referral on a borderline phrase) is far smaller than false-negative cost (a missed emergency). The trigger list is therefore deliberately broad. CHW Companion is decision *support* — a CHW reading the EMERGENCY card who concludes from clinical examination that the case is not truly urgent has the final word. The app does not block their judgement; it raises a floor.

## Cached responses are clinically curated

The 20 cached scenarios are not raw model output. The first generation pass produced clinically incorrect urgency tiers on most scenarios (10 should-be EMERGENCY collapsed to URGENT; all 20 were tagged red regardless of severity; 3 language tags were wrong). The checked-in offline cache remains tagged **`google/gemma-3-1b-it`** (curated). Optional later regen with Gemma 4 via `regen_scenarios_gemma4.py` is **not** applied to the in-repo cache. Each scenario was reviewed and corrected:

- Urgency tier set to match the clinical severity (not the model's collapsed default)
- Urgency colour aligned to tier (red/orange/yellow/green), not always red
- `recommended_action` checked for clinical appropriateness (e.g. "no tourniquet" for snake bite, "do not give aspirin to children" for pediatric fever)
- `language_detected` corrected (Hausa was tagged "Filipino" by the model)
- `trigger_keywords` curated so each set is literally substring-present in its own prompt and unique vs sibling scenarios (preventing false matches like "no oedema" matching the severe-malnutrition trigger "oedema")

Curation is a permanent part of the cache build pipeline, not a one-time fix. Any regeneration of `scenarios.json` requires the same review pass before shipping.

## Failure-mode handling

| Failure | What the user sees | Why this is safe |
|---------|--------------------|------------------|
| Model JSON parse fails | Mock response with conservative urgency, full safety banner | A predictable conservative answer beats a 500 error or blank screen |
| Network unavailable + cache miss | Clear message: "Inference unavailable. Try when signal returns." | Honest about the limitation rather than silently hallucinating |
| Network slow / partial response | Spinner with progress text; cancel button | The CHW knows the system is still working and can fall back to clinical judgement |
| Backend unreachable + red-flag keywords in input | Mock-mode EMERGENCY/red card from `mockPrimary()` keyword check | Offline-degraded path still escalates the most dangerous presentations |
| Model returns non-EMERGENCY tier for a red-flag presentation | Render-layer override forces EMERGENCY/red regardless of model output | The model cannot downgrade an emergency presentation past the override |
| Model returns a contradiction (low confidence + EMERGENCY) | Display both — confidence shown alongside urgency | The CHW sees the uncertainty and weighs it |

We do not show error stack traces, JSON dumps, or server messages to the user. Every failure path resolves to either a structured triage card or a clean failure message.

## What we explicitly do NOT do

- We do not send patient data to an analytics or telemetry pipeline, and the Flask backend does not implement durable symptom logging. The on-device triage queue **does** persist age, sex, and free-text symptoms in browser `localStorage` (`chw_queue_v1` in `app/index.html`) until the CHW clears the queue — it is **not** wiped on reload. Shared-phone deployments must treat the queue as sensitive. See `docs/SAFETY_AND_COMPLIANCE.md`.
- We do not claim regulatory clearance. CHW Companion has no FDA, EMA, or WHO pre-qualification. The path to that clearance is the impact pathway in `README.md`.
- We do not rank patients on demographics. The triage queue ranks on urgency tier only. There is no age-weighting, no sex-weighting, no socioeconomic input.
- We do not auto-translate the disclaimer. The English disclaimer is the disclaimer. Localising it requires translation review by clinicians fluent in the target language and is part of a future pilot, not this prototype.
- We do not propose specific drug doses. The recommended-action field is a triage decision (refer, monitor, treat per protocol), not a prescription.

## Why Gemma 4 and why this architecture

Gemma 4 (E4B, or the text-only E2B variant for lower latency) is the production model. A frontier API model would produce richer prose. We use Gemma 4 because:

- **It runs on infrastructure CHW programmes can actually afford.** Kaggle's free T4 tier was the production path during the 2026 Gemma 4 Good Hackathon build. A pilot deployment can stand up an equivalent tier on $50–200/month of cloud GPU; a frontier API costs orders of magnitude more per query.
- **Open weights are non-negotiable for this use case.** Cached scenarios can be pre-generated once and shipped as static JSON only because the weights are open. A closed API cannot produce an offline cache.
- **Gemma 4’s broad language support is helpful for online novel cases**, but this prototype’s **measured offline coverage** is the curated EN/SW/FR/HA cache — not clinical parity across marketed “35+” / “140+” counts.
- **Cache + Gemma 4 > Gemma 4 alone for this user.** The 20-scenario cache covers the most common cases at zero latency and zero cost. Smaller failure surface because deterministic cache responses are auditable in a way live inference is not.

## Auditability

Every layer of the app is auditable in plain text:

- `app/index.html` — entire client, single file, no build
- `app/scenarios.json` — every cached response, including trigger keywords
- `backend/server.py` — entire backend, single file
- `SAFETY.md` — this document

A pilot partner, a clinical reviewer, or a regulator can read the whole stack in an afternoon. That is intentional, and it is the floor for any future regulated deployment.
