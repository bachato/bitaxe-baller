# Bitaxe Baller

**v1.3** — Flask app + browser dashboard for monitoring and tuning Bitaxe Gamma (BM1370) miners on the local network. Single-file frontend, no build step.

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

- `app.py` — Flask backend. Polls each device's `/api/system/info` every 5s in parallel via ThreadPoolExecutor. In-memory state behind a lock; device list persists to `config.json` (gitignored). Publishes the dashboard as an mDNS service via `zeroconf`. Computes per-device tuning recommendations from live telemetry on every summary call.
- `templates/dashboard.html` — single-page UI, vanilla JS, no framework, no build step. Polls `/api/devices` every 5s and re-renders. Theme (dark / light) toggled in the header and persisted in `localStorage`. CSS uses theme variables on `:root[data-theme]` so both modes share one stylesheet.
- `logs/<label>_<date>.csv` — per-device CSV time series (gitignored).

## Bitaxe API reference

- `GET /api/system/info` — full status JSON
- `PATCH /api/system` — body `{frequency, coreVoltage, fanspeed, autofanspeed}`
- `POST /api/system/restart`

## Internal API (browser → Flask)

- `GET  /api/devices` — list with metrics, rolling avgs, hwErrors, shares, recommendations, history
- `GET  /api/config`
- `POST /api/devices/{add,remove,rename,tune,preset,restart,reset_session}`

The per-device summary includes a `recommendations` array of `{id, severity, title, body, action?}` objects. `action.type` is `tune` | `preset` | `reset_session`; `action.params` are the body for the matching endpoint. The frontend dispatches to the right endpoint based on `action.type`.

## Safety bounds (server-enforced before PATCH)

- frequency: 400–700 MHz
- coreVoltage: 1000–1300 mV
- fanspeed: 0–100%

Bounds are enforced server-side in `api_device_tune`. Never trust the browser.

## Environment variables

- `PORT` — explicitly pin a port. Unset → app tries `80` first (clean URL), falls back to `5050` if it can't bind (the typical non-root case).
- `HOST` (default `0.0.0.0`; set to `127.0.0.1` to keep it local-only — also disables mDNS).
- `MDNS_ENABLED` (default `1`; set to `0` to skip mDNS publication).
- `MDNS_NAME` (default `bitaxe-baller`; the `.local` host name to publish).

## Conventions

- No build step, no frontend framework — keep it that way.
- Single-file HTML template, vanilla JS only.
- CSV log every poll, one file per device per day.
- Tuning changes auto-reset the rolling-average and HW-error baseline so the next measurement starts clean.
- All bounds-checking happens server-side; never trust the browser.
- The disclaimer (README, dashboard banner, tune-panel danger note, footer) is non-negotiable — keep it visible.
- Theme palette is centralized in `:root[data-theme="dark"]` / `:root[data-theme="light"]` CSS variables. New colors should reference variables, not hex literals.

## Test device

- Local network test Gamma: `192.168.1.223` (BM1370, firmware v2.13.1)
