# bitaxe.bench — Project Handoff

Status snapshot for picking this up in Claude Code.

## What this is

A Flask app + browser dashboard for monitoring and tuning Bitaxe Gamma (BM1370) miners on the local network. One command to run; everything else (adding devices, tuning frequency/voltage, restarting, presets) happens in the browser. CSV logs every poll for later analysis.

Built for Nate's 3 Gammas. Test device on his network: `192.168.1.223`.

## Files in this repo

```
bitaxe-bench/
├── app.py                      # Flask backend
├── templates/
│   └── dashboard.html          # Single-page UI (vanilla JS, no build step)
├── README.md                   # User-facing run instructions
├── HANDOFF.md                  # This file
├── requirements.txt            # flask, requests (need to create)
├── .gitignore                  # need to create
└── CLAUDE.md                   # Claude Code context (need to create)
```

## What's done

### Backend (`app.py`)
- Polls every configured device's `GET /api/system/info` every 5s in parallel via ThreadPoolExecutor
- Tracks rolling hashrate averages over 1m / 5m / 15m / 1h windows
- Calculates J/TH efficiency and expected vs actual hashrate (Gamma coefficient ≈ freq × 2.28)
- Tracks hardware error rate from a session baseline (auto-resets when settings change)
- Writes one CSV per device per day to `logs/<label>_<date>.csv`
- Persists device list to `config.json` (gitignored — runtime data)
- In-memory state with `threading.Lock` for safety
- Logs an event stream per device (last 50): tuning changes, restarts, online/offline transitions

### API endpoints
- `GET  /api/devices` — full status payload for all devices
- `GET  /api/config` — current config
- `POST /api/devices/add` — validates by hitting `/api/system/info` first; rejects unreachable IPs and duplicates
- `POST /api/devices/remove`
- `POST /api/devices/rename`
- `POST /api/devices/tune` — body `{ip, frequency?, coreVoltage?, fanspeed?, autofanspeed?}`
- `POST /api/devices/preset` — body `{ip, preset}` where preset ∈ stock/mild/balanced/aggressive/max
- `POST /api/devices/restart`
- `POST /api/devices/reset_session` — clears history + HW error baseline without changing settings

### Safety bounds (server-side, enforced before PATCH)
- frequency: 400-700 MHz
- coreVoltage: 1000-1300 mV
- fanspeed: 0-100%

### Frontend (`templates/dashboard.html`)
- Vanilla JS, no framework, no build step. Single file.
- Terminal aesthetic — dark green-on-black, JetBrains Mono + Major Mono Display, scanline CSS, grid background
- Polls `/api/devices` every 5s and re-renders
- Per-device card shows: live metrics grid (hashrate, temps, voltages, power, efficiency), 1m/5m/15m/1h rolling averages, HW error rate, expected vs actual %, best diff, fan, stratum URL
- Two sparkline canvases per card: hashrate (last 15m) and temps (ASIC + VR)
- Color-coded thresholds for ASIC temp (60/65), VR temp (55/65), HW error rate (0.1%/0.5%), efficiency (16/19/22 J/TH)
- Collapsible "⚙ tune & control" panel per device:
  - 5 preset buttons
  - Manual frequency/voltage inputs with ±5/±25 step buttons
  - Reset benchmark, Restart device, Remove buttons
  - Recent events log
- Toolbar: add-device form (IP + optional label), validates on submit
- Toast notifications for actions (success/error)
- Click device name to rename inline via prompt

### Tuning presets (Gamma-specific, in `app.py`)
| Preset | Frequency | Core Voltage |
|--------|-----------|--------------|
| Stock | 525 MHz | 1150 mV |
| Mild OC | 550 MHz | 1170 mV |
| Balanced | 575 MHz | 1185 mV |
| Aggressive | 600 MHz | 1200 mV |
| Max (risky) | 625 MHz | 1225 mV |

### Tested
End-to-end test passed 17/17 checks against a mock Bitaxe HTTP server. Verified: GET endpoints, validation rejecting unreachable IPs, duplicate detection, polling loop, preset application, manual tune within bounds, out-of-bounds rejection, overvoltage rejection, restart, reset session, rename, event logging, remove, CSV writing, config persistence.

## What still needs to happen

### Setup tasks for first commit
1. Create `~/Code/bitaxe-bench/`, drop in `app.py`, `templates/dashboard.html`, `README.md`, this file
2. Create `requirements.txt`:
   ```
   flask>=3.0
   requests>=2.31
   ```
3. Create `.gitignore`:
   ```
   __pycache__/
   *.pyc
   venv/
   .venv/
   config.json
   logs/
   .DS_Store
   .env
   ```
4. Create `CLAUDE.md` (see template below)
5. `git init && git add . && git commit -m "initial commit: bitaxe.bench dashboard"`
6. Create `465media/bitaxe-bench` repo on GitHub (no README init since we have one)
7. `git remote add origin git@github.com:465media/bitaxe-bench.git && git push -u origin main`

### Run instructions (for the README, after venv setup)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open `http://localhost:5050`. Add `192.168.1.223` (Nate's test device) and any other Gamma IPs.

### Suggested next features (not built yet)
- `start.sh` one-liner: creates venv if missing, installs deps, runs the app
- A/B comparison mode: pin two settings snapshots side-by-side to compare 15m+ averages
- "Tuning session" markers — bookmark a timestamp + config label so the CSV has explicit experiment boundaries
- Auto-tune mode: sweep frequency in 25 MHz steps, hold for 15 min each, pick best J/TH that stays under HW error threshold
- WebSocket push instead of polling (current 5s polling is fine for fleet of 3-10, would matter at larger scale)
- Multi-model support: presets/expected-hashrate coefficients for Supra (BM1368) and Ultra (BM1366), not just Gamma
- Export-to-PDF benchmark report
- Discord/email alerts when a device goes offline or HW error rate spikes

### Known gotchas
- macOS without Xcode CLT has no `python3`. Run `xcode-select --install` first.
- Bitaxe's `/api/system/info` returns instantaneous hashrate which is very noisy on the BM1370. Always look at the rolling averages, not the headline number, when tuning.
- The expected-hashrate coefficient (2.28) is approximate — real Gammas vary chip-to-chip. The "actual % of expected" row is a sanity check, not a precise measurement.
- VR temp is what kills boards, not ASIC temp. The dashboard color-codes both but VR is the one to watch.

## CLAUDE.md template (to drop at project root)

```markdown
# bitaxe.bench

Flask app + browser dashboard for monitoring and tuning Bitaxe Gamma (BM1370) miners on the local network.

## Run
\`\`\`bash
source venv/bin/activate
python app.py
\`\`\`
Then open http://localhost:5050

## Architecture
- `app.py` — Flask backend, polls each device's `/api/system/info` every 5s,
  exposes endpoints for tuning (`PATCH /api/system`), restarting,
  managing the device list. In-memory state, config persists to `config.json` (gitignored).
- `templates/dashboard.html` — single-page UI, vanilla JS, no build step.
  Polls `/api/devices` every 5s and re-renders.
- `logs/<label>_<date>.csv` — per-device CSV time series, gitignored.

## Bitaxe API reference
- `GET /api/system/info` — full status JSON
- `PATCH /api/system` — body `{frequency, coreVoltage, fanspeed, autofanspeed}`
- `POST /api/system/restart`

## Safety bounds (server-enforced)
- frequency: 400-700 MHz
- coreVoltage: 1000-1300 mV

## Conventions
- No build step, no frontend framework — keep it that way
- Single-file HTML template, vanilla JS only
- CSV log every poll, one file per device per day
- Tuning changes auto-reset the rolling-average baseline so measurements stay clean
- All bounds-checking happens server-side; never trust the browser
- Test device on local network: 192.168.1.223
```

## Picking up in Claude Code

After cloning/setting up the project, a good first prompt would be something like:

> Read HANDOFF.md and CLAUDE.md, then verify the app runs cleanly. Add `192.168.1.223` as my first device and confirm we're getting live data. After that, let's build a `start.sh` script.

Or if you're picking up cold:

> Read HANDOFF.md to understand current state. What's the most useful next thing to add given my goal of benchmarking 3 Gammas?
