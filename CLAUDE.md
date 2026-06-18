# Bitaxe Baller

**v1.16.3** — Flask app + browser dashboard for monitoring and tuning Bitaxe Gamma (BM1370) miners on the local network. Two pages: a compact scannable home view, plus a per-device detail page for tuning + pool config. Built-in LAN scanner auto-discovers new miners. Inline tooltips throughout. Single shared stylesheet and JS helper file under `static/`. The web app itself has no build step (vanilla JS, no framework) — desktop packaging is a separate PyInstaller pipeline under `build/`.

> **This Flask app is the core of a 5-channel product, not the whole thing.** Don't trust version numbers in docs — verify against `git`/`gh` first (the docs have drifted before). See the persisted memory files for the full picture: `project-ecosystem-map`, `release-process`, `feedback-keep-docs-current`.

## Ecosystem & distribution channels

The product ships through five channels, spanning three repos:

| Channel | Where it's built / lives |
|---|---|
| macOS desktop (signed + notarized DMG) | `build/` here — local `build/build-mac.sh` + `release-mac.sh` (needs Apple notary creds + Ed25519 key) |
| Windows desktop (Authenticode-signed EXE) | `build/` here — built in CI (`.github/workflows/build-windows.yml`) on tag push |
| Umbrel self-host (Docker + community store) | `umbrel/` here + the separate repo `465media/umbrel-bitaxe-baller-store`; image is built by `build-docker.yml` |
| iOS app (live, App Store v1.2.x) | Dedicated **private** repo `465media/bitaxe-baller-mobile` — Capacitor, relay client |
| Android app (live, Play Store) | Same repo — one Capacitor codebase covers both platforms |

Mobile has its own version line (1.2.x), independent of the dashboard (1.16.x). It was extracted (2026-06-18) from the old `feat/mobile-capacitor` branch of this repo, which is now superseded.

Other repos: `465media/bitaxe-baller-mobile` (private — Capacitor iOS+Android) · `465media/bitaxe-baller-site` (private — bitaxeballer.com marketing, download tracker, license server `/api/license`, leaderboard, **appcast hosting**) · `465media/umbrel-bitaxe-baller-store` (public — Umbrel community store).

**Relay** (`relay/` here, deployed at `relay.bitaxeballer.com`): a dumb in-memory WebSocket router that lets remote browsers and the mobile apps reach a user's LAN dashboard. Desktop opens an outbound WSS; clients route by license key. All product logic and safety bounds stay in the local app. It is the spine that connects desktop ⇄ remote ⇄ mobile.

**Releasing** is a defined multi-step sequence (version-bump checklist → tag → CI for Win/Docker/Discord → local Mac build + appcast merge → separate Umbrel digest bump). The full procedure is in the `release-process` memory file — follow it; the steps are order-sensitive.

## Run

```bash
source venv/bin/activate
python app.py                     # port 5050 (no sudo)
sudo $(which python) app.py       # port 80 (clean URLs, e.g. http://bitaxe-baller.local)
```

The app prefers port 80 if it can bind it (yields cleaner URLs since browsers default to 80 for `http://`), and falls back to 5050 when it can't (typical when not running as root). Set `PORT=...` to override and skip the auto-pick.

The startup banner prints every URL the dashboard is reachable on:
- `http://localhost[:port]` — this machine
- `http://<lan-ip>[:port]` — auto-detected LAN IP, reachable from any device on the network
- `http://bitaxe-baller.local[:port]` — published via mDNS / Bonjour

## Architecture

```
app.py                       # Flask backend
templates/
  dashboard.html             # home page — compact device cards
  device.html                # per-device detail page
static/
  style.css                  # all CSS, shared by both pages
  common.js                  # shared JS: theme toggle, toast, api(), formatters, charts
logs/                        # per-device daily CSV (gitignored)
config.json                  # device list (gitignored)
```

- `app.py` — Flask backend. Polls each device's `/api/system/info` every 5s in parallel via ThreadPoolExecutor. In-memory state behind a lock; device list persists to `config.json`. Publishes the dashboard as an mDNS service via `zeroconf`. Computes per-device tuning recommendations from live telemetry on every summary call. Each device summary carries a `severity` field (max severity of actionable recs) used for the home-card health border.
- `templates/dashboard.html` — home page. Renders one compact card per device from `/api/devices`. Whole card is an `<a href="/device/<ip>">`. Card class includes `health-crit | health-warn | health-good | health-good` (border tint) plus an offline override.
- `templates/device.html` — detail page. Polls `/api/device/<ip>` every 5s. Owns all the heavy controls: tune panel (presets + manual + fan), pool config form (primary + fallback), full charts, event log.
- `static/common.js` — `applyThemeUI`, `toast()`, `api()`, formatters (`formatDiff`, `formatNum`, `fmtUptime`, `fmtTime`, `escapeHtml`), severity-class helpers (`tempClass`, `effClass`, `hwErrClass`), chart drawing (`drawChart`, `drawTempChart`), and the **tooltip primitive** (event-delegated, listens for `[data-tip]` attributes anywhere in the DOM — works on dynamically rendered nodes without re-binding).
- Theme: dark / light variables on `:root[data-theme="dark|light"]`. Toggle button in header on both pages, persisted in `localStorage`. The inline `<script>` at the top of each page applies the saved theme synchronously to avoid a flash.

## Bitaxe API reference (device → us)

- `GET /api/system/info` — full status JSON, including primary + fallback stratum config
- `PATCH /api/system` — body keys for tuning: `frequency`, `coreVoltage`, `fanspeed`, `autofanspeed`. Body keys for pool: `stratumURL`, `stratumPort`, `stratumUser`, `stratumPassword`, `stratumTLS`, `stratumSuggestedDifficulty`, plus `fallback*` versions. Pool changes apply on the next stratum reconnect — restart the device.
- `POST /api/system/restart`

## Internal API (browser → Flask)

- `GET  /` — home page
- `GET  /device/<ip>` — detail page (404s if device isn't tracked)
- `GET  /api/devices` — list with metrics, rolling avgs, hwErrors, shares, stratum, recommendations, severity, history
- `GET  /api/device/<ip>` — single device summary
- `GET  /api/config`
- `POST /api/devices/{add,remove,rename,tune,preset,restart,reset_session}`
- `POST /api/devices/pool` — body `{ip, stratumURL?, stratumPort?, ..., fallbackStratumURL?, ..., restart?}`. Validates and PATCHes the device, optionally restarts. Empty / missing fields are skipped (worker passwords blank-by-default).
- `POST /api/scan` — scans the host's `/24` LAN for Bitaxes by probing `/api/system/info` on each address in parallel (64 workers, 1.5 s per request). Skips host self and already-added devices. Returns `{found, scanned, subnet, host, skipped_existing}`. RFC1918 ranges only.

The per-device summary includes a `recommendations` array of `{id, severity, title, body, action?}` objects. `action.type` is `tune` | `preset` | `reset_session`; `action.params` is the body for the matching endpoint. The frontend dispatches based on `action.type`.

The `severity` field on the summary is the max severity of actionable recs (excluding `warming_up`), or `null`. Used for the home-page card health border. Offline devices always report `severity: "crit"`.

## Safety bounds (server-enforced before PATCH)

- frequency: 400–900 MHz
- coreVoltage: 1000–1300 mV
- fanspeed: 0–100%
- stratum port: 1–65535

Bounds are enforced server-side in `api_device_tune` and `api_device_pool`. Never trust the browser.

## Environment variables

- `PORT` — explicitly pin a port. Unset → app tries `80` first (clean URL), falls back to `5050` if it can't bind.
- `HOST` (default `0.0.0.0`; set to `127.0.0.1` to keep it local-only — also disables mDNS).
- `MDNS_ENABLED` (default `1`; set to `0` to skip mDNS publication).
- `MDNS_NAME` (default `bitaxe-baller`; the `.local` host name to publish).

## Tooltips

Any element can declare `data-tip="explainer text"` (and optional `data-tip-pos="top|bottom|left|right"`, default `top`) to get a hover/focus tooltip. The primitive is event-delegated on `document`, so dynamically rendered nodes (e.g. inside `renderCompactDevice` or `renderDetail`) just work without re-binding.

Tooltip content is plain text via `textContent` — never inject HTML, since these strings often interpolate device-supplied data (labels, pool URLs).

When adding new UI, default to writing a one-sentence tooltip for any non-obvious control, threshold, or value. Example tone: short, declarative, includes thresholds where relevant. Tooltips are user-facing documentation — they reduce support questions, not just decoration.

## Conventions

- No build step, no frontend framework — keep it that way.
- Single shared `static/style.css`; theme palette via `:root[data-theme]` CSS variables. New colors should reference variables, not hex literals.
- Single shared `static/common.js` for cross-page helpers; page-specific JS lives inline in the template at the bottom.
- CSV log every poll, one file per device per day.
- Tuning changes auto-reset the rolling-average and HW-error baseline so the next measurement starts clean.
- All bounds-checking happens server-side; never trust the browser.
- The disclaimer (README, dashboard banner, tune-panel danger note, footer) is non-negotiable — keep it visible on both pages.
- Worker passwords are write-only — never display, never echo from the device API. Pool form starts the password field blank; only sent if the user types something.

## Test device

- Local network test Gamma: `192.168.1.223` (BM1370, firmware v2.13.1)
