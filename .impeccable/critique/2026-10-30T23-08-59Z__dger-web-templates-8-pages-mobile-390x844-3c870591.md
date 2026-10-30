---
target: src/skinledger/web/templates (8 pages, mobile 390x844)
total_score: 20
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 20
target_identity: "file:/home/focampo/Proyectos/skinledger/src/skinledger/web/templates (8 pages, mobile 390x844)"
timestamp: 2026-10-30T23-08-59Z
slug: dger-web-templates-8-pages-mobile-390x844-3c870591
---
# Impeccable critique — SkinLedger, 8 pages at 390x844

Method: dual-agent (A: design review · B: detector + Playwright/audit)
Targets: home, /try, /demo, sample timeline, sample product verdict, capture (pre-camera),
people list, product form. Data: public SIMULATED sample profile only.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | No active nav state; selected capture tab is invisible |
| 2 | Match System / Real World | 2 | "Aspect", "noise band", "unstable" used before definition |
| 3 | User Control and Freedom | 2 | No cancel from capture; products can only be ended, not edited |
| 4 | Consistency and Standards | 2 | "Try it" button/link/page; stock blue vs brand green |
| 5 | Error Prevention | 2 | 15 aspects accepted, 1-4 limit only after submit |
| 6 | Recognition Rather Than Recall | 2 | Chart mark meanings hidden; labels truncate |
| 7 | Flexibility and Efficiency | 2 | One rigid path; no summary/filter on 15-aspect timeline |
| 8 | Aesthetic and Minimalist Design | 2 | 15 near-identical cards; outcome repeated 2-3x |
| 9 | Error Recovery | 2 | Errors not field-level; chart retry is text only |
| 10 | Help and Documentation | 2 | Core concept has no in-place help where users act |
| **Total** | | **20/40** | **Acceptable (50%)** |

## Audit Health Score

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 1 | Dark mode drops verdict/banner text to 1.18-1.58:1; focus ring 1.75:1; charts have no value text |
| 2 | Performance | 3 | Lean shell (33-79ms) but 15 Chart.js canvases + 71KB gz chart.js load unconditionally |
| 3 | Theming | 1 | Only --sl-accent is a token; 29 literal hex values; Pico blue does all primary work; dark mode unthemed |
| 4 | Responsive Design | 2 | No page overflow, but tables hide key columns, targets <44px, 200% text makes the page 563px wide |
| 5 | Implementation Integrity | 2 | DESIGN.md documents drift but tokens are not implemented; two greens; six off-ramp sizes |
| **Total** | | **9/20** | **Poor** (light-mode contrast is otherwise strong) |

## Design Specificity Verdict

The data model and copy are authored for this product; the shell is not. Without the words and
status colors this is a stock Pico CRUD app. The two authored ideas are the 4-6px state spine +
wash and the per-person noise-band chart grammar. At 390px both are weakened: the verdict's
"Noise band" and "Outside noise?" columns are columns 5-6 of a clipped 6-column table, and the
timeline buries the story under 15 identical cards (~9,300px). The product is authored as a
measurement instrument in principle and presented as a generic list-and-form app in practice.

Deterministic scan (after DESIGN.md existed): 29 findings on templates — 26 advisory, 3 warning.
Verified: 6 real (5 token/dark drift + 1 documented exception), 23 false positives (unresolved CSS
variables reported as rgb(0,0,0), Pico's own neutral shadow and dark palette, JS-populated hidden
images). Before DESIGN.md existed the same run returned 3 generic warnings; the extra 26 are
token-map comparisons. No user-visible overlay was produced; evidence came from Playwright
measurements, not script injection into a presented browser.

## What's Working

1. The verdict card's honesty system: tint + spine + word, never colour alone, plus a visible
   "can't isolate one product" warning.
2. The noise band as a chart primitive: per-aspect shaded band, product-start hairlines,
   dashed/hollow provenance marks.
3. Copy discipline: "Keep / No measurable change / Too early", "reconsider before rebuying",
   the baseline sentence, and the in-context privacy note.
4. Labels are honest and everywhere: REAL / SIMULATED / SAMPLE on cards, charts, banners, rows.

## Priority Issues

### Cross-page

- **[P0] Dark mode makes the core verdict unreadable.** Pico flips text to #c2c7d0 but the app's
  hard-coded light washes stay. Verdict body 1.55:1, verdict h2 1.18:1, banners 1.58:1, timeline
  chip 2.72:1. Any phone on dark theme sees an unreadable answer. (app.css:166-217, 210-217;
  capture.html:42-63)
- **[P1] Brand accent unused for action.** Primary buttons, links and both capture tabs use Pico
  #0172ad; the authored #1f6f5c appears only on status. Only --sl-accent is a token; 29 hex
  literals remain. (app.css:3-5, base.html)
- **[P1] No location signal.** No active nav state, no `aria-current`; the wordmark is not a link.
  Every page looks identical in the header. (base.html:18-31)
- **[P1] Touch targets below 44px.** Nav 40px; standalone links 18-22px; checkboxes 20x20; footer
  links 18px. WCAG 2.5.8. (base.html, people.html, products_list.html, products.html)
- **[P2] Focus ring 1.75:1.** Pico replaces link outlines with a low-contrast shadow; WCAG 2.4.11
  wants 3:1.
- **[P2] Footer "Demo" link 3.64:1** at 13.33px (footer opacity 0.8 on a 5.23:1 link).

### Home (/)

- **[P1] "Your active products" is shown over the sample user's data.** The heading contradicts
  the card footer "Sample user (SIMULATED)". (index.html:17, 32)
- **[P1] The outcome is printed twice per card** ("Keep" / "Keep"; "No measurable change" /
  "No measurable change -> reconsider..."). (index.html:25-26)
- **[P1] The zero-friction path is absent above the fold.** "Try it" leads to an invite wall; the
  sample profile is not offered on Home.
- **[P2] CTA pair misaligns:** the "My people" text link sits on the tall button's baseline, not
  visually paired with it. Card titles wrap 3 lines at 390px because "(SAMPLE)" is in the h3.

### Try (/try)

- **[P1] Invite wall with no way to obtain a code.** No hint, no source, no format; only /demo
  mentions the Devpost instructions. Input is `type=text` without autocapitalize/autocorrect off.
- **[P2] The sample path is two lines of prose** wrapped around an em dash, visually weaker than
  the form. (try.html:11-15)
- **[P2] "Judges: how this demo works" links to a page that does not explain how it works.**
- **[P3] The error is above the form, not associated with the input.**

### Demo (/demo)

- **[P2] Dead end for the audience it names.** One button, three paragraphs of limits, no example,
  no 3-step tour. Judges have 1-3 minutes.
- **[P2] "Try it with your own face" appears before the sentence saying a code is required.**
- **[P3] Duplicate privacy sentence + separate Privacy link.**

### Sample timeline

- **[P1] 15 full cards, ~9,300px, no summary or grouping.** The 2-product story is invisible
  above 9,000px of scrolling; `data-order-group` is emitted but unused.
- **[P1] Chart labels truncate mid-word** ("Niacinamide seru", "Hydrating crea") and collide with
  the day-28 marker; the provenance legend is hidden (`legend.display=false`).
- **[P1] No text alternative for the values.** Canvas `role=img` + "Oiliness scores over time";
  the failure message stays `hidden` without JS, so no-JS/SR users get 15 blank cards. WCAG 1.1.1.
- **[P2] SIMULATED gold (#8a6d3b) sits next to verdict amber**, weakening the One Judgement Rule.
- **[P2] "Skin type: -" reads as a failed load.** No unstable-only filter.
- **[P3] 15 Chart.js instances render immediately** (71KB gz, no lazy loading).

### Sample verdict

- **[P0] The noise band - the product's differentiator - is off-screen at 390px.** The table is
  505px inside a 320px wrapper; 185px hidden; columns 5-6 invisible, no scroll affordance.
- **[P1] The outcome is printed three times** in the h1 block, `.verdict-outcome` and
  `.verdict-action`. "Keep" / "Keep".
- **[P1] The change list asserts "Outside noise" without the band number**, which lives only in
  the hidden column.
- **[P2] "Before and after masks" promises a section, then says masks are not shown for SIMULATED.**
- **[P2] The isolation warning is plain body text**, not the 4px amber warning card the system
  already defines.
- **[P3] No forward action; the disclaimer appears twice** (card + footer).

### Capture before camera

- **[P1] Two equal blue primaries and an invisible selected tab.** Both tabs compute to #0172ad;
  only `aria-selected` differs; plain buttons inside `role=tablist` with no `role=tab`,
  `aria-controls` or `tabpanel`.
- **[P1] The attestation gate explains itself only in small text**; the disabled Start gives no
  reason (`aria-describedby` missing).
- **[P1] The privacy reassurance is the smallest, most warning-shaped text before the camera.**
  "never stored" and "YouCam may keep it for up to 30 days" have equal weight.
- **[P2] "Guided camera is still loading..." has no progress cue.** Camera language sits below
  the primary action.
- **[P3] The tips card is duplicated in both tabs; upload tips are wrong for an upload.**
  The file input has no descriptive label.

### People list

- **[P1] The sample row is a bullet with run-on inline metadata**, visually weaker than the
  "Create a profile" primary button.
- **[P1] A real row jams six links (including Delete) into a `<small>` line** at 18-22px.
- **[P2] "People" is the wrong noun** for a personal app; no explanation of what a profile is.
- **[P3] "No profiles yet." is a bare empty state.**

### Product form

- **[P1] 15 target-aspect checkboxes at once**, on a phone, limit enforced only after submit, no
  counter, no grouping, repeated unstable hint under each affected row.
- **[P1] The form is above the product list**, so existing products and the Verdict link are
  ~2,000px below.
- **[P1] The product log is a 7-column table**; at 390px only Product/Category/Started are
  visible, and Verdict/End start at x=626, fully off-screen.
- **[P2] Three date formats in one flow** (10/30/2026 picker, 2026-09-30 table, "like 2026-10-29"
  hint). No edit or undo; only End.

## Persona Red Flags

**Casey (distracted mobile).** Invite code gets auto-capitalized; capture requires scrolling past
two blue buttons and a checkbox before Start; checked attestation is lost on reload; the verdict's
reason is behind an undiscovered horizontal scroll; 24 sub-44px targets on the product form.

**Jordan (first-timer).** Home's h1 is a question, not a product; "invite code" is never explained
and cannot be obtained on /try; /demo has no tour; "aspect", "tear trough", "unstable" arrive
undefined; the demo ends without ever showing the band number that justifies the verdict.

**Sam (screen reader/keyboard).** No skip link or `aria-current`; capture tabs are invalid ARIA;
charts expose no values and the failure message is hidden without JS; scrollable tables lack
`tabindex`/accessible names and `<th scope>`; focus ring is 1.75:1; dark-mode contrast fails AA.

## Minor Observations

- Footer repeats the full disclaimer immediately after the verdict card already contains it.
- "Skin type: -" looks like a failed load.
- Dates mix "Sep 20, 09:00 AM", "2026-09-30" and "10/30/2026".
- "Try it" names a nav link, a Home button and a page title.
- "(SIMULATED)" inside display names forces 2-3 line h1s on mobile.
- The home lede is good prose, but no visual shows the noise band.

## Questions to Consider

1. If the noise band is the product, why is its number off-screen on the verdict and its chart
   repeated 15 times? Would one band strip beside each verdict number do more than 15 charts?
2. What would this UI look like if "aspect" never appeared and the taxonomy was grouped the way
   people talk ("breakouts", "dullness", "lines")?
3. PRODUCT.md promises one action per screen; capture shows two equal blue buttons, a disabled
   third, a checkbox, a select, tips and a privacy paragraph before the camera. Which is the action?
4. If a judge has 90 seconds, should the sample profile be the hero of Home and "your own face"
   the secondary path?
5. Is "Keep / Keep / Keep" a design decision or a template artifact - and what would the verdict
   sound like as one sentence a person could say to a friend?
