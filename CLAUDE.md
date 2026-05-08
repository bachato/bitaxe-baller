# bitaxe.bench

Flask app + browser dashboard for monitoring and tuning Bitaxe Gamma (BM1370) miners on the local network.

## Run

```bash
source venv/bin/activate
python app.py
```

Then open http://localhost:5050 — or `http://<lan-ip>:5050` from any device on the same network. The startup banner prints the LAN IP automatically.

## Architecture
- `app.py` — Flask backend. Polls each device's `/api/system/info` every 5s in parallel via ThreadPoolExecutor. In-memory state behind a lock; device list persists to `config.json` (gitignored).
- `templates/dashboard.html` — single-page UI, vanilla JS, no build step. Polls `/api/devices` every 5s and re-renders.
- `logs/<label>_<date>.csv` — per-device CSV time series (gitignored).

## Bitaxe API reference
- `GET /api/system/info` — full status JSON
- `PATCH /api/system` — body `{frequency, coreVoltage, fanspeed, autofanspeed}`
- `POST /api/system/restart`

## Safety bounds (server-enforced before PATCH)
- frequency: 400-700 MHz
- coreVoltage: 1000-1300 mV
- fanspeed: 0-100%

## Conventions
- No build step, no frontend framework — keep it that way.
- Single-file HTML template, vanilla JS only.
- CSV log every poll, one file per device per day.
- Tuning changes auto-reset the rolling-average and HW-error baseline so the next measurement starts clean.
- All bounds-checking happens server-side; never trust the browser.
- Flask binds to `0.0.0.0` so the dashboard is reachable from other devices on the LAN. macOS may prompt about firewall on first run — allow it.

## Test device
- Local network test Gamma: `192.168.1.223`
