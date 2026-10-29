# Deploying SkinLedger to Railway

Target: `https://skinledger.focampo.com`, a Railway service built from this GitHub
repository with a persistent volume at `/data`. The app is Python 3.12 + uv;
the Dockerfile runs it as a non-root user.

## 1. Railway service

1. Railway → **New project** → **Deploy from GitHub repo** → `focampok/skinledger`.
2. Railway detects the `Dockerfile` and builds it. The start command is in the
   Dockerfile:
   `uvicorn skinledger.web.app:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*' --no-access-log`.
3. `railway.json` sets the healthcheck to `/healthz`.

## 2. Volume

Service → **Volumes** → **Add volume**, mount path **`/data`**. The SQLite file
and `masks/` live there. Photos are never written; without the volume every
redeploy wipes the data.

The image has no `USER` line and starts as root, but only long enough to fix
volume ownership. `scripts/entrypoint.sh` chowns `DATA_DIR` and `LOG_DIR` to uid
`10001`, then re-execs uvicorn as uid `10001` with
`setpriv --reuid=10001 --regid=10001 --init-groups`. The application process
therefore never runs as root, even when the container does.

Railway mounts the volume root-owned, so set the service variable
**`RAILWAY_RUN_UID=0`**: with it the entrypoint can chown the volume on every
boot, which is what makes `/data` writable for the SQLite file. Without the
variable the container starts as uid `10001` directly, the entrypoint execs
uvicorn as-is, and an empty root-owned volume fails with
`sqlite3.OperationalError: unable to open database file`.

Started as a non-root user, the entrypoint skips the chown and execs uvicorn
directly, so local `docker run --user 10001` still works.

HEAD requests are answered like GET (same status, same headers, same
`Content-Length`, empty body) by a middleware in `src/skinledger/web/app.py`, so
uptime monitors can probe `/healthz` with either method.

## 3. Variables (names only — set the values in Railway, never in the repo)

| Name | What it does |
|---|---|
| `YOUCAM_API_KEY` | Perfect Corp API key. Server only; never reaches the browser, logs or templates. |
| `YOUCAM_BASE_URL` | API base URL (default `https://yce-api-01.makeupar.com`). |
| `YOUCAM_SKIN_VERSION` | Skin Analysis version (`v2.0`). |
| `YOUCAM_MOCK` | Must be **false** in production; the app refuses to start otherwise. |
| `YOUCAM_POLL_INTERVAL_S` | Task polling interval in seconds. |
| `YOUCAM_POLL_TIMEOUT_S` | Task polling timeout in seconds. |
| `DATA_DIR` | `/data` (the mounted volume). |
| `LOG_DIR` | JSONL event log directory; keep it outside `DATA_DIR`. |
| `LOG_LEVEL` | Event log level (default `INFO`). |
| `PUBLIC_URL` | Public origin, `https://skinledger.focampo.com`. |
| `INVITE_CODE` | Shared-link invite code. Required in production. |
| `ADMIN_TOKEN` | Value for the `X-Admin-Token` header on `/admin/usage`. Required in production; header-only, no query parameter. |
| `MAX_REAL_ANALYSES_PER_PERSON` | Real analyses per visitor (2). |
| `DAILY_UNIT_CAP` | Visitor units per Guatemala day. |
| `TOTAL_UNIT_CAP` | Visitor units in total (the judges' pool). |
| `UNITS_PER_ANALYSIS` | Units one SD analysis costs (16). |
| `ALLOW_UPLOAD` | Whether the quick photo upload is offered. |
| `STORE_MASKS` | Whether result masks are stored on the volume. |
| `CAMERA_KIT_LANGUAGE` | Camera Kit language (`enu`). |
| `SEED_SAMPLE_ON_START` | `true` creates the public sample profile on boot if missing (idempotent); default `false`. |
| `RAILWAY_ENVIRONMENT` | Set by Railway. When present the app refuses to start if `YOUCAM_MOCK` is true or `INVITE_CODE`/`ADMIN_TOKEN` is empty. |
| `RAILWAY_RUN_UID` | `0`. Starts the container as root so `scripts/entrypoint.sh` can chown the volume; the entrypoint then drops to uid `10001` before running uvicorn. |
| `CSP_REPORT_ONLY` | `true` sends the same policy as `Content-Security-Policy-Report-Only` instead of enforcing it; default `false`. |

The startup check logs only the variable **name** that is missing or invalid,
never its value. The API key and tokens are never printed.

## 4. Custom domain

1. Railway → service → **Settings** → **Networking** → **Custom Domain** →
   `skinledger.focampo.com`; copy the CNAME target Railway shows.
2. Cloudflare → DNS → **Add record**: type `CNAME`, name `skinledger`, target
   from Railway, **DNS only (grey cloud)**. Railway terminates HTTPS.
3. Open `https://skinledger.focampo.com/healthz`; it must return
   `{"ok": true}` with valid HTTPS.

## 5. Security headers and logs

`src/skinledger/web/security.py` builds **two** policies. The strict one covers
every page and has no `'unsafe-inline'` and no `'unsafe-eval'` for scripts:
scripts are external files under `/static/` plus the Camera Kit SDK, and the Kit
origins live in one constant in `src/skinledger/config.py`
(`CAMERA_KIT_ORIGINS`). The module also sets `img-src 'self' blob: data:`,
`Permissions-Policy: camera=(self)`, HSTS, `Referrer-Policy: same-origin`,
`X-Content-Type-Options: nosniff` and `frame-ancestors 'none'`.

The capture policy applies **only to the guided capture page**
(`/people/{id}/capture`, matched by `is_capture_path()`), the single page that
loads the Kit. Report-only logs on production showed the SDK needs it: it
evaluates strings as JS (`'unsafe-eval'`, 1000+ violations), compiles
WebAssembly (`'wasm-unsafe-eval'`), and loads its own stylesheets from
`https://fonts.googleapis.com` and `https://cdnjs.cloudflare.com`, webfonts from
`https://fonts.gstatic.com`, and images from arbitrary HTTPS origins. So that
page's policy adds those to `script-src`, `style-src`, `font-src` and `img-src`.
It still forbids `'unsafe-inline'` for scripts, and `frame-ancestors`,
`object-src 'none'`, `base-uri`, `form-action`, `report-uri` and `report-to` are
identical to the strict policy. Every other page — including `/try`, which only
renders the invite form — keeps the strict policy. If the Kit needs another
origin, add it to the capture policy and its constants here rather than
loosening the strict one.

The policy carries `report-uri /csp-report` and `report-to csp-endpoint`; the
`Report-To` response header defines that group. `POST /csp-report` accepts
`application/csp-report` and `application/reports+json`, caps the body at 8 KB,
rate-limits per client IP and always returns 204. It logs `csp.violation` with
only the violated directive, the blocked URI reduced to scheme+host (or
`inline`/`eval`/`blob`/`data`) and the page path — never the body, query strings
or source samples. Watch these logs after changing either policy: the strict one
must stay free of `'unsafe-eval'`, and any report coming from a page other than
`/people/{id}/capture` means an origin was added to the wrong policy.

Uvicorn access logging is off (`--no-access-log`) so query strings can never be
logged. The JSONL application event log is unchanged. `--proxy-headers` and
`--forwarded-allow-ips='*'` make the app see the Cloudflare client IP, which is
what the `/try` invite-code rate limit keys on.

## 6. Admin usage

Open `/admin/usage` with the header:

```
X-Admin-Token: <ADMIN_TOKEN>
```

A missing or wrong header returns 404, and `?token=` is not supported. The page
shows counts only: visitor analyses/units today and since deploy, your admin
units, analyses left in the visitor pool, the caps, `ALLOW_UPLOAD`, the YouCam
balance (or `unavailable`), rejected 0-unit attempts by error code, and the
number of files outside `masks/` in `DATA_DIR` (must be 0). It never shows a
visitor's name, scores or masks.

## 7. Public sample and judges' page

Set `SEED_SAMPLE_ON_START=true` to create the public "Sample user (SIMULATED)"
profile on startup if it is missing (running again never duplicates it), or run
once:

```
uv run python -m skinledger.seed --sample-person
```

The sample is read-only for visitors and appears on `/people`. `/demo` explains
it, links `/try`, and says the invite code is in the Devpost testing
instructions (2 analyses per person). `/try` and the footer link to `/demo`.

## 8. Acceptance checklist

- [ ] Railway service deployed from `focampok/skinledger` with a volume at `/data`.
- [ ] Variables set by hand: API key, `INVITE_CODE`, caps and the rest of the list above.
- [ ] `https://skinledger.focampo.com/healthz` returns 200 with valid HTTPS.
- [ ] Redeploy keeps the data (the volume persists).
- [ ] `/admin/usage` without the `X-Admin-Token` header returns 404.
- [ ] The Camera Kit opens on the domain: correct CSP, no console errors.
- [ ] After a real analysis, `/admin/usage` shows 0 files outside `masks/`.
- [ ] `/demo` links `/try`, names "Sample user (SIMULATED)" and mentions the Devpost invite code.

## 9. Keep it up

Leave the Railway service and the volume running until judging/winners are
done. Do not delete the service or the volume; deleting the volume deletes all
scores and masks.
