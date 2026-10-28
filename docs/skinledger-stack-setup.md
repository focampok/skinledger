# SkinLedger: stack, accounts and setup guide

*Written Monday 26 Oct 2026, ~20:10 GT (Guatemala time, UTC−6); rewritten in English and updated ~20:30 GT with Francisco's photo-handling decision (production upload path, original photos never stored, invite code and unit caps). Format decided today: **responsive web app + installable PWA over HTTPS**. Includes today's progress (YouCam account created, 1,000 units redeemed) and the official `/develop/` docs re-read today. Decisions of 26 Oct ~20:12 GT applied: folder and repo confirmed, 18+ only, polling only, `v2.0`, floor 3.0, no `/admin/backup`, no landing page. Nothing was installed on your computer, no accounts or keys were created and no project code was written.*

Companion to `skinledger-plan.md` (scope, schedule, kill switch) and `skinledger-prompts.md` (rules for the coding agents and ordered prompts). **[verified 26 Oct]** = read today in the official docs; **[unverified]** = confirm during the build; **[confirm]** = your decision.

---

## Part 1. Stack (with reasons)

Criteria: fits in ~16 h, few moving parts, no frontend build, the Camera Kit needs HTTPS, and everything is MIT-compatible.

| Piece | Choice | Why | Rejected |
|---|---|---|---|
| Language and environment | **Python 3.12 + uv** (`uv.lock`) | Same pattern as SowProof; the lock keeps your laptop and Railway identical. | pip + venv without a lock. |
| Backend | **FastAPI + Uvicorn + Jinja2 + pydantic-settings** | Async for polling and mask downloads; server-side templates. | Next.js: more pieces and a build. |
| Interaction | **HTMX** (pinned file in `static/vendor/`) | Forms and fragments without writing an SPA. Analysis status via `hx-trigger="every 3s"`. | React. |
| Styles | **Pico.css** (classless, in `static/vendor/`) + a short `app.css` | Looks decent without design work and works well on a phone. | Tailwind (build). |
| Charts | **Chart.js 4** (in `static/vendor/`) | One line per aspect + shaded noise band with a `fill` dataset. | D3. |
| Capture | **YouCam JS Camera Kit v2.5 from the CDN**: `https://plugins-media.makeupar.com/v2.5-camera-kit/sdk.js` | Guided capture (light, pose, distance) in the browser. Global `YMK`, `window.YMKAsyncInit`, `<div id="YMK-module">`, event `faceDetectionCaptured` **[verified 26 Oct]**. Per the docs it needs no key in the browser. Recommended for weekly tracking. | Our own `getUserMedia` (no quality control). |
| Photo upload | **Plain `<input type="file" accept="image/jpeg,image/png">`**, sent as the raw request body with `fetch` | The quick "try it" path for people opening the shared link. Raw body (not multipart) so the server never spools the image to a temp file. | Multipart `UploadFile` (Starlette spools files > 1 MB to disk). |
| API client | **httpx (async)** in a single module `youcam.py` | Simple REST with Bearer. Tests with `respx` or `httpx.MockTransport`. | Third-party SDK. |
| Database | **SQLite** (stdlib `sqlite3`, WAL mode) on the `/data` volume | Small scale; zero cost; one file. | Railway Postgres (another service). |
| Files | **Masks only** in `/data/masks/<person_id>/<capture_id>/`. **The original photo is never stored** — no photo files, no R2/S3, no temp files | The photo lives in memory during the request and is discarded after the signed PUT to YouCam. Masks are deleted with the person. Never in the repo. | R2/S3 or a photo folder (decided 26 Oct: nothing to protect if nothing is kept). |
| Background work | `asyncio.create_task` in-process + `captures.status` row | Upload and task creation happen **inside the request** (bytes never outlive it); the background job only polls and downloads masks. On restart, a "resume" retakes pending `task_id`s (valid 30 days per `/develop/file_retention_period`). | Celery/Redis. |
| PWA | `manifest.webmanifest` + 192/512 icons + `sw.js` caching only the static shell | Installable on Android/Chrome; on iOS, "Add to Home Screen". The SW **never** caches images, masks or `/api` responses. | APK. |
| LLM | **None** | Rules are fixed; also, §3.6 forbids sending Camera Kit photos to another AI (we apply it to uploads too). | — |
| Tests | **pytest + ruff** (+ `respx`) | Client, verdict, band, rules, guards, no-photo-on-disk and copy audit. | — |
| Webhooks | **No (decided 26 Oct)**: polling only. The docs offer webhooks (Standard Webhooks, HMAC-SHA256, `whsec_…` secret, set in the console) | Polling is enough at this scale and exposes no extra public endpoint. | — |
| Hosting | **Railway** (Dockerfile) + **volume** at `/data` + domain `skinledger.focampo.com` (CNAME in Cloudflare, DNS only) | Your ClinicKeep/TwinVerdict pattern; automatic HTTPS. | Own VPS. |
| Licence | **MIT** | Public repo with a licence is required. HTMX (0BSD), Chart.js (MIT), Pico (MIT), FastAPI (MIT). | GPL. |

### 1.1 Repo layout
```
skinledger/
  AGENTS.md  CLAUDE.md  .cursor/rules/  .roo/rules/  .claude/settings.json  .cursorignore  .rooignore
  LICENSE  README.md  pyproject.toml  uv.lock  .gitignore  .env.example  Dockerfile  railway.json
  docs/ (skinledger-plan.md, skinledger-stack-setup.md, skinledger-prompts.md, video-script.md, devpost.md)
  src/skinledger/
    config.py  db.py  schema.sql  models.py
    youcam.py          # 4-step client (the only place that knows the key)
    imaging.py         # in-memory validation + EXIF strip (Pillow), never writes to disk
    pipeline.py        # bytes in memory → YouCam → store raw_score + masks (job polls)
    guards.py          # invite code, attestation, per-person cap, daily/total unit caps
    aspects.py         # the 16 SD aspects, English labels
    noise.py  verdict.py  routine.py  shopping.py  usage.py  seed.py  copy_audit.py
    web/app.py  web/routes/{persons,captures,products,timeline,routine,admin,try_}.py
    web/templates/{base.html, ...}
    web/static/{app.css, capture.js, charts.js, sw.js, manifest.webmanifest, icons/, vendor/}
  tests/ (fixtures/sd_result_SAMPLE.json, test_youcam.py, test_guards.py, test_no_photo_persisted.py, test_noise.py, test_verdict.py, ...)
  data/   # local, in .gitignore (on Railway it is the /data volume): skinledger.sqlite + masks/ only
```

## Part 2. Accounts
| Account | Status | What to do |
|---|---|---|
| **Devpost** | ✔ Registered (26 Oct) | — |
| **YouCam API console** https://yce.perfectcorp.com/ai-api | ✔ Account created (26 Oct) | — |
| **Code redemption** | ✔ Redeemed (26 Oct): 1,000 units | Expire ~**24 Jan 2027** (90 days from redemption). |
| **API key** | **Pending (the only step left)** | See step 2.1. |
| **GitHub** (`focampok`) | You have it | Public repo `focampok/skinledger`, MIT ✔ (confirmed 26 Oct). |
| **Railway** | You have it (paid account) | New project `skinledger` on Thu 29 or Sat 31. |
| **Cloudflare** (zone `focampo.com`) | You have it | Confirm `skinledger` doesn't exist yet. |
| **YouTube** | Minor note: choose the account (not blocking) | Unlisted or public video, 1–3 min. |

### 2.1 Create the API key and store it as an environment variable (Wed 28, first thing)
1. Open the key console: https://yce.makeupar.com/api-console/en/api-keys/ (the docs also link it under `yce.perfectcorp.com/api-console/en/api-keys/`). **API Key** tab → create a new key named `skinledger`.
2. **The key is shown only once** (official FAQ). Copy it straight into `~/Proyectos/skinledger/.env` (`YOUCAM_API_KEY=…`, no quotes, no `< >`) and later into Railway → Variables. Don't paste it into any chat, assistant, issue or screenshot.
3. Check it works **without spending units** using the balance query (endpoint from the official `YouCam-API/skills` repo, not documented under `/develop/`):
   ```bash
   cd ~/Proyectos/skinledger && set -a && . ./.env && set +a
   curl -s -H "Authorization: Bearer $YOUCAM_API_KEY" https://yce-api-01.makeupar.com/s2s/v1.0/client/credit | python3 -m json.tool
   unset YOUCAM_API_KEY
   ```
   You should see `results` with amounts adding up to ~1,000. If it returns `401 InvalidAccessToken`, check the key is complete and prefixed with `Bearer `.
4. If the key leaks: revoke it in the same console and create another.

## Part 3. Environment variables
`.env.example` (in the repo, no real values):
```dotenv
YOUCAM_API_KEY=                   # server only; never to the browser or logs
YOUCAM_BASE_URL=https://yce-api-01.makeupar.com
YOUCAM_SKIN_VERSION=v2.0          # decided; v2.1 exists (official skills repo) but is not used
YOUCAM_MOCK=true                  # true = uses tests/fixtures/sd_result_SAMPLE.json, 0 units
YOUCAM_POLL_INTERVAL_S=5
YOUCAM_POLL_TIMEOUT_S=180
DATA_DIR=./data                   # on Railway: /data (the volume). Holds the SQLite file and masks/ only
PUBLIC_URL=http://localhost:8000
INVITE_CODE=                      # required to run a real analysis from the shared link; empty = analysis closed to visitors
ADMIN_TOKEN=                      # for /admin/usage, the seed and your own uncapped analyses; long and random
MAX_REAL_ANALYSES_PER_PERSON=2    # matches the day-1 noise-band pair
DAILY_UNIT_CAP=96                 # visitor units per GT day (96 = 6 analyses)
TOTAL_UNIT_CAP=480                # hard cap on all visitor units since deploy (480 = 30 analyses)
UNITS_PER_ANALYSIS=16             # SD, 16 aspects [verified 26 Oct]
ALLOW_UPLOAD=true                 # photo upload path in production (the quick try); Camera Kit is always on
STORE_MASKS=true                  # set false if the first real result shows masks contain the photo [unverified]
CAMERA_KIT_LANGUAGE=enu           # enu | esp
```
- On Railway: `YOUCAM_MOCK=false`, `DATA_DIR=/data`, `PUBLIC_URL=https://skinledger.focampo.com`, `ALLOW_UPLOAD=true`, plus `INVITE_CODE` and the caps.
- Generate `ADMIN_TOKEN` in your terminal: `python3 -c "import secrets;print(secrets.token_urlsafe(24))"`. `INVITE_CODE` should be short and easy to type (e.g. two words + a number) because you'll send it to friends and put it in Devpost.
- **Changing a cap or rotating `INVITE_CODE`** = edit the variable in Railway (it redeploys); data is kept on the volume.

## Part 4. Local setup (Linux Mint)
### Step 1. Tools (you should already have them)
```bash
git --version && uv --version && gh --version
uv python install 3.12
```
### Step 2. Folder and repo (Wed 28; path confirmed)
```bash
mkdir -p ~/Proyectos/skinledger && cd ~/Proyectos/skinledger
git init -b main
mkdir -p docs && cp <path-to-the-3-md-files>/skinledger-*.md docs/
# LICENSE (MIT) and AGENTS.md are created in P00; after the first commit:
gh repo create focampok/skinledger --public --source . --push
```
### Step 3. Key in `.env` without pasting it into any chat (see 2.1)
```bash
cp .env.example .env && chmod 600 .env
${EDITOR:-nano} .env      # paste YOUCAM_API_KEY by hand; keep YOUCAM_MOCK=true until the smoke test
git check-ignore .env     # must print .env
```
### Step 4. Run
```bash
uv sync
uv run uvicorn skinledger.web.app:app --reload --port 8000
uv run ruff check . && uv run pytest -q
```
On the laptop, `http://localhost:8000` works for the Camera Kit with the webcam (the docs say localhost doesn't need HTTPS **[verified 26 Oct]**).

## Part 5. HTTPS for testing on the phone (Thu 29)
The phone can't see your `localhost`, and without HTTPS the browser won't open the camera. Use a temporary tunnel:
```bash
# install cloudflared (once): https://github.com/cloudflare/cloudflared/releases (amd64 .deb package)
sudo dpkg -i cloudflared-linux-amd64.deb
cloudflared tunnel --url http://localhost:8000     # prints https://<something>.trycloudflare.com
```
- Open that URL on the phone. **Close the tunnel when done** (Ctrl+C): while it's open, anyone with the URL sees your local app.
- While the tunnel is open, keep `INVITE_CODE` set (and the caps) so nobody can spend units.
- Alternative: deploy to Railway right away (Part 6) and test there.
- **[unverified]** whether the Camera Kit restricts domains. The docs don't say; if it fails over the tunnel but not on localhost, check the browser console and try on Railway.

## Part 6. Railway
1. **New project** → Deploy from GitHub repo → `focampok/skinledger`. Railway detects the `Dockerfile`.
2. **Volume:** on the service → *Volumes* → **Add volume**, mount path **`/data`**. SQLite and `masks/` live there (no photos). Without a volume, every redeploy wipes the data.
3. **Variables:** those from Part 3 with production values. Paste the key directly in the panel.
4. **Start command** (from the Dockerfile): `uvicorn skinledger.web.app:app --host 0.0.0.0 --port ${PORT}`.
5. **Healthcheck:** path `/healthz` (in `railway.json`).
6. **Test redeploy** on Saturday: create a SAMPLE profile, redeploy, confirm it's still there.
7. **No backup endpoint (decided 26 Oct).** If you want a copy before recording the video, use `railway ssh` / `railway run` **[unverified: availability on your plan]**; not required.
8. **Photo check on the volume** (Saturday, after a real analysis): `railway ssh` then `find /data -type f ! -path '/data/masks/*' ! -name 'skinledger.sqlite*'` must print nothing **[unverified: `railway ssh` on your plan; otherwise use the `/admin/usage` file count from P15]**.

## Part 7. Domain `skinledger.focampo.com`
1. Railway → service → *Settings* → *Networking* → **Custom Domain** → `skinledger.focampo.com`. Railway shows the CNAME target (and, if needed, a TXT verification record **[unverified]**; add whatever it shows).
2. Cloudflare → DNS → **Add record**: `CNAME`, name `skinledger`, target from Railway, **DNS only (grey cloud)**. Same pattern as `clinickeep.focampo.com`.
3. Check:
   ```bash
   dig +short skinledger.focampo.com
   curl -sI https://skinledger.focampo.com/healthz | head -1     # HTTP/2 200
   ```

## Part 8. Shared-link and judge access (submission requirement)
- **The shared link** is `https://skinledger.focampo.com/try`. You send it with the `INVITE_CODE` to friends, coworkers and family; judges get it in Devpost.
- **No login to look around:** anyone can open the **"Sample user (SIMULATED)"** profile with its timeline, verdict and routine, spending no units.
- **To analyze their own face:** the visitor enters the invite code → creates a profile (display name only) → accepts consent (18+) → ticks **"This is my own face and I am 18 or older."** → chooses **Upload a photo** (quick try) or **Guided capture** (Camera Kit, recommended for tracking). The photo goes from memory to YouCam and is discarded; only scores and masks are kept.
- **Guards:** max `MAX_REAL_ANALYSES_PER_PERSON=2` real analyses per person (and per browser), `DAILY_UNIT_CAP` per GT day and the hard `TOTAL_UNIT_CAP`, all for visitors (your own analyses with `ADMIN_TOKEN` are exempt but counted). Rejected images (no face, several people, too dark) cost no units and show friendly messages. At a cap: *"Demo limit reached — thanks for trying SkinLedger! Explore the sample profile instead."*
- In Devpost, "Testing instructions": URL, invite code, "Use Chrome or Safari on a phone; allow camera access, or upload a well-lit front-facing selfie", "2 analyses per person", and that they can delete their profile when done.
- **Judges share the visitor pool with friends.** Before submitting, check `/admin/usage` and keep at least ~8 analyses (128 units) free; if needed, raise `TOTAL_UNIT_CAP` from the margin or rotate `INVITE_CODE` (the old one stops working; update Devpost).
- The app must stay up **until judging ends** (rules: 20 Nov 10:45 GT; Devpost calendar: 20 Nov 16:00 GT). Keep it **at least until winners are announced (~24 Nov)**. Leave Railway on and the key with units.
- **Only your face** in the video, repo and screenshots (plan §10). Visitors' data is visible only to their own browser.

## Part 9. Licence and credits
- `LICENSE` MIT with your name and 2026.
- README: "Powered by YouCam API (Perfect Corp)" as credit, no large logos. Credits for HTMX, Chart.js and Pico.
- No third-party branded assets; your own icons ("SL" letters on a flat colour, generated by a script, no faces).

## Part 10. Secrets hygiene
- The key lives only in `.env` (local, `chmod 600`, in `.gitignore`) and in Railway Variables. Never in code, README, logs, HTML or the browser. It is not shared (Terms §3.1).
- The assistants don't read `.env` (rules in `skinledger-prompts.md` Part A.3).
- `config.py` uses `SecretStr`; a test checks that `repr(settings)` doesn't show the key or `INVITE_CODE`/`ADMIN_TOKEN`, and that no template receives them.
- httpx logs don't print headers. Signed upload/download URLs are never logged in full (they are temporary credentials). Request bodies (photos) are never logged.
- Before every push: `git grep -nE "Bearer [A-Za-z0-9]|YOUCAM_API_KEY=.+"` must be empty.
- If the key leaks: revoke it in the console, create another and update Railway.
- After the hackathon, rotate the key if the repo or video showed anything sensitive.

## Now / later summary
| Step | When |
|---|---|
| YouCam account and redemption | ✔ done (Mon 26) |
| Railway and Cloudflare checked | **now** (Mon 26–Tue 27) |
| Create the API key (step 2.1), repo, P00–P03 | **Wed 28** |
| HTTPS tunnel and phone test (Camera Kit + upload) | **Thu 29** |
| Railway + volume + domain + invite code and caps | **Sat 31** (before 20:00) |
| Video, Devpost, submission | **Sun 1 Nov** before 21:00 GT |
