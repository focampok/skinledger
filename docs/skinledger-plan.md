# SkinLedger: plan for the YouCam API Skin AI & eCommerce VTO Hackathon

*Written Monday 26 Oct 2026, ~20:10 GT (Guatemala time, UTC−6); rewritten in English and updated ~20:30 GT with Francisco's photo-handling decision (production keeps a photo upload path; original photos are never stored). Single source of truth for scope. Sources: `HANDOFF.md` and `extract.md` (same folder), plus the official docs re-read today: the Skin Analysis and JS Camera Kit reference (https://docs.perfectcorp.com/reference/ai_skin_analysis), the `/develop/` pages (quick start, API server, error codes, rate limit, webhook, file retention, debugging guide, FAQ, MCP, agent skills) and the official repo `github.com/YouCam-API/skills`. Differences from extract.md are in §5.1. Stack and accounts: `skinledger-stack-setup.md`. Prompts for your coding agent: `skinledger-prompts.md`. Nothing has been built, no accounts or keys were created and no units were spent.*

**Legend:** **[verified 26 Oct]** = read today in the official docs. **[unverified]** = not in any official source I read; the code must tolerate it and you confirm it during the build. **[confirm]** = your decision is pending (only two minor notes remain, at the end of §15).

## Decisions, 26 Oct 2026
- **Format: responsive web app + installable PWA** (manifest + icon), over HTTPS, usable with the phone camera. No APK. Decided by you today.
- **Stack:** FastAPI + Jinja + HTMX, SQLite, httpx, Chart.js, JS Camera Kit from the CDN (`skincare` mode, `qualityLevel: 'strict'`, UI `enu`/`esp`). No LLM. Details in stack-setup.
- **Deploy:** Railway at **`skinledger.focampo.com`** (no separate landing page). The YouCam key lives only in environment variables.
- **Local folder:** `~/Proyectos/skinledger` ✔. Public repo `focampok/skinledger`, MIT ✔ (confirmed 26 Oct).
- **Decided 26 Oct, ~20:12 GT (Francisco):** 18+ profiles only; schedule Wed 28 and Thu 29 evenings + Sat 31 and Sun 1; optional extras only "Before you buy" and the Fitzpatrick sunscreen reminder; polling only (no webhooks); endpoint `v2.0` with the version in a variable; noise-band floor 3.0 points; no `/admin/backup` endpoint.
- **Decided 26 Oct, ~20:24 GT (Francisco) — photos:** production keeps **two ways in**: the **Camera Kit** (recommended for weekly tracking, because it keeps captures consistent) and a **photo upload** (the quick "try it" path for friends, coworkers and family from a shared link — the "wow" moment). **The original photo is never stored anywhere we control:** the server holds it in memory, validates it, sends it to YouCam (file upload + signed PUT) and discards the bytes. No R2/S3, no photos on disk. Only `raw_score`s, the result JSON (no `ui_score`, no signed URLs) and masks are stored. The shared link is protected by an **invite code**, **2 real analyses per person**, a **daily unit cap** and a **hard total unit cap**, plus a required **"This is my own face and I am 18 or older."** checkbox.
- **Frozen idea:** SkinLedger, *"Is it working or not?"*, with a per-product verdict before you rebuy.
- **YouCam account created and code redeemed today (26 Oct):** 1,000 units, valid ~90 days (until ~24 Jan 2027). Only the API key is left (stack-setup, Part 2).

---

## 1. One-line pitch
*"Before you rebuy a skincare product, SkinLedger tells you from your own measurements whether it is really working — and only counts a change when it beats the noise of the measurement itself."*

Product tagline: ***"Is it working or not? Know before you rebuy."***

## 2. Problem, user and moment
- **Problem:** you spend 4 weeks on a serum without knowing if it works. The mirror lies, the light changes, and beauty apps show "motivating" scores (YouCam's `ui_score` is deliberately adjusted to look more favourable).
- **User:** an adult already using 1–3 products who wants to decide with data whether to rebuy. Secondary: friends, coworkers and family who try it once from a shared link (each adult with their own profile and consent).
- **Challenge moment we target (official wording):** *"…standing in front of a mirror deciding whether a product is working."* We also touch *"right before a purchase"* with the generic shopping list and, if it gets in, "Before you buy".
- **Honest, brand-free eCommerce angle:** the verdict is a purchase decision (rebuy, reconsider or pause). The routine is expressed in **ingredient categories** and the shopping list is generic. Any catalogue is SAMPLE.

## 3. User flow (P0)
1. **Profile** → create a person → **consent** screen (adult 18+, what is sent to YouCam, how long YouCam keeps it, that we never store the photo, how to delete) → accept.
2. **Analyze:** choose **Guided capture (Camera Kit)** — recommended for tracking — or **Upload a photo** (quick try). Before each analysis, tick **"This is my own face and I am 18 or older."** The photo goes from memory to YouCam and is discarded; `raw_score`s and masks are stored **immediately**.
3. **Day-1 baseline:** 2 analyses in a row (same place, same light) → per-aspect **noise band**. For a visitor from the shared link, these 2 analyses are their whole allowance and the "wow": 16 scores, masks, and "how much your score moves on its own".
4. **Products:** "Started a niacinamide serum on 28 Oct" (generic name, category, date, target aspects suggested by rules).
5. **Timeline:** one chart per aspect with the shaded noise band; REAL and SIMULATED points look different.
6. **Check-in (day 14 and 28):** 1 capture → per-product **verdict**: **Keep** / **No measurable change → reconsider before rebuying** / **Worse → pause & consult**, with the aspects that changed most and before/after masks.
7. **Routine:** AM/PM per person from fixed aspect → ingredient-category rules + a generic **shopping list**.
8. Always visible: the mandatory **disclaimer** and "Powered by YouCam API".

## 4. Features and cut order

### P0 (must ship; no submission without it)
| # | Feature | Key notes |
|---|---|---|
| P0.1 | **Profiles + consent + delete** | Adults only (18+ checkbox). Per-person consent with text version and date. "Delete this person" removes rows and mask files from the volume. |
| P0.2 | **Capture: Camera Kit + photo upload** | Camera Kit: `faceDetectionMode: 'skincare'`, `qualityLevel: 'strict'`, `language: 'enu'` or `'esp'`, `videoQuality: '1080p'`, `imageFormat: 'blob'` **[verified 26 Oct]** — recommended for weekly tracking. Upload: JPG/PNG < 10 MB, short side ≥ 480 px — the quick try. Both send the image bytes as the raw request body (no multipart temp files) and require the own-face/18+ checkbox. Captures record `source` = `camera_kit` or `upload`. |
| P0.3 | **Skin Analysis SD client, 16 aspects, 4-step async flow** | `POST /s2s/v2.0/file` → `PUT` to the signed URL → `POST /s2s/v2.0/task/skin-analysis` with `src_file_id` and `dst_actions` → `GET …/skin-analysis/{task_id}` until `success` or `error` **[verified 26 Oct]**. Mocked tests. |
| P0.4 | **Never persist the photo; store `raw_score` + masks immediately** | The image lives only in memory during the request and is discarded once YouCam has it. Never `ui_score` (not stored, shown or charted). Result URLs last 2 h (renewable via the `task_id`, valid 30 days): masks are downloaded in the same job. |
| P0.5 | **Per-aspect timeline** | Chart.js, one chart per aspect, shaded noise band, REAL/SIMULATED badge per point, upload vs. Camera Kit shown in the tooltip. |
| P0.6 | **Day-1 noise band (2 captures)** | Band per aspect = max(\|A − B\|, 3.0 points). The 3.0 floor is a **product heuristic**, not a YouCam figure; the UI says so ("estimated from 2 captures"). |
| P0.7 | **Product log** | Generic name, category, start, optional end, target aspects. |
| P0.8 | **14/28-day verdict per product** | Keep / No measurable change → reconsider before rebuying / Worse → pause & consult; "Too early" before day 12; warning if another product started in the same window. Top changed aspects + before/after masks (REAL captures only). |
| P0.9 | **AM/PM routine + generic shopping list** | Fixed rules, no brands, no medicines. Uses the 3 aspects with the lowest `raw_score` in the latest capture. |
| P0.10 | **Disclaimer** | Exact text in the footer of every page and on the verdict screen. |
| P0.11 | **Deploy + shared-link guards** | Railway + persistent volume + `skinledger.focampo.com`; invite code to analyze; 2 real analyses per person; daily and total unit caps (env vars); friendly "demo limit reached" message. |
| P0.12 | **Submission** | README (English, MIT), 1–3 min video, Devpost description, screenshots with your face only. |

### P1 (optional; only if the kill switch passed and there is time left)
| # | Feature | Notes |
|---|---|---|
| P1.1 | **"Before you buy"** | Paste an ingredient list → Fit / Caution / Mismatch against your latest capture, using a ~40-ingredient rules table. Soft language. |
| P1.2 | **Fitzpatrick sunscreen reminder** | AI Fitzpatrick Skin Type API: endpoint, parameters and cost **[unverified]**; read the docs before spending units. |

**Cut on 26 Oct (post-hackathon):** Skin Simulation, the agentic angle with the official MCP, and the `info-skinledger.focampo.com` landing page. Notes for later: the `beauty` MCP (`https://mcp-api-01.makeupar.com/mcp/beauty`) offers `AI_Skin_Analysis`, `AI_Skin_simulation` and `Get_Feature_Cost`; if used, only with a regular selfie, never with a Camera Kit photo (Terms §3.6: those photos may not pass through another AI).

### Out of scope (not built)
Native app or APK, HD, real multi-user accounts with passwords, LLM, brand or named-product recommendations, push notifications, PDF export, multi-language UI (the UI is English; only the Camera Kit switches to `esp`), webhooks (polling only, decided), photo storage of any kind (decided), Skin Simulation, MCP/agents and landing page (cut on 26 Oct).

### Cut order if you fall behind
1. All of P1 (P22 Fitzpatrick → P21 Before you buy).
2. Before/after masks on the verdict (numbers and arrows stay; masks are still stored).
3. Shopping list (the AM/PM routine stays).
4. Camera Kit language selector (`enu` stays).
5. 28-day check-in in the UI (day 14 stays; the engine supports both).

**Never cut:** consent + delete, own-face/18+ attestation, invite code and unit caps, never storing the photo, `raw_score` (never `ui_score`), storing the result immediately, the noise band, the SIMULATED/SAMPLE label, the disclaimer and the demo privacy rule.

## 5. API facts the plan relies on
- **Endpoints [verified 26 Oct]:** base `https://yce-api-01.makeupar.com`. `POST /s2s/v2.0/file` with `{"files":[{"content_type","file_name","file_size"}]}` → `data.files[0].file_id` and `data.files[0].requests[0]` (`method: PUT`, `url`, `headers`). `PUT` the bytes with those headers. `POST /s2s/v2.0/task/skin-analysis` with `src_file_id`, `dst_actions`, `format: "json"` → `data.task_id`. `GET /s2s/v2.0/task/skin-analysis/{task_id}` → `data.task_status` (`running`/`success`/`error`) and `data.results.output[]` with `type`, `ui_score`, `raw_score`, `mask_urls`.
- **The 16 SD aspects [verified 26 Oct]:** `wrinkle, droopy_upper_eyelid, droopy_lower_eyelid, firmness, acne, moisture, eye_bag, dark_circle_v2, age_spot, radiance, redness, oiliness, pore, texture, tear_trough, skin_type`. SD and HD are never mixed (400 `InvalidParameters`).
- **[unverified]:** the exact shape of `skin_type` (categorical, with `whole/t_zone/u_zone`), `all` and `skin_age` in `format: json`, and which field carries the error code when `task_status = error`. Also **whether the mask images contain any of the face photo** (we request per-aspect masks with `enable_mask_overlay` off; if the first real result shows masks embed the photo, set `STORE_MASKS=false` and keep scores only). The parser treats them as optional and stores the raw JSON for auditing.
- **Image errors [verified 26 Oct]:** `error_below_min_image_size`, `error_exceed_max_image_size`, `error_src_face_too_small`, `error_src_face_out_of_bound`, `error_lighting_dark`. General [verified 26 Oct, /develop/error_codes]: `error_no_face`, `error_large_face_angle`, `error_multiple_people`, `error_decode_image`, `error_download_image`, `exceed_max_filesize`, `invalid_parameter`, `error_face_parsing`, `error_inference`, `unknown_internal_error`. An `error` **does not consume units**, so rejected uploads (no face, several people, etc.) are free.
- **Image requirements:** JPG/PNG < 10 MB, short side ≥ 480 px for SD, face > 60% of the width, frontal, good light. The Camera Kit in `strict` requires ≥ 75% face and lighting 0.8–0.9 **[verified 26 Oct]**. Uploads do not get this guidance, which is why the Camera Kit is the recommended path for tracking.
- **Retention [verified 26 Oct, /develop/file_retention_period]:** `file_id` and `task_id` are valid **30 days**; the result download URL lasts **2 h**, but a fresh link can be requested with the `task_id`; everything uploaded and generated is deleted after 30 days. (The Skin Analysis reference still says "retained for 24 hours": we design for the strict case and store everything immediately.) Consent text: "YouCam may keep the uploaded photo for up to 30 days; SkinLedger never stores it."
- **Rate limit [verified 26 Oct, /develop/rate_limit]:** 250 requests per 300 s per IP **and** per token, recommended pace ~5 QPS; otherwise `429`. Back off and retry. Irrelevant at our scale.
- **Unit balance:** `GET /s2s/v1.0/client/credit` (free) returns `results[]` with `type` and `amount`; spendable units are the types starting with `Api`. Per-feature cost: `GET /s2s/v2.0/credit/feature-cost`. **Source: the official `YouCam-API/skills` repo (1 Oct 2026 snapshot), not the docs** → used only on `/admin/usage`, falling back to the local counter if it fails.
- **Terms §3.6:** Camera Kit photos go only to Perfect Corp, never to another AI (we apply the same rule to uploads). **§3.1:** the key is not shared.

### 5.1 What today's docs change versus extract.md
| Topic | extract.md | Official docs (26 Oct) | Effect on the plan |
|---|---|---|---|
| Retention | Result 24 h, URL 2 h | `file_id`/`task_id` 30 days; URL 2 h and renewable with the `task_id` (Skin Analysis reference still says 24 h) | Store everything immediately; re-fetch via `task_id` as plan B if masks fail |
| Rate limit | V1, unverified for V2 | Verified in `/develop/`: 250/300 s per IP and per token, ~5 QPS, `429` | Backoff in the client |
| Endpoint version | `v2.0` | The reference uses `v2.0`; the units table says "V2.0, 2.1" and the official skills repo uses `/s2s/v2.1/task/skin-analysis` | Decided: `v2.0` (documented with examples) with the version in `YOUCAM_SKIN_VERSION`; `v2.1` not used **[unverified: differences]** |
| Polling | Every ~10 s | Quick start: "periodically"; official skills: every 5 s, max 20 tries; FAQ: if you don't check in time, `InvalidTaskId` | Every 5 s up to 180 s; if still `running`, continue in the background, never abandon the `task_id` |
| Errors | `error_src_face_too_small`, `error_lighting_dark`, `error_no_face` | Also `error_src_face_out_of_bound`, `error_below_min_image_size`, `error_exceed_max_image_size` (Skin Analysis); general `error_large_face_angle`, `error_multiple_people`, `error_decode_image`, `exceed_max_filesize`, `invalid_parameter`, `error_face_parsing`, `error_inference`, `unknown_internal_error`; HTTP `InvalidParameters` (400), `InvalidAccessToken` (401), `InvalidTaskId` | Friendly-message table in the client |
| Auth | Bearer | Same; no `< >` around the key. The key is shown **only once** when created (FAQ) | Paste it straight into `.env` and Railway |
| Console | `yce.perfectcorp.com/ai-api` | Keys at `https://yce.makeupar.com/api-console/en/api-keys/` (also under `yce.perfectcorp.com`) | Setup updated |
| Webhooks | "also available" (no detail) | Standard Webhooks, HMAC-SHA256 with a `whsec_…` secret, configured in the console (up to 10), payload `{task_id, task_status}` | Decided: polling only, no webhooks |
| MCP | `/mcp/beauty` only | 3 servers (`beauty`, `fashion`, `creators`); `beauty` includes `AI_Skin_Analysis`, `AI_Skin_simulation`, `AI_Fitzpatrick_Skin_Type_Analysis`, `Get_Feature_Cost`, `Get_Running_Task_Status` | MCP cut (post-hackathon) |
| Balance | Not mentioned | Free balance endpoint (official repo) | `/admin/usage` shows the real balance |
| Camera Kit | CDN, `skincare`, `esp` | Global `YMK`, `YMKAsyncInit`, `qualityLevel` (`strict` = face ≥ 75%, light 0.8–0.9, yaw ±5°), `videoQuality` up to `1920p`, events `faceDetectionCaptured`/`cameraFailed`/`faceQualityChanged`; HTTPS except on localhost | Prompt P05 uses the real API |
| Official skills | — | `YouCam-API/skills` "Skin Analysis Expert" reports `ui_score` | SkinLedger deliberately does the opposite (`raw_score`) and says so in the README |

## 6. Unit budget (1,000 units; SD 16 aspects = 16 units → ≈ 62 analyses)
| Use | Analyses | Units |
|---|---|---|
| Client smoke test (Wednesday) | 2 | 32 |
| Development and debugging on the phone | 6 | 96 |
| Your REAL day 1 (2 captures, noise band) | 2 | 32 |
| Retakes for the video and screenshots | 4 | 64 |
| Your real check-ins after submission (optional) | 4 | 64 |
| **Shared link: friends, coworkers, family and judges** (invite code; `MAX_REAL_ANALYSES_PER_PERSON=2`; `DAILY_UNIT_CAP=96` ≈ 6 analyses/day; `TOTAL_UNIT_CAP=480` ≈ 30 analyses ≈ 15 people) | ~30 | ~480 |
| Margin | ~14 | ~232 |
| **Total** | **≈ 62** | **~1,000** |
- Daily development runs in **mock mode** (`YOUCAM_MOCK=true`) with a SAMPLE fixture shaped like the docs example: 0 units.
- Failed analyses (`error`, e.g. no face or several people) are not charged. The app keeps an `api_usage` counter (16 per success) on `/admin/usage`, next to the real account balance (balance endpoint from the official repo; counter only if it fails).
- The daily and total caps count **invite-code (visitor) analyses**; your own analyses (with `ADMIN_TOKEN`) are counted separately and not capped, so you watch them on `/admin/usage`.
- **Judges share the same visitor pool.** Share the link with friends mostly after you submit, and before submission check `/admin/usage` so at least ~8 analyses (128 units) remain for judges; if friends use more, raise `TOTAL_UNIT_CAP` from the margin or rotate `INVITE_CODE` (old code stops working).
- Optional: +500 units per platform for posting the video (max 2), using the form in extract.md §4, before Mon 2 Nov 10:45 GT.
- **Redeemed 26 Oct:** expires around **24 Jan 2027**.

## 7. Schedule (≈ 16 h spread over evenings + weekend)
| Day | Hours | Prompts | Gate |
|---|---|---|---|
| Mon 26 (today) | 0 | — | ✔ YouCam account created and code redeemed (1,000 units). API key pending |
| Tue 27 | 0 (optional 0.5) | Setup prep only (stack-setup Part 4, steps 1–4) | — |
| **Wed 28, evening** | ~3 | Create the API key first · P00–P03 | Client passes mocked tests and **1 real analysis** stores 16 `raw_score`s and masks |
| **Thu 29, evening** | ~3 | P04–P07 | From the phone (HTTPS tunnel): consent → Camera Kit **and** upload → analysis stored, no photo on disk → noise band |
| Fri 30 | 0 (buffer) | Only if behind: P08 | — |
| **Sat 31** | ~6 (10:00–17:30 with breaks) | P08–P16 | **20:00 GT: kill switch** (below) |
| **Sun 1 Nov** | ~4 (13:00–20:00) | P17–P20 (+ P21–P22, P1, only if time allows) | **Submit before 21:00 GT.** Checklist at 16:00 |
| Mon 2 Nov | 0 | — | Margin only until 10:45 GT. No planned work: save energy for the Vultr kickoff (Tue 3, 09:00) |

**Schedule confirmed by Francisco (26 Oct):** Wednesday and Thursday evenings + Saturday and Sunday.

**Kill switch, Saturday 31 Oct, 20:00 GT.** On `https://skinledger.focampo.com`, from your phone: profile with consent → Camera Kit capture → real `success` → `raw_score`s and masks stored, no photo file on the volume → point on the timeline → product logged → verdict computed (on a labelled SIMULATED check-in, since there are no real 14 days) → one **upload** analysis through the invite-code flow shows the friendly result and counts against the caps. **If it doesn't work end to end → GO-lite:** keep the app for personal or family use and don't submit.

## 8. Mapping to the judging criteria
| Criterion (equal weight; tie → technical) | How SkinLedger covers it | What to show in the video |
|---|---|---|
| **Stage 1: theme + correct API use** | Skin AI, the "deciding whether a product is working" moment. Official 4-step flow + Camera Kit. | Say "YouCam AI Skin Analysis API" and "JS Camera Kit". |
| **Technical implementation** | Full async pipeline, 16 aspects, `raw_score` instead of `ui_score`, masks stored, photos never stored, noise band, tested verdict engine, unit caps, real delete. Not a wrapper. | The "only counts if it beats the noise band" moment. |
| **Design (complete product)** | Installable PWA; profile → capture/upload → timeline → verdict → routine; useful image-error messages; shareable try-it link. | Home-screen icon and the flow on the phone. |
| **Potential impact** | Saves money on products that don't work; honest rebuy decision; anyone can try it from a link with consent. | "Reconsider before rebuying". |
| **Quality of the idea** | Non-obvious use: measuring the noise of the measurement itself and refusing to claim fake improvements. | Shaded band + an honest "No measurable change". |

## 9. Demo data policy
- **REAL** = real analyses (your day 1 and later captures; visitors' analyses). Shown with a "REAL" badge.
- **SIMULATED** = the 14/28-day history created by the `seed` script (generated scores, no images). "SIMULATED" badge on every point, dashed chart line and a banner on the verdict screen: *"Demo: day 14/28 check-ins are SIMULATED. Day 1 is real."*
- **SAMPLE** = the docs-shaped fixture (mock mode), the sample catalogue and sample products. "SAMPLE" badge.
- Fake photos or masks are never generated. SIMULATED points have no masks.
- Numbers in the README and Devpost come from the app, never invented.

## 10. Privacy (non-negotiable)
- **Only your face** in the video, the repo and the screenshots. **Never photos of your family** there (rules §7 and §10 let Perfect and Devpost use the demo's name, image and voice for 3 years).
- **No minors:** consent requires "I confirm this person is 18 or older", and every analysis requires **"This is my own face and I am 18 or older."** (the API is for adults, Terms §2.2/§4.1; never under 13).
- **Per-person consent** before the first analysis, with text version and date. Revoking = deleting.
- **We never store the original photo.** It stays in memory during the request, goes to YouCam via the file upload + signed PUT, and the bytes are discarded. No object storage, no photo files, no temp files (the image arrives as the raw request body, not multipart). Stored: `raw_score`s, the result JSON without `ui_score` or signed URLs, and masks.
- **Delete** a person removes their rows and mask files from the volume. The text explains that YouCam may keep the uploaded photo for up to 30 days (§12.4) and how to ask them to delete it.
- **Visitors from the shared link** see only their own profiles (per-browser cookie); `/admin/usage` shows counts and units only, never visitors' scores or masks. Visitors can delete their profile at any time.
- **Your family's tracking** can use the same link with their own consent; a separate private instance after 2 Nov is a minor open note.
- Masks live on the Railway volume, not in the repo (`data/` is in `.gitignore`). The repo contains no faces; Devpost screenshots are uploaded to Devpost, not to the repo.
- No photo is used to train anything (Terms §8.6 t) and none is sent to another AI (§3.6).

## 11. Brand and language rules
- YouCam appears only as **"Powered by YouCam API"** (footer, README, video). The product is not named or styled as a YouCam product.
- **No third-party product brands** in the UI, seed, video or README. Sample products are generic and say SAMPLE ("Niacinamide serum (SAMPLE)").
- **No medical language:** never "diagnose", "treat", "cure", "disease", "prescription", "medication". Use "cosmetic insight", "estimate", "consider". An automated test checks the templates (P13).
- **Mandatory disclaimer, exact text:** "Cosmetic skin insights, not a medical diagnosis. Scores are AI estimates and vary with lighting. See a dermatologist for persistent acne, changing moles, rashes or pain."

## 12. Verdict engine (frozen definition)
- **Product baseline** = mean of the person's captures in the 7 days before the product start (or the 2 day-1 captures if the product started on day 1).
- **Check-in** = the capture closest to day 14 (window 12–20) or day 28 (window 26–35) from the start.
- **Per target aspect:** Δ = check-in − baseline (higher = better). *Improved* if Δ > band; *Worse* if Δ < −band; otherwise *within noise*.
- **Verdict:** if any target aspect got worse → **Worse → pause & consult**. Otherwise, if at least one improved → **Keep**. If none left the band → **No measurable change → reconsider before rebuying**. Before day 12 → **Too early to tell**. No noise band → no verdict ("Take 2 baseline captures first").
- **Warnings:** if another product started or ended in the window → *"Another product changed in this window; this verdict can't isolate one product."* If the compared captures mix REAL/SIMULATED → SIMULATED badge on the verdict. If they mix upload and Camera Kit → note *"Captured different ways; differences may be larger."*
- Shows the 3 aspects with the largest \|Δ\| (across the 15 numeric aspects, not only targets) with arrows and, if both captures are REAL, their masks side by side.

## 13. Routine rules (fixed table, no brands)
| Low aspect (among the 3 lowest) | Ingredient category | When |
|---|---|---|
| `oiliness`, `pore` | Niacinamide serum; lightweight gel moisturizer | AM/PM |
| `moisture` | Ceramide or hyaluronic acid moisturizer | AM/PM |
| `age_spot`, `radiance` | Broad-spectrum SPF 30+; vitamin C serum | AM |
| `redness` | Fragrance-free, gentle cleanser and soothing moisturizer; avoid alcohol-heavy toners | AM/PM |
| `acne` | Salicylic acid (BHA) cleanser or leave-on, a few times a week | PM |
| `texture` | Gentle exfoliant (AHA/PHA), 2–3 nights a week | PM |
| `wrinkle`, `firmness` | Retinol (start low, alternate nights) + SPF 30+ in the morning | PM / AM |
| `dark_circle_v2`, `eye_bag`, `tear_trough`, eyelids | Caffeine eye cream; sleep and hydration note | AM |
| Always | Gentle cleanser, moisturizer, SPF 30+ every morning | AM/PM |
Conflict rules: retinol and AHA/BHA never on the same night (alternate); if `redness` is among the 3 lowest, exfoliants drop to 1–2 nights a week. If `acne` is the lowest, the card carries the disclaimer. **These rules are general cosmetic heuristics, and the UI says so.**

## 14. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Running out of units (1,000 units / 16 per SD analysis ≈ 62 analyses) | Mock mode for development; invite code; 2 real analyses per person; `DAILY_UNIT_CAP` and hard `TOTAL_UNIT_CAP` by env var; real balance on `/admin/usage`; rotate `INVITE_CODE` if the link spreads. Rejected images cost nothing. |
| Shared link abused (strangers, someone else's face, minors) | Invite code required to analyze; required "This is my own face and I am 18 or older." checkbox; 18+ consent; caps; the photo is never stored; visitors can delete their profile. Clearing cookies to get more analyses is still bounded by the daily and total caps. |
| Photo accidentally persisted (temp files, logs, caches) | Raw-body upload (no multipart spooling), no logging of bodies, service worker never caches `/api` or images, and a test asserting no image file exists in `DATA_DIR` or the temp dir after an analysis. |
| Masks turn out to contain the photo **[unverified]** | Check the first real result on Wednesday; if so, set `STORE_MASKS=false` and show scores only. |
| Score noise (lighting) | Camera Kit `strict` recommended for tracking, 2 day-1 captures, per-aspect band, same time and place for check-ins, UI notes; uploads labelled as such. |
| No real 14/28-day history | REAL day 1 + labelled SIMULATED history. The video says so out loud. |
| Camera Kit doesn't run on some browser or without HTTPS | Test Thursday from the phone over an HTTPS tunnel; `cameraFailed` shows a clear message and offers "Upload a photo instead". |
| Response shape differs from expectations (`skin_type`, `all`, errors) | Tolerant parser, raw JSON stored, check against the first real result on Wednesday and adjust the fixture. |
| Judges find the visitor pool exhausted | Check `/admin/usage` before submitting; keep ≥ 8 analyses for judges; raise the cap from the margin or rotate the code; the public SAMPLE/SIMULATED profile works without units. |
| Railway loses the database on redeploy | SQLite and masks on a **volume** (`/data`); redeploy test on Saturday. |
| Heavy competition (~1,300) | Polished design and honesty (noise band) as the differentiator; the try-it link as the wow; the video tells the story in 30 s. |
| Energy for 3 Nov | Submit Sunday before 21:00; Monday is margin only. |

## 15. Checklist before Wednesday 28
- [x] Devpost registration (26 Oct, per Hack).
- [x] YouCam account created and code redeemed (26 Oct; 1,000 units until ~24 Jan 2027).
- [ ] Create the API key on Wednesday 28 first thing (shown only once) and put it straight into `.env`.
- [x] Folder `~/Proyectos/skinledger` and public repo `focampok/skinledger` confirmed.
- [ ] Railway account with a payment method.
- [ ] Check in Cloudflare that `skinledger` doesn't exist yet.
- [ ] Read `skinledger-prompts.md` Parts A and B.
- [ ] Pick an `INVITE_CODE` that is easy to type (e.g. two words + a number).

## Files
- `HANDOFF.md`, `extract.md`: context and sources.
- `skinledger-plan.md`: this document.
- `skinledger-stack-setup.md`: accounts, variables, local setup, repo, local HTTPS, Railway, DNS, shared-link and judge access, licence, secrets.
- `skinledger-prompts.md`: P00–P22 for your coding agent (P21–P22 optional), with acceptance criteria.

**Minor open notes (not blocking):** which YouTube account to use for the video; and whether to set up a private family instance after 2 Nov.
