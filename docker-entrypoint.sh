#!/bin/sh
# docker-entrypoint.sh — fix the bind-mounted /data ownership, then drop
# privileges to uid 1000 and exec the app. Umbrel (and many other Docker
# environments) bind-mount data dirs owned by root, which an unprivileged
# user can't write to. We chown at start, then `gosu` swaps to the
# unprivileged user before the app process starts.

set -e

DATA_DIR="${BITAXE_BALLER_DATA_DIR:-/data}"

# Make sure the data dir exists and is owned by uid 1000 (the `baller`
# user the image was built with). Skip the chown if we're already that
# user — only the root case needs it.
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$DATA_DIR"
  chown -R baller:baller "$DATA_DIR"
  exec gosu baller "$@"
fi

exec "$@"
