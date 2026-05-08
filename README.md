# Bitaxe Baller

**v1.3** — Live dashboard + tuner for Bitaxe miners on your local network. One command to start; add devices, apply tuning, restart, watch the recommendation engine — all in the browser.

> ## ⚠️ Disclaimer — read this before clicking anything
>
> **Overclocking can permanently damage your Bitaxe.** Pushing frequency or voltage past stock raises temperatures, accelerates silicon degradation, and in extreme cases can let the magic smoke out — especially on the VR (voltage regulator), which is what kills boards. The presets and bounds in this tool are chosen to be conservative, but **conservative is not the same as safe.**
>
> By using Bitaxe Baller you agree that:
>
> - You're tuning **your own hardware at your own risk**.
> - The author(s) and contributors are **not liable** for any damage to your miner, lost mining revenue, electricity costs, fire, water damage, voided warranties, or other consequences arising from use of this tool.
> - The "safety bounds" baked into the app (frequency 400–700 MHz, core voltage 1000–1300 mV) are **upper guardrails, not recommendations** — sustained operation at the high end of those ranges WILL shorten chip life.
> - Software is provided **AS-IS, without warranty of any kind**. See [LICENSE](LICENSE) once one is added; absent that, all rights reserved and no warranty is implied.
>
> If you don't accept this, don't click "apply." Stick to stock and you'll be fine.

## Run it

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The startup banner prints every URL the dashboard is reachable on. Two flavors depending on how you start the app:

```bash
python app.py
#   http://localhost:5050              (this machine)
#   http://192.168.x.x:5050            (from any device on your LAN)
#   http://bitaxe-baller.local:5050    (via mDNS / Bonjour)

sudo $(which python) app.py
#   http://localhost                   (this machine — clean URL, no port)
#   http://192.168.x.x                 (from any device on your LAN)
#   http://bitaxe-baller.local         (via mDNS / Bonjour — type this and you're in)
```

Open any one. No config file editing.

## Want clean URLs without `:5050`? Run with sudo

The simplest URL is `http://bitaxe-baller.local` — but **port 80 requires root** on macOS and Linux. The app handles both cases gracefully:

- **No env var set** → tries port 80 first, falls back to 5050 if it can't bind.
- **Run with sudo** → port 80 succeeds; banner prints `http://bitaxe-baller.local` (no port).
- **Run without sudo** → port 5050; banner prints `http://bitaxe-baller.local:5050`.
- **Force a port** → set `PORT=8080 python app.py` to skip the auto-pick.

So the recommended setup for the cleanest experience on a Mac you control is:

```bash
sudo $(which python) app.py
```

You'll be prompted for your password once per Terminal session. Use the venv path explicitly so sudo doesn't lose your virtualenv: `sudo $(which python)` works because `which python` resolves to the venv's interpreter while the venv is active.

## LAN access — three ways to reach the dashboard

The app binds to `0.0.0.0` by default, so any device on your network can use the dashboard. Pick whichever URL is easiest:

1. **`localhost`** (or `localhost:5050`) — only on the host machine.
2. **`<lan-ip>`** — works from anything on the LAN. The startup banner auto-detects and prints the right IP.
3. **`bitaxe-baller.local`** — published via mDNS (Bonjour on macOS/iOS, Avahi on Linux, native on Windows 10+). No need to remember an IP. Toggle off with `MDNS_ENABLED=0` if it ever conflicts with anything.

Headless setup (Mac mini, Mac Studio, Raspberry Pi, etc.):

- **macOS firewall**: on first run, macOS may prompt to allow incoming connections for Python. Allow it. (System Settings → Network → Firewall — make sure Python isn't set to "Block all incoming connections.")
- **Static IP recommended** if you can't rely on mDNS: pin a DHCP reservation for the host machine in your router so the URL doesn't change.
- **mDNS gotchas**: works on macOS/iOS out of the box, on Linux with `avahi-daemon`, and on Windows 10+ (older Windows may need the Bonjour Print Services installer). A few aggressive routers block multicast — if `bitaxe-baller.local` doesn't resolve, fall back to the IP.
- **Port / host / mDNS overrides**:

  ```bash
  PORT=8080 HOST=0.0.0.0 MDNS_NAME=miners python app.py     # custom port + name
  HOST=127.0.0.1 python app.py                              # local-only (also disables mDNS)
  MDNS_ENABLED=0 python app.py                              # keep LAN access, turn off Bonjour
  ```

- **Run at login (macOS)**: drop a `launchd` plist in `~/Library/LaunchAgents/` if you want it to start on boot. A `launchd` job runs as root, so it gets port 80 automatically — no sudo prompt. Easiest interim path is `caffeinate -s sudo $(which python) app.py` from a Terminal tab on the host until you're ready to formalize it.

## What you can do in the browser

- **Add a device** — paste its IP at the top, optionally name it, click add. The app validates the connection before saving.
- **Watch live metrics** — hashrate, ASIC + VR temps, power, efficiency (J/TH), HW error rate, and rolling averages over 1m / 5m / 15m / 1h.
- **Shares & difficulty** — session shares accepted/rejected, share rate per minute, best-diff this session and all-time (formatted as 9.27G etc), pool difficulty, lifetime accepted shares.
- **Live recommendations** — a per-device panel surfaces 0–3 prioritized tuning suggestions based on the live telemetry. Each suggestion has a one-click apply button.
- **Charts** — hashrate and temps over the last 15 minutes per device.
- **Tune** — click ⚙ tune & control on any device card to:
  - Apply a preset (Stock, Mild OC, Balanced, Aggressive, Max).
  - Manually bump frequency and core voltage with ±5 / ±25 buttons.
  - Switch the fan to auto, or lock it at a specific manual percentage.
  - Reset the benchmark session to start a fresh measurement.
  - Restart the device, rename it, or remove it from the dashboard.
- **Recent events** — every tuning change, restart, and online/offline transition is logged per device.
- **Light or dark mode** — toggle in the top-right (☀ / 🌙). Preference is stored in `localStorage` and applied per-browser.

## Recommendation engine

The dashboard surfaces up to three suggestions per device, ranked by severity (`crit` > `warn` > `good` > `info`). The rules encode the suggested tuning workflow below — they are transparent and conservative, not an autotuner. Each rec has an optional one-click apply button.

| Trigger | Severity | Suggested action |
|---|---|---|
| VR temp ≥ 65°C | crit | Drop core voltage 15 mV |
| HW error rate ≥ 1% (after 20+ session shares) | crit | Drop core voltage 10 mV |
| HW error rate 0.5–1% | warn | Add 10 mV (more stability) or back off freq |
| ASIC ≥ 65°C, VR < 65°C | warn | Enable auto-fan / improve airflow |
| 5m hash < 92% of 15m hash | warn | Reset benchmark and re-baseline |
| Stable 15+ min, errors < 0.1%, temps healthy | good | Try +25 MHz |
| Hashrate < 85% of expected (after 5 min) | info | Could be silicon lottery — check HW errors |
| J/TH ≤ 16 with 0% errors and cool temps | good | Hold this point — excellent efficiency |

The engine waits ~3 minutes after add or benchmark reset before returning tuning recs (so they don't fire on noise).

## Color thresholds (Gamma-tuned)

| Metric | Good (green) | Warn (yellow) | Crit (red) |
|--------|-------------|---------------|-----------|
| ASIC temp | <60°C | 60–65°C | >65°C |
| VR temp | <55°C | 55–65°C | >65°C |
| HW error rate | <0.1% | 0.1–0.5% | >0.5% |
| Efficiency | <16 J/TH | 19–22 J/TH | >22 J/TH |

VR temp matters more than ASIC temp for board longevity. Watch it.

## Suggested tuning workflow

1. Apply the **Stock** preset, let it run 15+ minutes. Note the 15m average hashrate, J/TH, and HW error rate from the device card.
2. Click **Mild OC** preset. The benchmark resets automatically. Wait 15 minutes again.
3. If HW error rate stays under 0.5% and temps are healthy, try **Balanced**. Repeat.
4. When errors start climbing or efficiency stops improving, you've found your sweet spot. Back off one notch.

For fine tuning, use the manual ± buttons: frequency in 25 MHz jumps, then trim with 5 MHz; voltage in 5–10 mV bumps. The recommendation engine surfaces concrete next steps as the data comes in.

## Logs

Every poll (every 5s) is appended to `logs/<label>_<date>.csv` per device. Open in Excel or pandas to compare settings over time. Columns: timestamp, ISO time, hashrate, ASIC temp, VR temp, power, voltage (measured), core voltage (requested), frequency, shares accepted, shares rejected, uptime.

## Safety bounds

The app refuses settings outside these ranges (regardless of what you enter):

- Frequency: 400–700 MHz
- Core voltage: 1000–1300 mV
- Fan speed: 0–100%

These are conservative; the BM1370 is rated up to ~1300 mV but that's where chip degradation becomes a real concern. Stay under 1225 mV unless you really know what you're doing.

## Roadmap / not built yet

- LICENSE file (MIT is the likely choice)
- `start.sh` one-liner that creates the venv, installs deps, runs the app
- launchd plist template for run-on-boot on macOS
- A/B comparison mode: pin two settings snapshots side-by-side
- Auto-tune sweep mode (frequency steps with HW-error guardrails)
- WebSocket push instead of 5s polling (matters at >10 devices)
- Multi-model presets for Supra (BM1368) and Ultra (BM1366)
- Discord / email alerts on offline or HW-error spikes
