# Bitaxe Baller — container image for Umbrel / Docker / self-hosted deployment.
#
# Builds the same Flask app that ships as native Mac/Windows binaries, minus
# the pywebview UI layer (containers don't have an X server / Cocoa, and the
# point of running in Docker is to access via browser from elsewhere anyway).
#
# Important runtime requirements:
#
#   - host networking is REQUIRED for:
#       (a) the LAN scanner to probe Bitaxe IPs on the host's /24
#       (b) mDNS publishing of bitaxe-baller.local
#     A bridged Docker network breaks both. Umbrel's compose template uses
#     `network_mode: host`. Plain `docker run` users should pass `--net=host`.
#
#   - a persistent volume bound to /data so config.json, logs/, and history.db
#     survive container restarts and Umbrel app re-installs.
#
#   - the data directory is set via the BITAXE_BALLER_DATA_DIR env var.
#     The compose template sets it to /data.
#
# Build:
#   docker build -t bitaxe-baller .
#
# Run (standalone Docker, not Umbrel):
#   docker run --net=host -v $PWD/data:/data \
#     -e BITAXE_BALLER_DATA_DIR=/data \
#     -e PORT=5050 \
#     bitaxe-baller

# ---------- builder stage: install deps into a venv we can copy over ----------
FROM python:3.12-slim-bookworm AS builder

# better-sqlite3-equivalent for Python (sqlite3 stdlib) needs no native deps,
# but some wheels (pynacl, websockets) prefer build tools for older Pythons.
# 3.12 has wheels for everything we use; keep this minimal.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt ./

# Install into a dedicated path we can copy clean into the final image. We
# skip pywebview entirely — it's only used in the frozen native-app code path
# (`_run_webview` in app.py, gated by `_is_frozen()`).
RUN pip install --no-cache-dir --target=/install \
        flask>=3.0 \
        requests>=2.31 \
        zeroconf>=0.131 \
        pynacl>=1.5 \
        websockets>=12.0 \
        certifi>=2024.2.2

# ---------- runtime stage: slim image, no build deps ----------
FROM python:3.12-slim-bookworm AS runtime

# Avahi-utils isn't required — zeroconf is pure Python and does the mDNS work
# itself. tini handles SIGTERM forwarding; gosu drops root → baller in
# the entrypoint after we fix bind-mount ownership.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tini \
        gosu \
    && rm -rf /var/lib/apt/lists/*

# Create the unprivileged user the entrypoint will gosu into. We do NOT
# `USER baller` here — the entrypoint must start as root so it can chown
# the bind-mounted /data (which arrives owned by root on Umbrel and many
# other environments), then it drops to uid 1000 itself.
RUN useradd --create-home --uid 1000 --shell /bin/bash baller
WORKDIR /app

# Copy installed deps + app code
COPY --from=builder /install /usr/local/lib/python3.12/site-packages
COPY --chown=baller:baller app.py /app/app.py
COPY --chown=baller:baller relay_client.py /app/relay_client.py
COPY --chown=baller:baller templates /app/templates
COPY --chown=baller:baller static /app/static
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# /data is bind-mounted by the compose template. The entrypoint fixes its
# ownership at startup (Umbrel mounts it owned by root). Source-mode app
# directory stays owned by baller.
RUN mkdir -p /data && chown -R baller:baller /app

ENV BITAXE_BALLER_DATA_DIR=/data \
    PORT=5050 \
    HOST=0.0.0.0 \
    MDNS_ENABLED=1 \
    BITAXE_BALLER_NO_AUTO_OPEN=1 \
    PYTHONUNBUFFERED=1

EXPOSE 5050

# tini reaps zombies + forwards SIGTERM; docker-entrypoint.sh chowns /data
# and gosus down to baller before exec-ing python.
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "/app/app.py"]

# Basic health check — Flask responds to /healthz once the polling thread
# is up. Generous start period because first-run might need to bootstrap
# the history.db SQLite file.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5050/healthz', timeout=4).status == 200 else 1)" || exit 1
