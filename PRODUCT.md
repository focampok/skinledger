# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Adults (18+) tracking their own and their family's skincare on a phone, often in a bathroom with
imperfect light. Not dermatology patients; not tech-savvy by default. Judges of a hackathon will
see it in a 1-3 minute phone video.

## Product Purpose

SkinLedger answers one question per product: "Is it working, or should I stop rebuying it?"
Day 1 gives a baseline from 2 captures; each aspect gets a personal noise band; later check-ins
produce honest verdicts (Keep / No measurable change / Worse / Too early) that refuse to judge
what they cannot measure.

## Positioning

The decision threshold is the person's own measurement noise, not a population average or a
generic score. Two back-to-back day-1 captures set a per-aspect band; aspects noisier than 10
points are excluded from verdicts entirely, and the product says so. A neighboring skin-score
app could not truthfully copy the "we won't judge what we can't measure" stance without also
giving up its confident scores.

## Operating Context

- One selfie per analysis, taken with the guided camera (recommended for tracking) or uploaded
  from a shared link (quick try).
- A baseline is 2 captures minutes apart in the same place, same light, same distance.
- Product check-ins happen at day 14 and day 28.
- Access needs an invite code; visitors get 2 analyses; daily and total unit caps protect the
  YouCam budget.
- Photos are sent only to the YouCam API (Perfect Corp), held in memory and never stored by
  SkinLedger. Scores, result JSON without ui_score, and masks are stored.
- Consent is required before any analysis (18+ confirmation, consent version, timestamp), plus
  a per-analysis attestation that the face is the user's own and they are 18+.
- A public read-only sample profile ("Sample user (SIMULATED)") lets anyone browse the demo
  without an invite code. Nothing in it is a real person.

## Capabilities and Constraints

- YouCam AI Skin Analysis (SD): 15 numeric aspects plus skin type; raw_score is stored, ui_score
  is discarded at parse time and never shown.
- Every data point carries REAL / SIMULATED / SAMPLE and the UI shows it.
- Verdicts come only from per-aspect noise bands; unstable aspects are excluded.
- Deleting a person removes every row and mask file on disk.
- Fixed stack: Python 3.12 + uv, FastAPI, Jinja2, HTMX, Pico.css, Chart.js 4 (vendored), SQLite,
  no Node build, no React, no LLM and no other AI service.
- Product UI text is English. Cosmetic language only; the medical disclaimer is the single
  allowlisted exception.
- No feature currently promises medical advice, diagnosis, personal dosing, or brand
  recommendations.

## Brand Commitments

- Name: SkinLedger. Tagline: "Is it working or not? Know before you rebuy."
- Voice: calm, honest, trustworthy, warm. Cosmetic, never medical. Plain English. One action per
  screen.
- YouCam appears only as "Powered by YouCam API".
- No third-party product brands anywhere in the product copy.
- The mandatory disclaimer stays verbatim in the footer of every page and on the verdict screen.

## Evidence on Hand

- A seeded public sample profile with 7 SIMULATED captures, 15 per-aspect bands, 2 SAMPLE
  products, and two 14/28-day verdicts (Keep; No measurable change). This is the only demo
  history in the product; screenshots must use it or show no data.
- No real faces, testimonials, customer logos, benchmarks, press or launch metrics exist in the
  repository. Future work must not fabricate any of these.
- Screenshots rules live in `docs/screenshots.md`: no faces, no real person data, no brands,
  visible labels and disclaimer.

## Product Principles

1. **Honest before impressive.** A "too early" or "no measurable change" is a successful
   outcome; never invent confidence the measurement does not support.
2. **One decision per screen.** The user is in a bathroom with one hand free; each screen asks
   for one action or answers one question.
3. **The person is the benchmark.** Compare each person with their own noise, never with an
   average or another person.
4. **Privacy is visible, not buried.** "We never store your photo" is shown where the photo is
   handled, not only in a policy page.
5. **Label every data point.** REAL, SIMULATED and SAMPLE stay visible wherever their data
   appears.

## Accessibility & Inclusion

- Mobile-first at 390x844; WCAG AA contrast; touch targets at least 44px; body text readable at
  arm's length.
- Strict CSP: no inline scripts, no new external origins; fonts must be self-hosted or system.
- Charts must have text alternatives; a chart failure may not hide the underlying numbers.
- Users may be interrupted mid-flow (bathroom, family), so state must survive leaving and
  returning.
