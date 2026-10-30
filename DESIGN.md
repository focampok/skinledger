---
name: SkinLedger
description: "Is it working or not? Know before you rebuy."
colors:
  primary: "#1f6f5c"
  primary-tint: "#eef7f2"
  action-blue: "#0172ad"
  action-blue-hover: "#015887"
  warn: "#b26a00"
  warn-tint: "#fff6e5"
  danger: "#b3261e"
  danger-tint: "#fdeeee"
  neutral-ink: "#2d3138"
  body-ink: "#373c44"
  muted-ink: "#646b79"
  neutral-surface: "#f1f3f4"
  neutral-border: "#e7eaf0"
  page: "#ffffff"
  card-sectioning: "#fbfcfc"
typography:
  display:
    fontFamily: "system-ui, \"Segoe UI\", Roboto, Oxygen, Ubuntu, Cantarell, Helvetica, Arial, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.125
  headline:
    fontFamily: "system-ui, \"Segoe UI\", Roboto, Oxygen, Ubuntu, Cantarell, Helvetica, Arial, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 700
    lineHeight: 1.15
  title:
    fontFamily: "system-ui, \"Segoe UI\", Roboto, Oxygen, Ubuntu, Cantarell, Helvetica, Arial, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.175
  body:
    fontFamily: "system-ui, \"Segoe UI\", Roboto, Oxygen, Ubuntu, Cantarell, Helvetica, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "system-ui, \"Segoe UI\", Roboto, Oxygen, Ubuntu, Cantarell, Helvetica, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  control: "0.25rem"
  panel: "0.5rem"
  pill: "999px"
spacing:
  unit: "1rem"
  control-x: "1rem"
  control-y: "0.75rem"
  card: "1rem"
  section: "1.5rem"
components:
  button-primary:
    backgroundColor: "{colors.action-blue}"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    padding: "0.75rem 1rem"
  button-primary-hover:
    backgroundColor: "{colors.action-blue-hover}"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    padding: "0.75rem 1rem"
  button-secondary:
    backgroundColor: "#e7eaf0"
    textColor: "{colors.body-ink}"
    rounded: "{rounded.control}"
    padding: "0.75rem 1rem"
  chip-accent:
    backgroundColor: "{colors.primary-tint}"
    textColor: "{colors.primary}"
    rounded: "{rounded.pill}"
    padding: "0.15rem 0.55rem"
  chip-neutral:
    backgroundColor: "{colors.neutral-surface}"
    textColor: "#3c4043"
    rounded: "{rounded.pill}"
    padding: "0.15rem 0.55rem"
  card:
    backgroundColor: "{colors.page}"
    textColor: "{colors.body-ink}"
    rounded: "{rounded.control}"
    padding: "{spacing.card}"
  input:
    backgroundColor: "{colors.card-sectioning}"
    textColor: "{colors.body-ink}"
    rounded: "{rounded.control}"
    padding: "0.75rem 1rem"
---

# Design System: SkinLedger

## Overview

**Creative North Star: "The Honest Ledger"**

SkinLedger looks like a calm measuring instrument you keep in the bathroom, not a beauty brand.
The page is paper-white, the type is the system font at reading size, and the only saturated
colour is a deep green used where a measurement has produced a judgement. Everything else is
ink, rule lines and quiet grey surfaces. The interface has one job per screen and says the
uncomfortable thing ("No measurable change", "Too early") in the same weight as the good news.

The visual language is inherited almost entirely from Pico.css: 0.25rem controls, 1rem spacing,
a seven-layer neutral shadow on cards, and a blue primary action. The product's own additions are
a green accent, left-border status cards, pill chips for metadata, and tinted verdict surfaces.
The system is deliberately plain; its character comes from restraint, labelling and honest
wording rather than decoration.

**Key Characteristics:**
- Paper-white page with near-black ink and one deep-green accent.
- Status is carried by a 4-6px left border plus a tinted surface, never by gradients or icons alone.
- System sans-serif at 1rem/1.5; headings 2rem/1.75rem/1.5rem bold.
- Pico.css defaults are the substrate: 0.25rem radii, 1rem rhythm, neutral stacked shadow.
- Every data point is labelled REAL, SIMULATED or SAMPLE; the disclaimer is always present.

## Colors

A near-monochrome page interrupted by one green judgement accent and three status tints.

### Primary
- **Deep Ledger Green** (#1f6f5c): the product accent. Used on verdict "Keep" borders and
  surfaces, selected chips, the timeline band legend, product notices, and the "all good"
  capture guidance. It is the only colour that reads as "SkinLedger".
- **Green Wash** (#eef7f2): the Keep verdict surface and the accent chip background.

### Secondary
- **Pico Action Blue** (#0172ad): currently the background of every primary button and selected
  tab because Pico.css is not themed. It is an inherited framework default, not a brand colour.
  This is documented drift; new status meaning must not be built on it.
- **Action Blue Hover** (#015887): the hover state of those buttons.

### Tertiary
- **Caution Amber** (#b26a00) on **Amber Wash** (#fff6e5): "No measurable change" verdicts,
  SIMULATED banners and general cautions.
- **Signal Red** (#b3261e) on **Red Wash** (#fdeeee): "Worse" verdicts and product form errors.
- **Quiet Grey** (#5f6368) on **Grey Wash** (#f1f3f4): "Too early", "No verdict yet",
  "Check-in needed", unstable chips and mask placeholders.

### Neutral
- **Ink** (#2d3138 / #373c44): headings and body copy.
- **Muted Ink** (#646b79): secondary text, hints, footer and `<small>`.
- **Rule Line** (#e7eaf0): card borders, table rules, dividers.
- **Paper** (#ffffff): the page and card surface.
- **Sectioning Paper** (#fbfcfc): form fields and card headers.

### Named Rules
**The One Judgement Rule.** Green, amber, red and grey mean a verdict state. They never decorate a
heading, an icon or a non-verdict surface.

**The Paper Rule.** The page is flat white. Tint appears only when a state changes: verdict cards,
SIMULATED banners, form errors and unstable chips.

## Typography

**Display Font:** system-ui (with Segoe UI, Roboto, Oxygen, Ubuntu, Cantarell, Helvetica, Arial)
**Body Font:** the same system stack

**Character:** Neutral, legible, unmarketed. The type is the browser's own voice, chosen so the
app reads as a utility rather than a skincare brand and so no font request breaks the strict CSP.

### Hierarchy
- **Display** (700, 2rem, 1.125): page titles, including the verdict headline. Wraps to 2-3 lines
  at 390px, which is expected.
- **Headline** (700, 1.75rem, 1.15): section titles such as "Target aspects" and "Biggest changes".
- **Title** (700, 1.5rem, 1.175): card titles, form section titles, the verdict outcome (1.6rem).
- **Body** (400, 1rem, 1.5): all explanatory copy and table cells.
- **Label** (400, 0.875-1rem): form labels, tab buttons, metadata. Metadata uses 0.8-0.9rem
  `<small>` at muted ink.

### Named Rules
**The No New Font Rule.** No webfont is introduced without resolving the CSP and the offline PWA
constraint. The system stack is normative.

## Layout

Pico's container is the layout: full width with 1rem gutters below 576px, then 510px, 700px,
950px, 1200px and 1450px max-width tiers at 576/768/1024/1280/1536px. `main` gets 1.5rem of
vertical padding. The primary composition is a single reading column; multi-column grids appear
only above 640px (`repeat(2, 1fr)`) and 1024px (`repeat(3, 1fr)`) for timeline cards and home
product cards, and the product form's date pair splits into two columns at 640px.

Mobile is the design target: 390x844, one column, 1rem rhythm. Dense tables (verdict targets,
product log) are placed in an `overflow-x: auto` wrapper rather than restructured; their full
six-column row does not fit 390px. Page actions are inline links, not a bottom action bar.

## Elevation & Depth

Depth is Pico's single neutral stacked shadow (`--pico-box-shadow`: seven layered grey shadows,
`rgba(129,145,181,...)`), applied to every `article` card. There is no glow, no coloured shadow
and no hover lift. Verdict and banner cards replace elevation with a 4-6px coloured left border
and a tinted background, so the state reads before the shadow does.

### Shadow Vocabulary
- **Card Rest** (`box-shadow: var(--pico-box-shadow)`): the default for every `<article>`; static,
  never animated.

### Named Rules
**The Flat-At-Rest Rule.** No shadows on buttons, links, inputs or chips. Only `article` cards
carry the neutral card shadow.

## Shapes

Controls, inputs and cards share a 0.25rem radius; the mask figures and capture tips card use
0.5rem; chips are full pills (999px). The recurring silhouette is a white card with a vertical
coloured spine: a 4px left border for banners and home cards, a 6px left border for verdict cards.
Borders are hairline (0.0625rem) in Rule Line grey on a white surface. There are no rounded
"friendly" shapes larger than 0.5rem and no cut corners, overlaps or clipping.

## Components

### Buttons
- **Shape:** 0.25rem radius, 0.0625rem border, Pico's 0.75rem x 1rem padding.
- **Primary:** Action Blue (#0172ad) background with white text; `role="button"` links inherit it.
- **Hover / Focus:** background shifts to #015887 over 0.2s; focus uses the browser/Pico outline.
- **Secondary:** light grey (#e7eaf0 in the product log's End button) with body ink text.
- **Capture primary:** "Start capture" is 1.15rem text, full width up to 420px.

### Chips
- **Style:** pill, 0.15rem x 0.55rem padding, 0.78rem text, on Green Wash with Deep Ledger Green
  text (`.sl-chip`) or grey on Quiet Grey (`.sl-chip-unstable`).
- **State:** metadata only; chips are not interactive and carry the skin-type or unstable label.

### Cards / Containers
- **Corner Style:** 0.25rem.
- **Background:** Paper; verdict cards use their state wash.
- **Shadow Strategy:** the single neutral card shadow.
- **Border:** hairline Rule Line; verdict/banner cards carry a 4-6px coloured left spine instead
  of a full border.
- **Internal Padding:** 0.9-1rem.

### Inputs / Fields
- **Style:** 1px #cfd5e2 border, Sectioning Paper background, 0.25rem radius, 0.75rem x 1rem
  padding, full width. Labels are block-level and sit above the control.
- **Focus:** Pico's primary-coloured border and outline.
- **Error / Disabled:** errors are separate `.product-error` / `role="alert"` paragraphs in Signal
  Red; no inline field-level error styling exists.

### Navigation
- **Style:** a single row inside the container: bold "SkinLedger" wordmark on the left, text links
  (Home, Try it, My people, and feature-gated Timeline, Products, Routine) on the right.
- **States:** links are underlined by default. There is no active-page state and no logo link.
- **Mobile treatment:** the same inline row; at 390px the three visible labels already fill the
  width and long labels such as "My people" sit tight against the wordmark.

### Status Banners
- **Style:** full-width card with a 4px amber left spine on Amber Wash, used for SIMULATED and
  SAMPLE notices, demo notices and baseline prompts.
- **Placement:** directly under the page title, inside the reading column.

### Verdict Card
- **Style:** 6px left spine + state wash + 1rem padding, max 46rem wide, followed by a summary
  block, a six-column target table, a change list and mask figures.
- **Signal:** the outcome word is repeated as a 1.6rem line; the same word also appears as the
  card's message, so the first word is read twice in a row.

### Tabs (capture)
- **Style:** two bordered buttons in a row, both using the primary blue in the current build, with
  only `aria-selected` distinguishing them visually. The selected state is not visible.

## Do's and Don'ts

### Do:
- **Do** keep the footer disclaimer verbatim on every page and the exact disclaimer inside the
  verdict card.
- **Do** keep the REAL / SIMULATED / SAMPLE label on every data point, including chips and cards.
- **Do** use the 4px left spine + wash pattern for any state message; it is the product's one
  recurring decorative move.
- **Do** keep touch targets at least 44px and body copy at 1rem or larger.
- **Do** use `.sl-chip` for metadata and keep pills non-interactive.
- **Do** keep `aria-live` status regions on the capture flow; capture has real waiting states.

### Don't:
- **Don't** introduce a webfont, a new external origin or an inline script; the CSP forbids them.
- **Don't** extend Pico's Action Blue to a new status meaning; it is an inherited default, not a
  brand signal.
- **Don't** convey a verdict by colour alone; the word and the border must agree.
- **Don't** show or chart `ui_score` anywhere; the raw score is the only approved number.
- **Don't** add shadows to controls, chips or links.
- **Don't** add brand logos, product brands or medical language.
