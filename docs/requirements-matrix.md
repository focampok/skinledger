# SkinLedger: Devpost requirements matrix

Prepared Thu 29 Oct 2026 (GT) from `extract.md` §2–§6, `skinledger-plan.md` and `skinledger-prompts.md` (P17–P20).
Target to submit: **Sat 31 Oct 2026, 21:00 GT** (kill switch Sat 20:00 GT). Hard deadline: **Mon 2 Nov 2026, 10:45 GT** (11:45 EST).
Status values: `todo` or `in progress`. Nothing is `done` until Francisco checks it with evidence (P20).
Owners: **F** = Francisco, **SL** = SkinLedger agent (scope, drafts, review), **CA** = Francisco's coding agent (prompts P08–P20).

## A. Devpost submission requirements (extract.md §5)

| # | Requirement | Artifact that satisfies it | Owner | Status |
|---|---|---|---|---|
| A1 | Public repo URL with all code, assets and run instructions, plus a licence (organizer notice asks for public) | `https://github.com/focampok/skinledger`, MIT `LICENSE`, README with run steps (`README.md` at the repo root, P17) | F + CA | in progress (repo exists, MIT confirmed 26 Oct; README is being updated against what shipped) |
| A2 | Text description: features and consumer / eCommerce value | `docs/devpost.md` pasted into the Devpost form | SL (draft text) → F (paste) | in progress (drafted; wording of unbuilt features to check) |
| A3 | Screenshots | `docs/screenshots.md` list; 4–5 images uploaded to the Devpost gallery (not committed to the repo) | F | todo (depends on P08–P16 UI) |
| A4 | Video, 1–3 min, YouTube (preferred) or Vimeo | `docs/video-script.md`, target 2:20–2:40, uploaded unlisted or public | F (record, upload), SL (script) | in progress (script drafted; recording after P16) |
| A4a | Video shows the full flow | capture → analysis → noise band → timeline → verdict → routine → privacy (script segments 3–8) | F | todo |
| A4b | Video explains which YouCam API is used | Said aloud and on screen: "YouCam AI Skin Analysis API" and "YouCam JS Camera Kit" (segment 2, repeated in the closing) | F | in progress (in script) |
| A4c | Video shows it working on the target device | Phone recording of the Camera Kit capture on `skinledger.focampo.com` | F | todo |
| A4d | No copyrighted music, no third-party marks | No music (or a CC0 track with its link kept in `docs/`); products covered or generic; no logos in frame | F | todo |
| A5 | Free test access until judging ends (20 Nov per rules; winners about 24 Nov) | Live demo `https://skinledger.focampo.com`, public SIMULATED sample profile at `/demo` (no code), `/try` with the invite code in the testing instructions. Do not stop the Railway instance or volume until winners are announced | F | todo (Railway deploy is P15) |
| A5a | Login credentials if the app has login | No accounts. The testing instructions give the invite code (`<INVITE_CODE>` placeholder in `docs/devpost.md`; real value typed only into Devpost "judges' notes / testing instructions", never into the repo) | F | todo |
| A5b | Enough visitor units left for judges | `/admin/usage` check: at least 8 analyses (128 units) left in `TOTAL_UNIT_CAP` and in the real balance before submitting (plan §6) | F | todo |
| A6 | All material in English (or translated) | All submission docs are English; UI is English | SL | in progress |
| A7 | New project or significant update since 29 Sep 2026 | Confirm the first commit date is after 29 Sep 2026 | F | todo (verify with `git log`) |
| A8 | Uses at least one YouCam API in a working prototype (web or mobile) | YouCam AI Skin Analysis V2 (SD, async 4-step flow) and YouCam JS Camera Kit v2.5 | CA | in progress (client and Camera Kit capture work end to end; real Camera Kit capture done end to end this week) |
| A9 | "Not a surface-level wrapper" | README section "Why it isn't a wrapper" and the description's noise-band story | SL (text), CA (code) | in progress |
| A10 | Entry eligibility (individual, adult, country allowed) | Francisco, Guatemala, individual entry; no action | F | in progress (nothing to produce) |

## B. Judging criteria (extract.md §6)

Stage 2 criteria have equal weight; a tie is broken by technical implementation.

| # | Criterion | How the artifacts address it | Where it shows | Owner | Status |
|---|---|---|---|---|---|
| B1 | Stage 1 (pass/fail): fits the Skin AI theme and uses the API correctly | Challenge moment "deciding whether a product is working"; official 4-step flow plus Camera Kit | description "What it does", README "YouCam APIs used", video segment 2 | SL | in progress |
| B2 | Technical implementation (tie-breaker): depth of API use, non-trivial code | `raw_score` instead of the display score; masks stored immediately; per-person noise band; photos never stored; invite code and unit caps; tested verdict engine | README "Why it isn't a wrapper", description "How we built it" and "Challenges", video segment 4 | CA (code), SL (text) | in progress (noise band built; verdict engine is planned, see NOTES) |
| B3 | Design: complete, coherent product, not a proof of concept | Installable PWA; profile → consent → capture → timeline → verdict → routine; friendly image-error messages; consent and delete | screenshots 1–5, video segments 3–7 | CA, F (UI polish pass) | in progress (UI screens after P08 are planned) |
| B4 | Potential impact: real problem, real audience, shown in the demo | Adults already using 1–3 skincare products who want to decide whether to rebuy; "reconsider before rebuying" verdict | description "Inspiration" and "What it does", video segments 1 and 5 | SL | in progress |
| B5 | Quality of the idea: creative, non-obvious API use | Measures the noise of the measurement itself and tells you which metrics are reliable for you before it gives a verdict; honest "No measurable change" | description, README, video segment 4 (key demo argument) | SL | in progress |

## C. Optional bonus (not required)

| # | Item | Details | Owner | Status |
|---|---|---|---|---|
| C1 | Social-share bonus: +500 units per platform, max 2 platforms (+1,000) | Post the demo video publicly on up to 2 platforms. The post must tag **@YouCam API**, name the API used, and include the text **"Received API credits for sharing"**. Account created before 29 Sep 2026; post stays public at least 30 days. Claim form: https://forms.gle/JwMFYMpaExckupEk7, before Mon 2 Nov 10:45 GT. **Posted by Francisco himself from his own accounts; the agent does not post.** | F | todo (optional) |

## D. Internal gates that protect the submission (plan §7, §10, P20)

| # | Gate | Evidence to collect | Owner | Status |
|---|---|---|---|---|
| D1 | Kill switch Sat 31 Oct 20:00 GT: profile → consent → Camera Kit capture → `success` → scores and masks stored → timeline point → product → verdict (SIMULATED check-in) → one upload analysis through the invite-code flow | `git tag killswitch-ok` | F | todo |
| D2 | No key, `.env`, `INVITE_CODE` or `ADMIN_TOKEN` value anywhere in the repo or history | `git log -p` search from P20 | F | todo |
| D3 | Only Francisco's face in repo, video and screenshots; never family | Manual review of every frame and image | F | todo |
| D4 | No photo files on the volume | `/admin/usage` "files outside masks/" = 0 | F | todo |
| D5 | Exact disclaimer on every page and on the verdict screen; "Powered by YouCam API" is the only brand mention; no medical language | `test_copy.py` (P13) green; run the banned-word check on README and docs | CA, SL | todo |
| D6 | Orphan test profile (person 6) removed before recording | Manual check on People page | F | todo |
| D7 | `--proxy-headers` confirmed so the `/try` rate limit sees the real client IP | P15 note | F, CA | todo |
| D8 | Visitor upload test in a private window (16 units) | P16 | F | todo |
| D9 | Submit on Devpost with repo, video and demo links correct; then `git tag submission` | Devpost confirmation page | F | todo |

## E. Open items before submission

Remove each item when verified. Before submitting, `grep -rn "PLANNED" README.md docs/` must print nothing, and no real invite code, admin token or key value may appear anywhere in the repo.

### Features to verify against the live app (drafts mark them `[PLANNED]`)
- [ ] Timeline page (P08, in progress).
- [ ] Product log, verdict engine and verdict screen (P09–P11).
- [ ] AM/PM routine and generic shopping list (P12).
- [ ] SIMULATED seed data and the public "Sample user (SIMULATED)" profile (P14).
- [ ] `/demo` page and the `/try` invite-code flow in production (P15).
- [ ] Railway deploy with volume, `skinledger.focampo.com`, HTTPS, caps (P15).
- [ ] For each feature that did not ship: delete its `[PLANNED]` line in `README.md`, `docs/devpost.md` and its row in `docs/video-script.md` and `docs/screenshots.md`.

### Facts to confirm in the app
- [ ] **Aspect count wording:** all docs say "15 numeric aspects plus skin type" (the 16 SD actions and 16 units per analysis are unchanged). Make the app copy (for example `try.html`), README and video say the same.
- [ ] **Pore and acne flagged unstable:** the drafts say so for Francisco's profile (band 17.3 and 15.0 are above 10; no other aspect exceeds 10). Confirm on `/people/{id}/baseline`.
- [ ] **"3.5 points or less":** the drafts say the other aspects moved 3.5 or less; the earlier table had them at 3.3 or less (dark_circle_v2 3.3, moisture 3.1). Use the figure the app shows.
- [ ] **Photo upload path** exists in the deployed app as the drafts describe.
- [ ] **Installable PWA** (manifest and icon) works on the phone.
- [ ] **Mask storage:** the privacy text assumes masks are stored. If the first real result showed masks embed the photo and `STORE_MASKS=false`, edit the privacy paragraph in README and devpost.
- [ ] README: HTMX, Chart.js and Pico licence names and versions come from the vendored files; the `uvicorn` module path in "Run locally" is correct; `test_copy.py` (P13) passes with README.md included.
- [ ] Repo history: first commit is after 29 Sep 2026.

### Placeholders
- [ ] `<INVITE_CODE>`: typed only into Devpost testing instructions, never committed.
- [ ] `<YOUTUBE_URL>`: filled in after the upload, in Devpost and README.

### Video
- [ ] Rows for unbuilt features cut; "simulated" said aloud and SIMULATED on screen for every day-14/28 element; length 2:15–2:45.
- [ ] Orphan test profile (person 6) deleted before recording; People page shows only Francisco and the sample profile.
- [ ] No family member, brand or logo visible; no invite code, admin token or query strings in the URL bar.

### Operations
- [ ] `--proxy-headers` confirmed for the `/try` rate limit (`request.client.host`).
- [ ] Visitor pool: at least 8 analyses (128 units) left on `/admin/usage` before submitting; keep Railway and the volume running until winners are announced (about 24 Nov).
- [ ] Saturday order: P15 deploy and P16 phone test must finish before the 14:00 checklist if possible; the kill switch is at 20:00 and submission by 21:00 GT.
