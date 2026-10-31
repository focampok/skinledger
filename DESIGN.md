---
name: SkinLedger
description: "Is it working or not? Know before you rebuy."
colors:
  page: "#FAF7F2"
  stone: "#F1ECE4"
  stone-deep: "#E8E1D6"
  ink: "#2B2A28"
  body: "#3B3833"
  muted: "#66615A"
  hairline: "#E2D9CD"
  primary: "#1F6F5C"
  primary-deep: "#17594A"
  primary-wash: "#E7EFEA"
  sand: "#D8C6A6"
  sand-wash: "#F4EDE1"
  rose: "#C4A09A"
  rose-wash: "#F6E9E6"
  warn: "#8A5514"
  warn-wash: "#F4E8D4"
  danger: "#A33A32"
  danger-wash: "#F7E5E1"
  neutral-ink: "#4A4640"
  neutral-wash: "#EFEAE1"
  dark-page: "#1C1A17"
  dark-stone: "#25221E"
  dark-stone-deep: "#2E2A25"
  dark-ink: "#F2EDE5"
  dark-body: "#DCD5CA"
  dark-muted: "#B3AA9E"
  dark-hairline: "#3A352F"
  dark-accent: "#8FC7B4"
  dark-accent-deep: "#A8D8C8"
  dark-neutral-wash: "#2A2622"
  dark-neutral-ink: "#CFC7BB"
  dark-sand-wash: "#332C21"
  dark-rose-wash: "#352624"
  dark-warn: "#E0B36A"
  dark-danger: "#E89A90"
typography:
  display:
    fontFamily: "Fraunces, Georgia, 'Times New Roman', serif"
    fontSize: "clamp(2.25rem, 6vw, 3.5rem)"
    fontWeight: 500
    lineHeight: 1.08
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Fraunces, Georgia, 'Times New Roman', serif"
    fontSize: "clamp(1.6rem, 3vw, 2rem)"
    fontWeight: 500
    lineHeight: 1.15
    letterSpacing: "-0.005em"
  title:
    fontFamily: "Fraunces, Georgia, 'Times New Roman', serif"
    fontSize: "1.25rem"
    fontWeight: 500
    lineHeight: 1.25
  body:
    fontFamily: "Inter, system-ui, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Inter, system-ui, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.01em"
rounded:
  control: "12px"
  card: "16px"
  panel: "16px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    padding: "14px 24px"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    padding: "14px 24px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "14px 24px"
  chip:
    backgroundColor: "{colors.stone}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "4px 12px"
  card:
    backgroundColor: "{colors.page}"
    textColor: "{colors.body}"
    rounded: "{rounded.card}"
    padding: "24px"
  input:
    backgroundColor: "{colors.page}"
    textColor: "{colors.body}"
    rounded: "{rounded.control}"
    padding: "14px 20px"
---

# Design System: SkinLedger

## Overview

**Creative North Star: "The Quiet Lab"**

SkinLedger should read like the printed report of a high-end Seoul skincare laboratory: warm
ivory paper, stone panels, one deep sage accent, a refined serif for the things you read and a
quiet sans for the things you operate. It is clinical without being cold, premium without
selling anything. The interface never performs wellness; it presents a measurement, a band and
an honest answer with the calm of a lab report.

The core visual idea is the noise band: a line inside a soft sand band, labelled. It is the one
graphic the product owns, and it appears on the home screen, the timeline and the verdict. Sand
and dusty rose are atmosphere only; they never carry a verdict. Sage means action and Keep,
warm amber means "no measurable change", warm red means "worse", and warm stone means "not
enough evidence yet". Every label is still honest: REAL, SIMULATED or SAMPLE.

This is a refinement of the incumbent system, not a marketing site. The monochrome honesty and
the status language stay; the paper turns warm, the headings gain a serif voice, the cards gain
soft radius and hairline rules, and the layout opens up on tablet and laptop instead of remaining
a narrow mobile column.

**Key Characteristics:**
- Warm ivory page, stone surfaces, ink text, one deep sage accent.
- Fraunces display serif for headings; Inter for UI and body; tabular figures for every number.
- Sand band, sage line, hairline grid: the noise band is the signature graphic.
- 12–16px card radii, full-pill chips and segmented control, 1px warm hairlines, no decorative shadow.
- Generous 8/12/16/24/32/48 spacing; 1120px maximum line length with real margins.
- Dark mode is warm charcoal (#1C1A17), never black.

## Colors

A warm paper palette with one saturated sage accent and two quiet highlights.

### Primary
- **Deep Sage** (#1F6F5C): primary buttons, links, focus, the Keep verdict spine and the chart
  line. It is the only saturated colour that carries meaning.
- **Sage Deep** (#17594A): primary hover and pressed states.
- **Sage Wash** (#E7EFEA): Keep surfaces and soft selected states.

### Secondary
- **Sand** (#D8C6A6) on **Sand Wash** (#F4EDE1): the noise-band fill, the small home chart and
  editorial highlight surfaces. Never text, never a verdict.
- **Dusty Rose** (#C4A09A) on **Rose Wash** (#F6E9E6): a rare editorial highlight (for example a
  quiet rule or a non-status note). Never text, never a verdict.

Sand and rose are atmosphere. They must not be used to say Keep, Worse or No change.

### Tertiary
- **Warm Amber** (#8A5514) on **Amber Wash** (#F4E8D4): No measurable change, baseline prompts
  and caution banners.
- **Warm Red** (#A33A32) on **Red Wash** (#F7E5E1): Worse and form errors.
- **Warm Stone Ink** (#4A4640) on **Stone Wash** (#EFEAE1): Too early, No verdict yet,
  Check-in needed, unstable chips.

### Neutral
- **Warm Ivory** (#FAF7F2): the page.
- **Stone** (#F1ECE4): cards, side panels and soft surfaces.
- **Stone Deep** (#E8E1D6): pressed surfaces, neutral chips, table headers.
- **Ink** (#2B2A28): headings and primary text.
- **Body** (#3B3833): body copy.
- **Muted Warm Grey** (#66615A): hints, metadata, footer.
- **Hairline** (#E2D9CD): 1px borders, table rules and dividers.

### Dark scheme
- **Page** (#1C1A17), **Stone** (#25221E), **Stone Deep** (#2E2A25), **Ink** (#F2EDE5),
  **Body** (#DCD5CA), **Muted** (#B3AA9E), **Hairline** (#3A352F).
- **Accent Ink** (#8FC7B4) for links, focus and the primary fill in dark; **Accent Deep**
  (#A8D8C8) for its hover; the dark primary button uses ink-on-sage (#1C1A17 on #8FC7B4), not white.
- **Sage Wash** (#27332D), **Amber Wash** (#33281A), **Red Wash** (#35211F).
- **Neutral Wash** (#2A2622) with **Neutral Ink** (#CFC7BB); **Sand Wash** (#332C21);
  **Rose Wash** (#352624).
- Charts read `--sl-chart-*`; the sage line, sand band, hairline grid and warm product marks all
  have dark counterparts.

### Named Rules
**The One Judgement Rule.** Sage, amber, red and warm stone mean a verdict state. Sand and rose
never do.

**The Paper Rule.** The page is warm ivory. Stone panels group content; tinted surfaces appear
only when a state changes.

**The No Decorative Gradient Rule.** Gradients are not used as decoration. A single subtle tonal
wash may sit inside the noise-band visual, where it represents the band.

## Typography

**Display Font:** Fraunces Variable (OFL), fallback Georgia, serif
**Body/UI Font:** Inter Variable (OFL), fallback system-ui

**Character:** Fraunces is a contemporary old-style serif with optical-size and soft/wonk axes.
Pinned to `opsz 144`, `SOFT 0`, `WONK 0` and weights 400–600, it reads precise and warm — a lab
report with a human hand, not a wedding invitation. Inter supplies a neutral, highly legible UI
voice and true tabular figures; it disappears behind the numbers, which is the point.

### Files and loading
- `/static/fonts/fraunces-latin.woff2` — 67.3 KB, variable `opsz 9–144`, `wght 400–600`, Latin subset.
- `/static/fonts/inter-latin.woff2` — 48.3 KB, variable `wght 400–600`, Latin subset.
- Total: **115.6 KB** (limit 150 KB). `font-display: swap`. `font-src 'self'` for app pages; the
  capture page keeps its existing Camera Kit font exception unchanged.

### Hierarchy
- **Display** (Fraunces 500, clamp 2.25–3.5rem, 1.08): home hero and the verdict outcome.
- **Headline** (Fraunces 500, clamp 1.6–2rem, 1.15): section titles and page headings.
- **Title** (Fraunces 500, 1.25rem, 1.25): card titles, product names, target names.
- **Body** (Inter 400, 1rem, 1.6): all explanatory copy. Maximum 70ch.
- **Label** (Inter 500, 0.8125rem, 1.4): metadata, chips, form labels, eyebrows.
- **Numbers** (Inter 500–600 with `font-variant-numeric: tabular-nums`): scores, bands, dates,
  check-in days, units.

### Named Rules
**The Two Voices Rule.** Serif is for reading and for the answer; sans is for operating and for
numbers. Never use the serif for form fields, buttons or data cells.

**The Tabular Numbers Rule.** Every score, band, date and count uses tabular figures.

## Layout

The content column is **1120px maximum**, with 24px gutters at 390px, 32px at 768px and 48px at
1440px. The design is verified at 390×844, 768×1024 and 1440×900.

- **Mobile (390):** one column. Cards stack; the target rows stack; the timeline shows three
  chart cards with a Show-all toggle; the product form groups stack; the segmented control is a
  full-width pill track.
- **Tablet (768):** two-column home hero; verdict summary above the target list; timeline two
  columns; product form groups two columns; people two cards per row.
- **Laptop (1440):** home hero is two columns (text + noise-band visual); verdict puts the summary
  card beside the target list; timeline is a 2–3 column chart grid; the content is centred in the
  1120px column with real margins, never a mobile column floating in an empty page.

The product form, people grid, timeline grid and home product cards switch to two columns at
640px and three at 1024px where the content allows. The verdict summary uses a sticky side card
only at ≥1024px.

## Elevation & Depth

The system is flat at rest. Cards are separated by a 1px warm hairline and a stone surface, not a
shadow. One exception: the home noise-band visual and the verdict summary card may carry a single
very soft ambient shadow (`0 1px 2px rgba(43,42,40,0.04), 0 12px 32px rgba(43,42,40,0.05)`) to
lift the two moments that carry the product idea. No coloured shadow, no glow, no glass.

### Named Rules
**The Flat-At-Rest Rule.** No shadow on buttons, chips, inputs, table rows or ordinary cards. The
hero visual and the verdict summary are the only lifted surfaces.

## Shapes

Controls use 12px radii, cards and panels 16px, chips and the segmented control are full pills
(999px). Borders are 1px warm hairline. The recurring silhouette is a warm ivory or stone panel
with a generous 24px interior and a fine rule; status cards add a 3px left spine in their state
colour. No cut corners, no overlaps, no clipping.

## Components

### Buttons
- **Shape:** 12px radius, 14px × 24px padding, minimum height 44px.
- **Primary:** Deep Sage (#1F6F5C) with white text; hover Sage Deep (#17594A); focus 2px sage
  outline with 2px offset. In dark, sage ink fill (#8FC7B4) with warm charcoal text.
- **Secondary:** transparent with Ink text and a 1px Hairline border; hover Stone fill. Never a
  second accent colour.
- **Disabled:** warm stone fill, muted text, `cursor: not-allowed`.

### Chips
- **Style:** full pill, 4px × 12px padding, Inter 500 0.8125rem, Stone or Stone Deep background,
  Ink text. Status chips use their state wash and state ink.
- **State:** metadata only; never interactive. SAMPLE/SIMULATED chips sit beside titles.

### Cards / Panels
- **Corner:** 16px.
- **Background:** Warm Ivory or Stone.
- **Border:** 1px Hairline.
- **Padding:** 24px (16px on mobile).
- **Shadow:** none at rest; the hero visual and verdict summary may use the one soft ambient shadow.

### Inputs / Fields
- **Style:** 1px Hairline border, Ivory background, 12px radius, 14px × 20px padding, Inter.
- **Focus:** 2px sage outline with 2px offset; the border stays hairline.
- **Error:** warm red text and a red wash block with `role="alert"`; never colour alone.

### Navigation
- **Style:** wordmark in Fraunces 500, 1.25rem, Ink; links in Inter 500, 0.9375rem, Muted.
- **States:** the current page uses Ink text and a 2px sage underline (`aria-current="page"`);
  hover uses Ink. The wordmark links home.
- **Mobile:** the same row with 44px link hit areas; no hamburger until six or more items.

### Segmented control (capture)
- **Track:** full-pill Stone background, 4px inner padding, 1px Hairline border.
- **Segment:** full pill, 44px, Inter 500; selected is Ivory with Ink text and a hairline border;
  unselected is transparent with Muted text.
- **Behaviour:** unchanged tab semantics and roving tabindex.

### Verdict card
- **Summary:** a Stone panel with the outcome word in Fraunces Display, one sentence in Inter,
  the window and the in-card disclaimer. On laptop it sits beside the target list.
- **Targets:** each target is a warm Ivory card with 16px radius, 1px hairline, the aspect in
  Fraunces Title, the change in tabular Inter, a `Noise band ±x` line and a pill direction chip.
  Desktop uses a refined table inside the same panel language at ≥768px.
- **Status:** 3px state spine on the summary card; the warnings use the amber wash and spine.
- **Masks:** shown only for REAL captures.

### Timeline
- **Summary:** stone strip with counts and latest check-in; the score-direction line below it.
- **Product key:** numbered swatch with the same muted dash as the chart, full product name and
  date; on laptop it sits beside the chart grid.
- **Cards:** Ivory cards with serif titles, a 1px hairline, a sand band and sage line; the first
  three aspects show by default with a pill Show-all control after them.
- **Numbers:** a `<details>` tabular table in Inter, 0.875rem, as the no-JS fallback.
- **Charts:** sage line, sand band, hairline grid, muted product marks, date-only axis, 12px
  tabular tick labels.

### Product form
- The product list comes first; "Add a product" is an ivory disclosure panel with a hairline
  below it, while its target groups sit on stone.
- Four grouped fieldsets on stone, 16px radius, 1px hairline; the counter and score-direction
  note sit above the groups. At four targets, unchecked rows mute and disable.

### People
- Stone cards with the name in Fraunces Title and one primary sage action. The sample card
  carries a SAMPLE/SIMULATED pill; a real profile's Delete sits in a separated warm-red text row.

### Footer
- Warm ivory, 1px hairline top; the verbatim disclaimer in Inter 0.875rem Muted, then one link
  line: Privacy · Powered by YouCam API · Demo.

### Noise-band visual (signature)
- A 1.5px sage line inside a soft sand band on ivory, with a hairline baseline, no axis labels
  except two small dates, and the label `SAMPLE` in a stone pill. Static SVG, no animation, no
  photo, no face. It appears above the fold on home and beside the verdict summary.

## Do's and Don'ts

### Do:
- **Do** keep the footer disclaimer verbatim on every page and the exact disclaimer inside the
  verdict card.
- **Do** keep REAL / SIMULATED / SAMPLE visible on every data point.
- **Do** keep the noise-band visual and the tabular numbers as the product's signature.
- **Do** use Fraunces for reading and Inter for operating and for every number.
- **Do** use sand and rose as atmosphere only; never as a verdict signal.
- **Do** keep 44px targets, 2px sage focus rings and 4.5:1 text contrast on ivory and dark.
- **Do** open the layout to two and three columns on tablet and laptop.

### Don't:
- **Don't** add decorative gradients, glassmorphism, glow, coloured shadows or emoji.
- **Don't** use stock photos, faces, testimonials, press logos or product brands.
- **Don't** use luxury superlatives ("revolutionary", "luxurious", "miracle").
- **Don't** introduce a second accent colour; sage is the only action and Keep colour.
- **Don't** use sand or rose to say Keep, Worse or No change.
- **Don't** use the serif for buttons, inputs or data cells.
- **Don't** add a webfont beyond the two self-hosted OFL families; no external font origins on
  app pages (the capture page keeps its existing Camera Kit exception).
- **Don't** show or chart `ui_score`; the raw score is the only approved number.
