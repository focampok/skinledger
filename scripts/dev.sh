#!/usr/bin/env bash
# SkinLedger dev runner.
#   scripts/dev.sh           -> app only on http://localhost:8000 (laptop testing)
#   scripts/dev.sh tunnel    -> app + fixed Cloudflare tunnel (phone testing)
#   MOCK=1 scripts/dev.sh    -> force YOUCAM_MOCK=true (no units spent)
# One Ctrl+C stops everything. The tunnel uses http2 because some networks block QUIC.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-local}"
PORT="${PORT:-8000}"
DEV_HOSTNAME="${DEV_HOSTNAME:-dev-skinledger.focampo.com}"
DEV_TUNNEL="${DEV_TUNNEL:-skinledger-dev}"

if [[ "${MOCK:-0}" == "1" ]]; then
  export YOUCAM_MOCK=true
  echo "[dev] YOUCAM_MOCK=true (no units)"
fi

pids=()
cleanup() {
  echo; echo "[dev] stopping..."
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
  echo "[dev] stopped. Tunnel closed."
}
trap cleanup EXIT INT TERM

if [[ "$MODE" == "tunnel" ]]; then
  # Rule: never open the tunnel without an invite code. Checks presence only; never prints it.
  if ! grep -Eq '^INVITE_CODE=.+' .env 2>/dev/null; then
    echo "[dev] INVITE_CODE is not set in .env. Refusing to open the tunnel." >&2
    exit 1
  fi
  if ! cloudflared tunnel info "$DEV_TUNNEL" >/dev/null 2>&1; then
    echo "[dev] Tunnel '$DEV_TUNNEL' not found. Run the one-time setup first." >&2
    exit 1
  fi
fi

# --proxy-headers so the /try rate limit sees the real client IP behind the tunnel.
uv run uvicorn skinledger.web.app:app --port "$PORT" --reload \
  --proxy-headers --forwarded-allow-ips 127.0.0.1 &
pids+=($!)

if [[ "$MODE" == "tunnel" ]]; then
  cloudflared tunnel --protocol http2 --no-autoupdate run --url "http://localhost:$PORT" "$DEV_TUNNEL" \
    >>logs/cloudflared.log 2>&1 &
  pids+=($!)
  echo "[dev] Phone URL: https://$DEV_HOSTNAME  (tunnel log: logs/cloudflared.log)"
else
  echo "[dev] Laptop URL: http://localhost:$PORT"
fi

wait -n "${pids[@]}"
