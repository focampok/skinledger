---
target: src/skinledger/web/templates (8 pages, mobile 390x844)
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:/home/focampo/Proyectos/skinledger/src/skinledger/web/templates (8 pages, mobile 390x844)"
timestamp: 2026-10-31T00-58-13Z
slug: dger-web-templates-8-pages-mobile-390x844-3c870591
---
# Impeccable AFTER critique — SkinLedger, 8 pages at 390x844

Method: dual-agent (A: design review · B: detector + Playwright/audit)
Targets: home, /try, /demo, sample timeline, sample verdict, capture (pre-camera), people,
product form. Data: public SIMULATED sample profile only.
Screenshots: docs/screenshots/p16b/after/ (8 light, home/verdict dark).

## Design Health Score (after)

| # | Heuristic | Score | Key issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | No active nav state; camera-loading reason below the disabled Start |
| 2 | Match System / Real World | 3 | Core terms explained after the first click; ISO dates |
| 3 | User Control and Freedom | 2 | No cancel/stop during analysis; reload loses the status view |
| 4 | Consistency and Standards | 2 | Pico secondary is a second hue; dates split; SAMPLE vs SIMULATED |
| 5 | Error Prevention | 3 | Attestation, cap, consent, upload validation are solid |
| 6 | Recognition Rather Than Recall | 2 | Product key detached from charts; no starting set in the form |
| 7 | Flexibility and Efficiency | 3 | Sample bypass, tabs, lazy charts, Numbers fallback |
| 8 | Aesthetic and Minimalist | 3 | Restrained; timeline preamble and repeated verdict data add air |
| 9 | Error Recovery | 3 | Friendly copy, Retry, upload fallback |
| 10 | Help and Documentation | 2 | No glossary for the core idea; invite hint leaks Devpost context |
| **Total** | | **26/40** | **Acceptable, up from 20/40** |

## Audit Health Score (after)

| # | Dimension | Score | Key finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 3 | Text AA; summary focus ring 1.69:1 light / 2.61:1 dark; products h1→h3 |
| 2 | Performance | 3 | Light and error-free; 3 charts initially, 15 after expand; Pico+htmx on every page |
| 3 | Theming | 4 | Light/dark token system consistent; all sampled contrasts pass |
| 4 | Responsive Design | 4 | No overflow in either scheme, including 15 expanded cards |
| 5 | Implementation Integrity | 3 | Behaviours, CSP, labels verified; DESIGN.md/sidecar were stale |
| **Total** | | **17/20** | **Good, up from 9/20** |

Post-review fixes (verified, not re-scored): summary focus ring replaced with the opaque token
(6.02:1 light / 10.03:1 dark); products heading order h1→h2→h3; DESIGN.md and sidecar refreshed
to the shipped tokens/components.

## Detector

22 findings — 19 advisory `design-system-color`, 2 warning `broken-image`, 1 warning `dark-glow`.
All 22 verified false positives: unresolved CSS variables reported as black; two hidden
JS-populated preview images; Pico's neutral card shadow. The 4 true positives at the previous
run were dark-token documentation drift, now fixed. Before: 29 findings, 6 real.

## Specificity verdict

Authored in the core, generic in the shell. The verdict + timeline pair now carries a real
product language: the three-line mobile target row, the noise-band chart, the product key,
"Product targets first". Home, /try and /demo still argue in prose; the differentiator is not on
the first screen. Specificity ~6/10.

## Strengths

1. Verdict mobile rows: label, change, band, Outside/Within chip with direction, baseline→check-in.
2. Voice system: "No measurable change", "Unstable, not used", "Take 2 baseline captures first".
3. Privacy and consent placement at the point of handling.

## Remaining issues

### P0
None.

### P1
- **Home does not show the noise band.** The first screen promises "your own measurement noise"
  but has no visual of it; a judge must click twice. (index.html)
- **"Improved/worse" depends on the engine's global higher-is-better assumption.** The verdict
  engine treats every positive delta as improved and every negative delta as worse
  (verdict.py:440-500). If YouCam polarity differs for oiliness/acne/redness, the words are
  publicly wrong. Verify per aspect or use neutral "score up/down".

### P2 (selection)
- Pico secondary (#5d6b89 light / #969eaf dark) is a second hue; map it to ink/neutral.
- Dates split between "Oct 28" and "2026-10-18".
- SAMPLE vs SIMULATED are used without teaching the difference.
- Nav has no active state; the wordmark is not a link; Timeline/Products/Routine are off-nav.
- Timeline: two screens of preamble; the product key is detached from later charts.
- Capture: pre-camera dead state; no cancel/resume; "We never store" needs its subject.
- Verdict: the product name is louder than the outcome; the sample verdict dead-ends.
- Product form: 15 targets with no recommended starting set; submit below a long form.

### P3
- Footer disclaimer size; duplicated in-card disclaimer (mandated).
- Touch comfort below 44px for nav/content/footer links (WCAG 2.5.8 AA is met via exceptions).
- Chart failure when Chart.js itself fails to load leaves blank canvases.
