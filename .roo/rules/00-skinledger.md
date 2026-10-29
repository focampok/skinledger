# SkinLedger — project rules (mandatory for any assistant)

## What it is
Responsive web app + installable PWA for the YouCam API Skin AI hackathon (Devpost, deadline
Mon 2 Nov 2026 10:45 GT). Tagline: "Is it working or not? Know before you rebuy."
A person captures a guided selfie with the YouCam JS Camera Kit (recommended for tracking) or
uploads a photo (quick try from a shared link), the server runs YouCam AI Skin Analysis (SD,
15 numeric aspects plus skin type), stores raw_score per aspect, and after 14/28 days of using a skincare product
SkinLedger says Keep / No measurable change / Worse — only if the change beats that person's own
measurement noise band (2 captures on day 1).
Source docs: docs/skinledger-plan.md (scope, privacy §10, verdict engine §12, routine rules §13),
docs/skinledger-stack-setup.md (stack, env vars), docs/skinledger-prompts.md (steps).

## Fixed stack (do not change unless Francisco asks)
Python 3.12 + uv · FastAPI + Uvicorn + Jinja2 + pydantic-settings · HTMX · Pico.css · Chart.js 4
(vendored in web/static/vendor/) · SQLite (stdlib sqlite3, WAL) · httpx (async) · Pillow ·
pytest + respx + ruff. YouCam JS Camera Kit loaded ONLY from
https://plugins-media.makeupar.com/v2.5-camera-kit/sdk.js. Deploy: Railway (Dockerfile, volume /data),
https://skinledger.focampo.com. No Node build, no React, no LLM, no other AI service, no object storage.

## YouCam API facts (verified 26 Oct 2026 unless marked)
- Base https://yce-api-01.makeupar.com, header exactly `Authorization: Bearer <key>` (no angle brackets
  in the real header). 4 steps: POST /s2s/v2.0/file → PUT bytes to the signed URL with the returned
  headers → POST /s2s/v2.0/task/skin-analysis → GET /s2s/v2.0/task/skin-analysis/{task_id}.
- SD actions only (never mix with hd_*): wrinkle, droopy_upper_eyelid, droopy_lower_eyelid, firmness,
  acne, moisture, eye_bag, dark_circle_v2, age_spot, radiance, redness, oiliness, pore, texture,
  tear_trough, skin_type (16 actions = 15 numeric aspects plus skin type). 16 actions = 16 units.
  Errors do not consume units.
- Rate limit 250 requests / 300 s per IP and per token, ~5 QPS; 429 → back off and retry.
- file_id and task_id valid 30 days; result download URLs valid 2 h (re-GET the task to get fresh ones).
- [unverified] exact JSON shape of skin_type / all / skin_age with format=json, where the error
  code sits when task_status == "error", and whether mask images contain any of the face photo.
  Parse tolerantly, keep the raw JSON, never invent fields.
- IDs (file_id, task_id) are opaque strings. Never cast them to int.

## Hard rules
1. The API key lives only in env var YOUCAM_API_KEY (SecretStr). Never log it, print it, put it in
   a template, JS, test, fixture, commit or error message. Only src/skinledger/youcam.py reads it.
   The browser never talks to the YouCam REST API; only the Camera Kit SDK runs client-side.
2. Store raw_score only. ui_score is discarded at parse time and never stored, shown or charted.
3. Download result masks immediately in the same job (URLs expire in 2 h), unless STORE_MASKS=false.
4. NEVER PERSIST THE ORIGINAL PHOTO. Image bytes arrive as the raw request body (never multipart,
   which spools to temp files), stay in memory, are validated and EXIF-stripped in memory, sent to
   YouCam (file upload + signed PUT) inside the same request, then dropped. No photo on disk, in
   DATA_DIR, in a temp file, in object storage (no R2/S3), in the DB, in logs or in a cache.
   The schema has no photo path column. Only raw scores, the result JSON (no ui_score, no signed
   URLs) and masks are stored.
5. Photos (Camera Kit or upload) go ONLY to Perfect Corp's API (YouCam Terms §3.6). Never send
   them, or derived data, to any other AI/LLM/service.
6. Consent first: no analysis without a consent row for that person (18+ checkbox, consent text
   version, timestamp) AND, on every analysis request, the attestation checkbox "This is my own face
   and I am 18 or older." Deleting a person deletes all rows and mask files on disk.
7. Units guard: every real analysis from a visitor passes, in order: INVITE_CODE in session,
   attestation, MAX_REAL_ANALYSES_PER_PERSON (also per browser), DAILY_UNIT_CAP (per GT day) and
   TOTAL_UNIT_CAP. ADMIN_TOKEN requests are exempt from caps but still counted. Rejected images
   cost 0 units. Tests and assistants run with YOUCAM_MOCK=true.
8. Demo honesty: every data point carries data_label REAL | SIMULATED | SAMPLE and the UI shows it.
   Never generate fake photos or masks. SIMULATED points have scores only.
9. No medical language in product copy: never "diagnose", "treat", "cure", "disease", "prescription",
   "medication" (the disclaimer is the only allowlisted text). No third-party product brands.
   YouCam appears only as "Powered by YouCam API".
10. Mandatory disclaimer, exact text, footer of every page and on the verdict screen (constant
   DISCLAIMER in src/skinledger/copy.py):
   "Cosmetic skin insights, not a medical diagnosis. Scores are AI estimates and vary with lighting.
   See a dermatologist for persistent acne, changing moles, rashes or pain."
11. Product UI text is English. Code comments in English.
12. Bands come only from noise.py; unstable aspects (band > 10) are never used in verdicts.

## Way of working
- Do only the step you were given. Before editing, list the files you will touch and how you'll test.
- Every step ends with `uv run ruff check . && uv run pytest -q` green.
- Never read .env. Never run commands that print environment variables.
- Anything not in the docs above: mark it `# UNVERIFIED:` in code and tell Francisco.
