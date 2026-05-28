# Bitaxe Baller for Umbrel

This directory has everything needed to publish Bitaxe Baller as an Umbrel community app. Two files matter:

- **`docker-compose.yml`** — Umbrel-flavored compose template. Uses host networking so the LAN scanner + mDNS publishing actually work.
- **`umbrel-app.yml`** — App store manifest (name, icon, gallery, version, release notes).

The mirror under `community-store/` is the staging copy for the separate GitHub repo that gets added to Umbrel as a custom app source.

---

## How users install it (once published)

1. In the Umbrel UI: **App Store → Community App Stores → Add Custom Store**
2. Paste: `https://github.com/465media/umbrel-bitaxe-baller-store`
3. Confirm. Bitaxe Baller appears in the store.
4. Click **Install**. Umbrel pulls the image, creates `~/umbrel/app-data/bitaxe-baller/data/`, and starts the container.
5. Open via the Umbrel dashboard tile, OR direct LAN at `http://umbrel.local:5050` / `http://bitaxe-baller.local:5050` (Bonjour/Avahi).
6. Add Bitaxes via **scan** or paste IPs — same flow as the desktop app.

Data persists in `~/umbrel/app-data/bitaxe-baller/data/` (config.json, logs/, history.db). Survives reinstalls and Umbrel updates.

---

## How to publish a new version (release checklist)

### 1. Build + push the container image

The compose template pins `ghcr.io/465media/bitaxe-baller:1.12.0@sha256:...`. You need to:

```bash
# from repo root
docker build -t ghcr.io/465media/bitaxe-baller:1.12.0 .

# push (requires gh CLI logged in or a GHCR PAT)
docker push ghcr.io/465media/bitaxe-baller:1.12.0
```

Grab the resulting SHA256 from `docker push` output. **Umbrel requires the image be pinned by digest** (`@sha256:...`) for community apps — they don't accept tag-only references because tag content can change and that's an unauditable supply-chain risk.

### 2. Update the compose template with the new digest

Edit both copies (`umbrel/docker-compose.yml` and `umbrel/community-store/bitaxe-baller/docker-compose.yml`):

```yaml
image: ghcr.io/465media/bitaxe-baller:1.12.0@sha256:<NEW_DIGEST>
```

### 3. Bump version in `umbrel-app.yml` (both copies)

Match `APP_VERSION` in `app.py`. Update `releaseNotes` with a one-paragraph summary linking to the full changelog.

### 4. Push to the community-store repo

If you haven't already created the community-store repo as a separate GitHub repo, do that once:

```bash
# one-time setup
gh repo create 465media/umbrel-bitaxe-baller-store --public \
  --description "Umbrel community app store for Bitaxe Baller"
cd /tmp && git clone https://github.com/465media/umbrel-bitaxe-baller-store
```

Then for each release:

```bash
cp -r /Volumes/WDBlack/Home/Development/bitaxe-baller/umbrel/community-store/* \
      /tmp/umbrel-bitaxe-baller-store/

cd /tmp/umbrel-bitaxe-baller-store
git add .
git commit -m "v1.12.0"
git push
```

Umbrel re-reads the manifest on its next refresh; users see the **Update** button.

---

## How to test locally (without Umbrel)

```bash
# 1. Build the image
docker build -t bitaxe-baller:local .

# 2. Run with host networking + a local data dir
docker run --rm -it \
  --network host \
  -v $(pwd)/.umbrel-test-data:/data \
  -e BITAXE_BALLER_DATA_DIR=/data \
  -e PORT=5050 \
  bitaxe-baller:local

# 3. Open http://localhost:5050 — should see the empty fleet view
# 4. Add a Bitaxe by IP or scan — same as native app
```

`--network host` on Mac/Windows Docker Desktop doesn't actually expose the host's network namespace the same way it does on Linux — for full LAN-scan testing you need to run on Linux. The container will still boot and serve the UI on Mac/Windows, just the LAN scan won't see anything beyond what Docker Desktop exposes.

---

## Architectural notes

- **Why host networking is required:**
  - LAN scan probes every IP in the host's `/24` via direct HTTP — bridge networking would limit this to the Docker bridge subnet.
  - mDNS uses multicast DNS on `224.0.0.251:5353` — bridge networking doesn't forward multicast to the LAN.
- **Why the data dir is `/data`, not `~/.config/bitaxe-baller`:** Umbrel convention. Every app gets `~/umbrel/app-data/<app-id>/` on the host and mounts whatever subdirs it wants. We use `data/` consistently.
- **Why no auto-update via Sparkle:** Umbrel handles updates via its own mechanism (re-pull image, re-apply compose). The desktop Sparkle/WinSparkle flow is for native binaries only.
- **Why Pro features work the same:** the license-key + relay-client flows are HTTP-out only. Pro license validation hits `bitaxeballer.com/api/license`; the relay hits `wss://relay.bitaxeballer.com`. Both work fine through Docker on host networking.
- **Why no in-container browser:** containers don't have one. We set `BITAXE_BALLER_NO_AUTO_OPEN=1` to skip the `webbrowser.open()` call that fires in source mode.

---

## Open follow-ups

- [ ] Get the `ghcr.io/465media/bitaxe-baller` package public (default is private). Settings → Packages → Change visibility.
- [ ] Set up a GitHub Action that builds + pushes the multi-arch image (`linux/amd64`, `linux/arm64`) on each `v*.*.*` tag push, then opens a PR to the community-store repo with the bumped digest. Would let us ship Umbrel updates the same way we ship Mac/Windows updates today.
- [ ] Submit to the official Umbrel app store at github.com/getumbrel/umbrel-apps once we have ≥1 month of community-store users without incident. Official store gets the app a featured slot but requires PR review by the Umbrel team and adherence to their content policies.
