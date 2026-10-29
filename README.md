# SkinLedger

**Is it working or not? Know before you rebuy.**

SkinLedger is a responsive web app (installable PWA) that tells you, from your own measurements, whether a skincare product is really working, and only counts a change when it beats the noise of the measurement itself.

Demo: https://skinledger.focampo.com · Licence: MIT · Powered by YouCam API

## The problem
People wonder about their skin right before a purchase, and right when they are standing in front of a mirror deciding whether a product is working. The light changes, the mirror lies, and many beauty apps show deliberately encouraging scores. A tracker that confuses noise with progress misleads you.

## How it works
1. **Capture.** A guided capture with the YouCam JS Camera Kit (recommended for tracking, because it keeps light, distance and pose consistent), or a quick photo upload for a first try.
2. **Analysis.** The server runs the YouCam AI Skin Analysis API (V2, SD): 15 numeric skin scores plus skin type.
3. **Raw scores.** SkinLedger stores `raw_score` for each aspect, plus the analysis masks. The display score (`ui_score`) is discarded at parse time.
4. **Personal noise band.** Day 1 takes two captures. Per aspect, `band = max(|A − B|, 3.0)`. An aspect whose band is above 10 points is shown as "Unstable for your setup" and is excluded from verdicts.
5. **Verdict at day 14 and day 28.** Keep, No measurable change → reconsider before rebuying, or Worse → pause & consult. [PLANNED]
6. **AM/PM routine** from fixed aspect → ingredient-category rules, plus a generic shopping list (no brands). [PLANNED]

## Why it isn't a wrapper
- **It measures its own noise.** On day 1, two guided captures of the same face, three minutes apart under the same light, are compared. In one real day-1 pair (the author's own), pore moved by +17.3, acne +15.0, radiance -7.9, oiliness +7.5, firmness +6.7, droopy upper eyelid -6.2, tear trough -5.5 and droopy lower eyelid +5.2; the other aspects moved 3.5 points or less, and skin type was identical. This is one person's measurement, not a general accuracy claim. It is why SkinLedger tells you which metrics are reliable for you before it gives a verdict.
- **`raw_score`, not the display score.** The API documents the display score as adjusted to look more favourable. SkinLedger tracks only `raw_score`.
- **Honest outcomes.** "No measurable change" is a first-class result.
- **Masks stored immediately.** Result links are short-lived, so scores and masks are saved in the same job.
- **Photos are never stored** (details under Privacy).
- **Unit guards.** Invite code, per-person limit, daily cap and total cap protect the shared demo.
- **Real delete.** Deleting a person removes all rows and mask files.

## Architecture
```
 Browser (phone or laptop)
   ├─ YouCam JS Camera Kit v2.5 (guided capture, runs client-side)
   └─ HTMX pages + Chart.js (vendored)
        │  image as the raw request body (no multipart, no temp files)
        ▼
 FastAPI (Jinja, HTMX)         photo bytes live in memory only
   ├─► YouCam AI Skin Analysis API  (file → signed PUT → task → poll)
   │        ▲ photos go only to Perfect Corp, never to any other service
   └─► SQLite + /data/masks (volume): raw_score, result JSON without
        signed URLs, masks. No photo path exists in the schema.
```

## YouCam APIs used
- **YouCam AI Skin Analysis API, V2, SD** (15 numeric aspects with `raw_score`, plus skin type). The asynchronous 4-step flow: `POST /s2s/v2.0/file`, `PUT` the bytes to the signed URL, `POST /s2s/v2.0/task/skin-analysis`, then `GET /s2s/v2.0/task/skin-analysis/{task_id}` until `success` or `error`. The endpoint version is a variable.
- **YouCam JS Camera Kit v2.5**, loaded from the vendor CDN, in `skincare` mode with strict quality checks.

Powered by YouCam API.

## Try it
- Public sample profile, no code needed: https://skinledger.focampo.com/demo (shows a "Sample user (SIMULATED)" profile). [PLANNED]
- Analyze your own face: `/try`, using the invite code from the Devpost testing instructions. Tick "This is my own face and I am 18 or older." Use the guided camera or upload a well-lit, front-facing selfie. 2 analyses per person.

## Data labels
- **REAL**: real analyses of real captures.
- **SIMULATED**: generated scores for demo check-ins (no photos, no masks); badges, dashed lines and a banner mark them.
- **SAMPLE**: fixtures and example products, labelled SAMPLE.

Numbers in this README come from the app, not from invention.

## Privacy
Adults 18+ only. Every analysis requires ticking "This is my own face and I am 18 or older." SkinLedger never stores your photo: it is held in memory, sent to the YouCam API for analysis and discarded, with no disk and no object storage. We store only the scores (`raw_score`; the display score is discarded), the result JSON without signed URLs, and the masks. YouCam may keep uploaded files for up to 30 days. Photos are never sent to any other AI. Delete your profile at any time; that removes everything we store.

Shared-link guards: invite code, 2 analyses per person, daily and total unit caps set by environment variables.

## Run locally
```bash
uv sync
cp .env.example .env          # edit .env yourself; keep YOUCAM_MOCK=true for development
YOUCAM_MOCK=true uv run uvicorn skinledger.web.app:app --reload
uv run pytest
```
With `YOUCAM_MOCK=true` the app uses a fixture labelled SAMPLE and spends no API units. Camera Kit needs HTTPS except on `localhost`.

## Deploy (Railway)
Dockerfile build, a persistent volume mounted at `/data`, healthcheck `/healthz`, and the variables below set in Railway. The service listens on `$PORT`.

## Environment variables (names only)
`YOUCAM_API_KEY`, `YOUCAM_BASE_URL`, `YOUCAM_SKIN_VERSION`, `YOUCAM_MOCK`, `YOUCAM_POLL_INTERVAL_S`, `YOUCAM_POLL_TIMEOUT_S`, `DATA_DIR`, `PUBLIC_URL`, `INVITE_CODE`, `ADMIN_TOKEN`, `MAX_REAL_ANALYSES_PER_PERSON`, `DAILY_UNIT_CAP`, `TOTAL_UNIT_CAP`, `UNITS_PER_ANALYSIS`, `ALLOW_UPLOAD`, `STORE_MASKS`, `CAMERA_KIT_LANGUAGE`.
The API key is read only on the server and never reaches the browser, logs or templates.

## Honest limitations
- The two-capture noise band is a rough estimate of measurement noise, not a statistical guarantee.
- The 3.0-point floor is a product heuristic, not a YouCam figure.
- Lighting changes scores; uploads are less consistent than guided capture.
- Demo check-ins on day 14 and day 28 are SIMULATED; only day 1 is real.
- Not clinically validated. Skin scores are AI estimates.

## Disclaimer
Cosmetic skin insights, not a medical diagnosis. Scores are AI estimates and vary with lighting. See a dermatologist for persistent acne, changing moles, rashes or pain.

## Licence and credits
MIT. Built with HTMX, Chart.js and Pico CSS, each under its own licence (add the exact licence names and versions from the vendored files). Skin analysis and guided capture are powered by YouCam API.

