# SkinLedger: Devpost description

Paste the sections below into the Devpost form. `<INVITE_CODE>` is a placeholder: the real code goes only into Devpost, never into the repo. Items marked **[PLANNED]** are removed or reworded before submission if the feature did not ship (see `requirements-matrix.md`, Open items).

---

## Project name
SkinLedger

## Tagline (elevator pitch)
Is it working or not? Know before you rebuy. SkinLedger only counts a skin change if it beats the noise of the measurement itself.

## Inspiration
People wonder about their skin right before a purchase, and right when they are standing in front of a mirror deciding whether a product is working. I have been there: four weeks into a new serum, with no idea whether it was doing anything. The mirror changes with the light, and most beauty apps show deliberately encouraging scores.

So I tested the measurement first. On day one I took two guided captures of my own face, three minutes apart, under the same light. The YouCam skin scores moved on their own: pore by +17.3, acne by +15.0, radiance by -7.9, oiliness by +7.5, firmness by +6.7, droopy upper eyelid by -6.2, tear trough by -5.5 and droopy lower eyelid by +5.2. The remaining aspects moved 3.5 points or less, and skin type came back identical. That is one person's day-1 measurement, not a claim about accuracy in general, but it made the point: a tracker that reads that movement as progress would be telling you stories. SkinLedger is built around that finding.

## What it does
SkinLedger is a responsive web app (installable as a PWA) that gives a person an honest answer to "is this product working?" before they rebuy it.

1. **Profiles with consent.** Adults 18+ only. Each person has their own profile, consent record and delete button.
2. **Guided capture or quick try.** The YouCam JS Camera Kit guides light, distance and pose for repeatable weekly captures. A quick photo upload is available for first-time visitors with an invite code.
3. **Skin analysis.** Each capture runs the YouCam AI Skin Analysis API: 15 numeric skin scores plus skin type. SkinLedger stores the `raw_score` of each aspect and the analysis masks. It never stores or shows the display score, because that score is adjusted to look more favourable.
4. **Your own noise band (the key idea).** Day 1 takes two captures. For each aspect, the band is the larger of the difference between the two captures and a 3-point floor. An aspect whose band is wider than 10 points is shown as **"Unstable for your setup"** and is left out of verdicts. SkinLedger tells you which metrics are reliable for you before it gives a verdict. In my own day-1 pair, pore and acne moved more than 10 points between two captures taken three minutes apart, so they would be flagged for me.
5. **Timeline per aspect.** One chart per aspect with the noise band shaded around your baseline. Only changes outside the band count. **[PLANNED: timeline page is being built today]**
6. **Product log and verdict.** Log what you started and when. At day 14 and day 28 a check-in compares your target aspects with your baseline and the band, and returns **Keep**, **No measurable change → reconsider before rebuying**, or **Worse → pause & consult**, with the three aspects that changed most. It warns when another product changed in the same window. **[PLANNED: verdict engine and screen]**
7. **AM/PM routine and generic shopping list.** Fixed rules map your lowest aspects to ingredient categories (no brands). **[PLANNED: routine and list]**

### Data labels: REAL, SIMULATED, SAMPLE
Everything on screen carries a label.
- **REAL**: an actual analysis of a real capture (my day-1 captures, and visitors' own analyses).
- **SIMULATED**: generated scores for the demo, used for the day-14 and day-28 check-ins in the public sample profile (no photos, no masks). The verdict screen shows the banner "Demo: day 14/28 check-ins are SIMULATED. Day 1 is real."
- **SAMPLE**: fixtures and example products (for instance "Niacinamide serum (SAMPLE)"). No real product brands appear anywhere.

Two weeks of real history cannot exist at the time of submission, so the demo shows my real day 1 and labels everything after it as simulated.

### Privacy by design
Adults 18+ only. Every analysis requires ticking "This is my own face and I am 18 or older." SkinLedger never stores your photo: it is held in memory, sent to the YouCam API for analysis and discarded, with no disk, no object storage and no cache. We store only the scores (`raw_score`), the result JSON without signed URLs, and the masks. YouCam may keep uploaded files for up to 30 days under its own terms. Photos are never sent to any other AI. You can delete your profile at any time, which removes everything SkinLedger stores.

> Cosmetic skin insights, not a medical diagnosis. Scores are AI estimates and vary with lighting. See a dermatologist for persistent acne, changing moles, rashes or pain.

Powered by YouCam API.

## How we built it
- **YouCam AI Skin Analysis API (V2, SD).** The asynchronous 4-step flow: create the file entry, upload the image to the signed URL, create the skin-analysis task, then poll the task until it reports success or error. 15 numeric aspects with `raw_score` (wrinkle, droopy upper eyelid, droopy lower eyelid, firmness, acne, moisture, eye bag, dark circle, age spot, radiance, redness, oiliness, pore, texture, tear trough) plus skin type. Masks are downloaded in the same job because result links are short-lived.
- **YouCam JS Camera Kit v2.5** in `skincare` mode with strict quality checks for consistent captures. It runs in the browser and sends photos only to the YouCam service.
- **Backend:** Python 3.12 with uv, FastAPI, Jinja templates, HTMX for interaction, SQLite, httpx.
- **Frontend:** Pico CSS, Chart.js (vendored, no CDN), installable PWA.
- **Deploy:** Railway with a persistent volume at `https://skinledger.focampo.com`.
- **Guards on the shared link:** invite code to run a real analysis, 2 real analyses per person, a daily unit cap and a hard total unit cap, all set by environment variables. The API key lives only in environment variables on the server; the browser never talks to the YouCam REST API.
- **Testing:** mocked API client and fixtures labelled SAMPLE; no test uses a real photo.

## Challenges we ran into
- **The measurement moves on its own.** Two captures three minutes apart gave different scores, which became the core feature rather than a bug to hide.
- **Using `raw_score`, not the display score.** The API's display score is adjusted to look more favourable, so SkinLedger tracks only `raw_score`.
- **Result links expire quickly.** Masks and scores are stored immediately after a successful analysis.
- **Showing results without keeping photos.** The image arrives as the raw request body, stays in memory, goes to YouCam and is dropped; no code path writes it to disk.
- **Consent, attestation and delete.** Face analysis needs explicit consent, an own-face and 18+ attestation on every analysis, and a delete that really removes everything we store.
- **Protecting a shared link's unit budget.** Invite code, per-person limit, daily and total caps, so judges and friends cannot exhaust the demo.
- **Camera Kit integration details.** Getting the SDK to initialise and the guided capture to complete reliably on a phone took real debugging.

## Accomplishments that we're proud of
- A real end-to-end guided capture on my phone, analysed and stored, and a measured day-1 noise band from my own two captures.
- A product whose headline feature is saying "this metric is not reliable for you yet".
- A consent-first, photo-never-stored design that I would be comfortable using for my family.
- An honest demo: real day 1, clearly labelled SIMULATED follow-up.

## What we learned
- Skin scores are estimates, and light changes them as much as skincare does. Any tracker has to measure its own noise before it claims progress.
- Showing "No measurable change" is a feature: it can save someone from rebuying a product that is not doing anything measurable for them.
- A short test-retest check on day one is cheap and reveals which aspects to trust.

## What's next
- Longer real tracking beyond day 28, and more check-in points.
- A "Before you buy" ingredient check against your latest capture.
- A sun-care reminder using skin tone type.
- A private instance for family use after the hackathon.

## Built with (tags)
python, fastapi, htmx, sqlite, chart.js, youcam-api, pwa, railway

## Try it out (links)
- Live demo: https://skinledger.focampo.com
- Repo: https://github.com/focampok/skinledger (MIT licence)
- Video: `<YOUTUBE_URL>` (fill in after upload)

## Testing instructions (for judges)
1. Open https://skinledger.focampo.com/demo. Browse the public "Sample user (SIMULATED)" profile with no code. **[PLANNED: /demo page and sample profile]**
2. To analyze your own face, go to `/try` and enter the invite code `<INVITE_CODE>`.
3. Tick "This is my own face and I am 18 or older."
4. Use the guided camera (Chrome or Safari on a phone, allow camera access) or upload a well-lit, front-facing selfie. Please use only your own face.
5. You get 2 analyses per person; they are the day-1 pair that builds your noise band. Your photo is never stored. Delete your profile when you are done.
6. No account or password is needed.

## Suggested screenshots (see `docs/screenshots.md`)
1. Guided capture on the phone (Francisco's face).
2. Day-1 result: 15 scores plus skin type (REAL).
3. Noise-band page with "Unstable for your setup" chips (REAL).
4. Timeline with the shaded band and dashed SIMULATED points.
5. Verdict screen with the SIMULATED banner and disclaimer.

