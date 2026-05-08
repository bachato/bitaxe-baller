# Bitaxe Baller

Live dashboard + tuner for Bitaxe miners on your local network. One command to start; add devices, apply tuning, restart — all in the browser.

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

The startup banner prints both URLs:

```
http://localhost:5050              (this machine)
http://192.168.x.x:5050            (from any device on your LAN)
```

Open either one. No config file editing.

## LAN access (run on a Mac mini / Mac Studio / Linux box, view from anywhere)

The app binds to `0.0.0.0` by default, so anything on your network — phone, laptop, tablet — can hit `http://<host-ip>:5050` and see the same live dashboard. Useful if you want to leave it running headless on a server and check on miners from the couch.

Notes:
- **macOS firewall**: on first run, macOS may prompt to allow incoming connections for Python. Allow it. (System Settings → Network → Firewall — make sure Python isn't set to "Block all incoming connections.")
- **Static IP recommended**: pin a DHCP reservation for the host machine in your router so the URL doesn't change.
- **Port / host overrides**: `PORT=8080 HOST=0.0.0.0 python app.py`. Set `HOST=127.0.0.1` if you ever want to keep it local-only.
- **Run at login (macOS)**: drop a `launchd` plist in `~/Library/LaunchAgents/` if you want it to start on boot. Easiest path is `caffeinate -s python app.py` from a Terminal tab on the host until you're ready to formalize it.

## What you can do in the browser

- **Add a device** — paste its IP at the top, optionally name it, click add. It validates the connection before saving.
- **Watch live metrics** — hashrate, ASIC + VR temps, power, efficiency (J/TH), HW error rate, rolling averages over 1m / 5m / 15m / 1h.
- **Charts** — hashrate and temps over the last 15 minutes per device.
- **Tune** — click "tune & control" on any device card to:
  - Apply a preset (Stock, Mild, Balanced, Aggressive, Max)
  - Manually bump frequency and core voltage with ±5 / ±25 buttons
  - Reset the benchmark session to start a fresh measurement
  - Restart the device
  - Rename or remove from the dashboard
- **Recent events** — every tuning change, restart, and online/offline transition is logged per device.

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

For fine tuning, use the manual ± buttons: frequency in 25 MHz jumps, then trim with 5 MHz; voltage in 5–10 mV bumps.

## Logs

Every poll (every 5s) is appended to `logs/<label>_<date>.csv` per device. Open in Excel or pandas to compare settings over time. Columns: timestamp, ISO time, hashrate, ASIC temp, VR temp, power, voltage (measured), core voltage (requested), frequency, shares accepted, shares rejected, uptime.

## Safety bounds

The app refuses settings outside these ranges (regardless of what you enter):
- Frequency: 400–700 MHz
- Core voltage: 1000–1300 mV

These are conservative; the BM1370 is rated up to ~1300 mV but it's where chip degradation becomes a real concern. Stay under 1225 mV unless you really know what you're doing.
