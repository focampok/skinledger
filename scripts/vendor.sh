#!/usr/bin/env bash
# Download the pinned front-end libraries into src/skinledger/web/static/vendor/.
# Versions are fixed here on purpose; re-run only when a version is bumped.
set -euo pipefail

HTMX_VERSION="2.0.4"
CHARTJS_VERSION="4.4.7"
PICO_VERSION="2.0.6"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/src/skinledger/web/static/vendor"
mkdir -p "$VENDOR"

curl -fsSL "https://unpkg.com/htmx.org@${HTMX_VERSION}/dist/htmx.min.js" -o "$VENDOR/htmx.min.js"
curl -fsSL "https://unpkg.com/chart.js@${CHARTJS_VERSION}/dist/chart.umd.js" -o "$VENDOR/chart.umd.js"
curl -fsSL "https://unpkg.com/@picocss/pico@${PICO_VERSION}/css/pico.min.css" -o "$VENDOR/pico.min.css"

curl -fsSL "https://unpkg.com/htmx.org@${HTMX_VERSION}/LICENSE" -o "$VENDOR/htmx.LICENSE"
curl -fsSL "https://unpkg.com/chart.js@${CHARTJS_VERSION}/LICENSE.md" -o "$VENDOR/chartjs.LICENSE"
curl -fsSL "https://unpkg.com/@picocss/pico@${PICO_VERSION}/LICENSE.md" -o "$VENDOR/pico.LICENSE"

printf 'pinned: htmx %s, chart.js %s, pico %s\n' "$HTMX_VERSION" "$CHARTJS_VERSION" "$PICO_VERSION"
