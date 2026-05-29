# Bitaxe Baller — Umbrel community app store

This is the [Umbrel](https://umbrel.com) community app source for **Bitaxe Baller**, the open-source dashboard + tuner for hobbyist Bitaxe Bitcoin mining hardware.

## What's here

```
.
├── umbrel-app-store.yml          # store manifest (id, name, developer)
└── bitaxe-baller/                # one app per directory
    ├── umbrel-app.yml            # app manifest (version, gallery, release notes)
    └── docker-compose.yml        # container spec, pinned by sha256 digest
```

## How to install Bitaxe Baller on your Umbrel

1. In the Umbrel UI: **App Store → Community App Stores → Add Custom Store**
2. Paste this repo's URL: `https://github.com/465media/umbrel-bitaxe-baller-store`
3. Confirm. Bitaxe Baller appears in the store.
4. Click **Install**.
5. Open via the Umbrel dashboard tile, OR direct LAN at `http://umbrel.local:5050` / `http://bitaxe-baller.local:5050` (Bonjour/Avahi).
6. Add Bitaxes via **scan** or paste IPs — same flow as the desktop app.

Data persists in `~/umbrel/app-data/bitaxe-baller/data/` (config.json, logs/, history.db). Survives reinstalls and Umbrel updates.

## About Bitaxe Baller

- **Main repo:** https://github.com/465media/bitaxe-baller
- **Website:** https://bitaxeballer.com
- **License:** MIT
- **Developer:** 465 Media

Free tier covers the full LAN dashboard, mDNS publishing, network scanner, recommendation engine, tuning controls, fan control, daily CSV logs, the solo block probability widget, live share feed, and the public leaderboard at [bitaxeballer.com/leaderboard](https://bitaxeballer.com/leaderboard) (free to enter — top miner per Bitaxe model wins a free month of Pro every month).

Pro tier ($29/year, optional) unlocks bulk tuning, auto-tune frequency sweeps with safety guardrails, 90 days of SQLite history, Discord webhook alerts, and remote dashboard access via [relay.bitaxeballer.com](https://relay.bitaxeballer.com).

## Why a community store and not the official Umbrel app store?

This is the soft-launch path. Once we have ≥1 month of community-store users without incident, the plan is to submit Bitaxe Baller to the [official Umbrel app store](https://github.com/getumbrel/umbrel-apps). The official store gets a featured slot but requires PR review by the Umbrel team and adherence to their content policies — easier to validate the install flow here first.

## Updates

Each new Bitaxe Baller release (Mac / Windows / Umbrel) ships in lockstep with a new commit to this repo bumping the `umbrel-app.yml` version + the pinned `@sha256:` digest in `docker-compose.yml`. Umbrel re-reads this repo on its next refresh and shows your existing install an **Update** button.

## Issues + support

- Bug reports, feature requests: [bitaxe-baller/issues](https://github.com/465media/bitaxe-baller/issues)
- General support: https://bitaxeballer.com/support.html
