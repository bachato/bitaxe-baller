# Bitaxe Baller

**v1.2** — Flask app + browser dashboard for monitoring and tuning Bitaxe Gamma (BM1370) miners on the local network. Single-file frontend, no build step.

## Run

```bash
source venv/bin/activate
python app.py
```

The startup banner prints three URLs:
- `http://localhost:5050` — this machine
- `http://<lan-ip>:5050` — auto-detected LAN IP, reachable from any device on the network
- `http://bitaxe-baller.local:5050` — published via mDNS / Bonjour (no IP needed)

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

- `PORT` (default `5050`)
- `HOST` (default `0.0.0.0`; set to `127.0.0.1` to keep it local-only — also disables mDNS)
- `MDNS_ENABLED` (default `1`; set to `0` to skip mDNS publication)
- `MDNS_NAME` (default `bitaxe-baller`; the `.local` host name to publish)

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
