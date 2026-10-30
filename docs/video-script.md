# SkinLedger: demo video script (target 2:20–2:40)

Length rule: 1–3 min on YouTube (unlisted or public). Voice-over is about 310 words (≈ 2:15 at 140 wpm, ≈ 2:30 with pauses over screen action). Read it aloud once with a timer before recording; add pauses if under 2:20, trim if over 2:45.
Only Francisco's face. No music (silence plus voice-over). No third-party brands or logos in frame. English voice-over, English subtitles.

## Script

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:15 | Francisco at a mirror-style framing, phone in hand (or the phone screen with the SkinLedger home). Title card text: "Is it working or not?" | "Four weeks into a new serum, I still couldn't tell if it was working, or if I was just hoping. The mirror changes with the light. So I built SkinLedger." |
| 0:15–0:35 | Home screen on the phone. Tagline "Is it working or not? Know before you rebuy." Footer "Powered by YouCam API". Short on-screen text: "YouCam AI Skin Analysis API + YouCam JS Camera Kit". | "SkinLedger helps you decide before you rebuy. It uses the YouCam AI Skin Analysis API, fifteen skin scores plus skin type per selfie, and the YouCam JS Camera Kit for guided capture." |
| 0:35–1:05 | Phone: consent screen → tick "This is my own face and I am 18 or older." → three-bullet tips card → Camera Kit opens → the guidance line and the Position / Light / Angle chips turn green one by one → "Hold still..." in green → capture → "Analyzing…" → result with 15 scores and skin type, badge REAL. | "Each person gives consent first, adults only. The Camera Kit guides light, distance and pose, one instruction at a time, so captures stay comparable week to week. It takes the photo itself once my position, light and angle are all good. The analysis comes back with fifteen scores. I store the raw score, never the display score, and never the photo." |
| 1:05–1:10 | Quick cut: upload tab on the capture page (or the 45-second "Having trouble? Upload a selfie instead" link), Francisco's own selfie, same three tips. Text: "Photo analyzed, never stored." | "Friends can try it from a link too, or fall back to a plain selfie if the camera won't cooperate. Same consent, same caps. The photo is analyzed and never stored." |
| 1:10–1:40 | Noise-band page for Francisco's real day-1 pair. Highlight the bars for pore, acne, radiance; then the grey chips "Unstable for your setup" on pore and acne. Overlay: "Day 1: two captures, 3 minutes apart, same light." | "Here is what matters. On day one I took two captures, three minutes apart, same light, same face. Pore moved seventeen points, acne fifteen, radiance eight. The scores move on their own. So SkinLedger builds a noise band for each aspect, and when a band is wider than ten points, it marks that metric 'Unstable for your setup' and leaves it out of verdicts. It tells you which metrics are reliable for you, before it gives a verdict." |
| 1:40–2:10 | Timeline of the sample profile: shaded band, dashed hollow points. Banner: "Demo: day 14/28 check-ins are SIMULATED. Day 1 is real." Then the verdict cards: "Keep" and "No measurable change → reconsider before rebuying", each with the SIMULATED badge. | "Over time, each aspect gets a timeline, with your noise band shaded. Only changes outside the band count. A word of honesty: these day-fourteen and day-twenty-eight check-ins are simulated. Day one is real. You can see it on screen. A verdict is Keep, or no measurable change, reconsider before rebuying, or worse, pause and consult." |
| 2:10–2:20 | Routine page: AM and PM cards with ingredient categories, generic shopping list with checkboxes. Label "General cosmetic heuristics". | "From your lowest scores, SkinLedger suggests a morning and evening routine by ingredient category, with a generic shopping list. No brands." |
| 2:20–2:35 | Privacy page, People page with "Delete this person". Footer with the exact disclaimer, large enough to read (hold 4 s). Closing card: "SkinLedger · Powered by YouCam API · skinledger.focampo.com". | "Everything needs consent, the photo is never stored, and you can delete your profile at any time. Cosmetic skin insights, not a medical diagnosis. SkinLedger: is it working or not? Know before you rebuy. Powered by YouCam API." |

Required phrases, aloud: "YouCam AI Skin Analysis API" (0:15 segment), "YouCam JS Camera Kit" (0:15 segment), "simulated" (1:40 segment). On screen: the word SIMULATED on the banner and on each verdict badge, from 1:40 to 2:10.

If a segment's feature did not ship, cut its row and shorten the voice-over; never show a mock-up as real (see `requirements-matrix.md`, Open items).

## Shot list
1. **Mirror opener** (landscape or vertical, 1080p): Francisco's face, natural light, neutral background. 5 s.
2. **Phone screen recordings** (vertical, native screen recording): home, consent, Camera Kit capture, result. Use the real REAL day-1 data.
3. **Camera Kit capture over the shoulder** (optional): phone held in frame so the guided capture is visibly on the target device. Only Francisco's face.
4. **Upload try page**: Francisco's own selfie only.
5. **Noise-band page**: screen capture on laptop or phone, zoom into the pore and acne bars and the "Unstable for your setup" chips.
6. **Timeline and verdict screens** of the public SIMULATED sample profile (or of his profile with attached SIMULATED history). Keep the banner in frame.
7. **Routine and shopping list**.
8. **Privacy page and delete**.
9. **Closing card**: text on a plain background.

## Recording checklist
- [ ] Orphan test profile (person 6) deleted; People page shows only Francisco and the sample profile.
- [ ] No family member in frame, in a reflection, in the background or in any screenshot or profile name.
- [ ] Phone on airplane mode with Wi-Fi back on, or Do Not Disturb on; no notifications.
- [ ] Notification previews, bookmarks, extra tabs and the browser profile name hidden or cleared; no third-party logos visible (cover product labels, close other apps).
- [ ] URL bar shows only `skinledger.focampo.com`; no query strings, invite code or admin token visible. Do not show `/admin/usage?token=…`.
- [ ] Even, front light, no window behind you; phone at eye level; same spot as the Camera Kit captures.
- [ ] 1080p, vertical for phone clips; screen recording at the phone's native resolution.
- [ ] Quiet room, microphone close; no music. Read the script once with a timer before recording.
- [ ] English subtitles added (YouTube auto-captions reviewed, or an uploaded .srt).
- [ ] Say "simulated" aloud and show SIMULATED on screen for every day-14/28 element.
- [ ] Disclaimer readable for at least 4 s.
- [ ] Final length between 2:15 and 2:45 (limit 3:00).
- [ ] Upload to YouTube (unlisted or public), set title "SkinLedger: Is it working or not? (YouCam API Skin AI Hackathon)", paste the link into Devpost and the repo README.
- [ ] Optional bonus posts are made by Francisco himself (see requirements-matrix C1).
