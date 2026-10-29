#!/bin/sh
# Container entrypoint: use root only to fix volume ownership, then drop to uid 10001.
#
# Railway mounts the persistent volume root-owned, so a non-root process cannot create
# the SQLite file inside DATA_DIR. Rather than run the whole app as root, this script
# starts as root (RAILWAY_RUN_UID=0), chowns DATA_DIR and LOG_DIR, and re-execs uvicorn
# as uid 10001 with setpriv. Started as a non-root user it execs uvicorn directly.
set -eu

APP_UID=10001
APP_GID=10001
APP_HOME=/home/appuser

prepare_dir() {
    dir=$1
    # Never chown a path that is not a real data directory.
    case "$dir" in
        "" | "/" | "." | "..")
            echo "entrypoint: refusing to chown '$dir'" >&2
            return 0
            ;;
    esac
    [ -d "$dir" ] || mkdir -p "$dir"
    chown -R "$APP_UID:$APP_GID" "$dir"
}

if [ "$(id -u)" = "0" ]; then
    prepare_dir "${DATA_DIR:-/data}"
    prepare_dir "${LOG_DIR:-/var/log/skinledger}"
    export HOME="$APP_HOME"
    exec setpriv --reuid="$APP_UID" --regid="$APP_GID" --init-groups \
        uvicorn skinledger.web.app:app \
        --host 0.0.0.0 \
        --port "${PORT:-8000}" \
        --proxy-headers \
        --forwarded-allow-ips='*' \
        --no-access-log
fi

exec uvicorn skinledger.web.app:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --no-access-log
