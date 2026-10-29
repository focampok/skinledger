# SkinLedger: screenshot shot list

Upload 4–5 images to the Devpost gallery (and use the same files for the video thumbnail). Screenshots go to Devpost only, not into the repo.

Rules for every image:
- Only Francisco's face (REAL captures) or the public "Sample user (SIMULATED)" profile. Never a family member, never a visitor's profile.
- No third-party brands or logos: close other tabs, hide bookmarks, no product labels in frame, no sample product with a brand name (use "Niacinamide serum (SAMPLE)" style names).
- No invite code, admin token, API key or query strings in the URL bar; crop to the page or show only `skinledger.focampo.com`.
- No notifications or personal names in the status bar.
- Labels must be visible where relevant: REAL, SIMULATED or SAMPLE badges, and the footer with the disclaimer and "Powered by YouCam API".
- Mobile screenshots at the phone's native resolution; desktop at 1280 px width or more.

| # | Screen | Data | What it must show | Caption (English) | Status |
|---|---|---|---|---|---|
| 1 | Guided capture on the phone | Francisco's face, live Camera Kit view | Camera Kit guidance (distance or pose hint), the own-face/18+ checkbox ticked | "Guided capture with the YouCam JS Camera Kit keeps light, distance and pose consistent." | todo |
| 2 | Day-1 analysis result | Francisco's REAL capture | 15 numeric scores plus skin type, REAL badge, no display score anywhere | "15 skin scores plus skin type from the YouCam AI Skin Analysis API. SkinLedger stores the raw score only." | todo |
| 3 | Noise-band page | Francisco's REAL day-1 pair | Per-aspect bands; pore and acne marked "Unstable for your setup" (confirm in the app) | "Two captures three minutes apart show how much each score moves on its own. Unstable metrics are left out of verdicts." | todo (page built; capture the screenshot) |
| 4 | Timeline | SIMULATED sample profile | Shaded noise band, dashed hollow SIMULATED points, legend "Shaded band = your day-1 measurement noise. Only changes outside it count." | "Only changes outside your own noise band count. Demo history is labelled SIMULATED." | todo (P08 in progress) |
| 5 | Verdict | SIMULATED sample profile | Banner "Demo: day 14/28 check-ins are SIMULATED. Day 1 is real.", outcome card, target-aspect table, exact disclaimer inside the card | "Keep, No measurable change or Worse, decided against your own noise band." | todo (planned) |
| 6 (optional) | Privacy and delete, or routine page | No faces | "We never store your photo", delete button; or AM/PM routine by ingredient category with the SAMPLE/"general heuristics" label | "Consent first, photo never stored, delete any time." | todo (optional) |

Fallbacks if a screen does not ship: use the privacy page (6) and a second REAL screen (for example the people page with only Francisco's profile). Never fill the gap with a mock-up presented as real.
