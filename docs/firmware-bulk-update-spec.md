# Firmware / AxeOS Bulk Update — Design Spec

Status: **draft** · Author: design pass 2026-06-25 · Target: ~v1.17

Lets users update the two on-device binaries that ship with every AxeOS release —
**`www.bin`** (web interface) and **`esp-miner.bin`** (firmware) — across their fleet
from Baller, instead of doing the two-file dance per miner in the AxeOS UI.

## Tiering (the whole point)

| Capability | Free | Pro |
|---|---|---|
| "New AxeOS version available" notice bar | ✅ | ✅ |
| Update a miner *through Baller* (orchestrated OTAWWW→OTA→verify) | ✅ single device, **user supplies the two `.bin`s** | ✅ |
| Baller fetches + caches the matched binary pair | ❌ | ✅ |
| One-click **bulk** update across selected miners | ❌ | ✅ |

Notification = free (goodwill). Convenience (auto-fetch + one-click bulk) = Pro.
The **curation gate is the Pro feature *and* the liability shield**: Baller only
one-click-pushes AxeOS versions we've blessed, so a bad release can't auto-brick a fleet.

## On-device API (verified against a real Gamma, AxeOS v2.14.0, board 601)

| Endpoint | Method | Purpose | Notes |
|---|---|---|---|
| `/api/system/info` | GET | version + board id + telemetry | match on `boardVersion` (e.g. `601`) + `ASICModel` (`BM1370`); current ver = `axeOSVersion`/`version` |
| `/api/system/OTAWWW` | POST | flash `www.bin` (web UI) | binary upload (`files[0]`); flash **first** |
| `/api/system/OTA` | POST | flash `esp-miner.bin` (firmware) | binary upload; **reboots** — flash **last** |
| `/api/system/pause` | POST | pause mining | best-effort before flashing |
| `/api/system/resume` | POST | resume mining | mining also resumes on boot |
| `/api/system/identify` | POST | blink screen/LED | "which physical miner is this" in the bulk picker |
| `/api/system/restart` | POST | reboot | fallback |

**Order is a safety detail:** `www.bin` first, `esp-miner.bin` (the rebooting one) last,
so the device comes back up with matching UI + firmware in one reboot. Reversed, you get a
window where new firmware talks to the old web UI.

## Backend — curated firmware catalog (`bitaxe-baller-site`) — ✅ BUILT

A curated, public, read-only catalog. We track official esp-miner GitHub releases
(`bitaxeorg/ESP-Miner`) and **bless** the ones we've vetted.

**Key fact (verified against a real release): the OTA binaries are UNIVERSAL.**
A release ships one `esp-miner.bin` (~1.6 MB) + one `www.bin` (~3 MB) that apply to
*every* Bitaxe board — the firmware detects the board at runtime. The per-board
`esp-miner-factory-NNN-v*.bin` files (~15 MB) are USB **factory** images for initial
flashing, **not** OTA — we never touch them. So **OTA needs no per-board matching**
and the bricking-by-wrong-board risk is essentially gone. We store the pair under
`board_version 0` (= all boards); non-zero is reserved for the rare future case a
board ever needs its own OTA binary.

**Auto-import (✅ built):** a daily cron pulls the latest release and, if new,
downloads + checksums the universal pair and inserts it as an **unblessed draft**
(plus a `⟳ check for updates now` admin button). Human still blesses to publish —
automation stocks the shelf, the gate stays manual.

### Schema
```sql
CREATE TABLE firmware_releases (
  version       TEXT PRIMARY KEY,      -- 'v2.15.0'
  channel       TEXT NOT NULL DEFAULT 'stable',  -- stable | beta
  notes_url     TEXT,
  published_at  INTEGER,
  blessed_at    INTEGER,               -- NULL = visible to nobody yet
  created_at    INTEGER NOT NULL
);
CREATE TABLE firmware_assets (
  version       TEXT NOT NULL,
  board_version INTEGER NOT NULL,      -- 0 = all boards (universal OTA); non-zero reserved
  asic_model    TEXT NOT NULL,         -- 'all' for universal, else e.g. 'BM1370'
  kind          TEXT NOT NULL CHECK (kind IN ('firmware','www')),
  url           TEXT NOT NULL,         -- official GitHub asset URL
  sha256        TEXT NOT NULL,         -- WE compute + store this
  size          INTEGER,
  PRIMARY KEY (version, board_version, kind)
);
```

### Endpoints
- `GET /api/firmware/catalog[?board=601]` (public) — blessed releases + assets (version,
  notes, per-board URLs + **sha256**). Drives both the free notice and the Pro download.
- `POST /admin/firmware/import` (basic-auth) — paste/select a GitHub release tag; server
  pulls the asset list, downloads each binary once to compute + store sha256, inserts rows
  (unblessed).
- `POST /admin/firmware/:version/bless` / `/unbless` (basic-auth) — flip `blessed_at`.
  Admin leaderboard-style row buttons. **This is the ~30-sec-per-release human gate.**

We serve **official GitHub URLs + our verified checksums**, not re-hosted binaries — lower
bandwidth + lower liability. The app downloads from GitHub and verifies against our sha256.

## App behavior

### Version detection (free + Pro)
On each poll, compare every tracked miner's `axeOSVersion` against the latest **blessed**
catalog version for its `boardVersion`. If any miner is behind → fleet has an update.

### Notice bar — MUST be distinct from the Baller app-update banner
- **Different glyph + color + copy + placement.** App-update banner = download-style, in the
  header ("Baller v1.16.7 ready"). Firmware banner = **hardware/chip glyph**, **fleet-level**
  (above the device cards), e.g. `🔧 AxeOS v2.15.0 available for 3 miners`.
- Pro CTA → **"Update all →"** (opens the bulk panel). Free CTA → **"How to update →"**
  (opens the manual single-device flow + a link to the AxeOS release).
- Per-card mini-badge on each out-of-date miner ("v2.14.0 → v2.15.0").

### Pro flow — one-click bulk (the state machine)
Selected miners run **sequentially** (concurrency 1 by default; stop-on-failure):
```
for dev in selected:
  info = GET /api/system/info                 # reachable? read current ver
  if current == target: SKIP (already current)
  pair = catalog[target]                        # universal esp-miner.bin + www.bin (board 0)
  if not pair: FAIL "no blessed firmware for {target}"
  www, fw = download(pair.www, pair.firmware)                # from cache or GitHub
  if sha256(www)!=pair.www_sha256 or sha256(fw)!=pair.fw_sha256: FAIL "checksum mismatch"
  POST /api/system/pause                       # best-effort
  POST /api/system/OTAWWW  (www)               # wait for ok
  POST /api/system/OTA     (fw)                # reboots
  poll GET /api/system/info until up           # timeout ~120s
  if info.version != target: FAIL "version mismatch after flash"
  SUCCESS                                        # mining resumes on boot
  on FAIL: HALT run, leave device in known state, surface error
```
Per-device progress UI: `queued → downloading → flashing UI → flashing firmware → rebooting → verifying → done | failed`.

### Free flow — manual, single device
Same orchestration (pause → OTAWWW → OTA → verify), but the user **picks the two `.bin`
files** themselves (file picker, validated by name/size). No catalog download, no multi-select.
Still strictly better than raw AxeOS (does the two-file order + verify for you).

### Bulk picker UI
Table of miners: name · current ver · → target ver · checkbox (Pro multi-select) ·
**identify (blink)** button · status. Target-version dropdown (blessed versions for the
boards in the selection). "Update selected" (Pro) primary button.

## Safety rules (non-negotiable)
1. **Only push blessed, official, universal OTA binaries.** OTA is board-agnostic, so
   there's no per-board file to mis-pick (the per-board *factory* images are USB-only and
   we never touch them). Still: confirm the device is a supported Bitaxe running AxeOS
   before flashing, and only the user-supplied file path on the free/manual flow.
2. **Checksum verify** every binary before flashing.
3. **Sequential + stop-on-failure** — one bad release can't take out the fleet at once.
4. **Confirm modal** — "You're flashing firmware on N miners" with the version diff.
5. **Pause before flash**, verify version after, surface failures loudly.
6. **Pro one-click only offers blessed versions.** Free/manual can flash anything the user
   supplies (their responsibility, like the AxeOS UI today).

## Pro gating
Server-side `is_pro_active()` gates: catalog auto-download, multi-select, and the
"Update all" bulk action. Free gets: the notice, version detection, and single-device
manual flash. (Mirror the existing bulk-tune gating.)

## Build phases
1. ✅ **DONE — Backend catalog** + admin import/bless + **daily auto-import** (shipped on the site, v1.17.0).
2. ✅ **DONE — Version detection + notice bar** (free; shipped v1.17.0).
3. ✅ **DONE — Single-device flash orchestration** (free, user-supplied files). `POST /api/firmware/flash` (multipart) → pause→OTAWWW→OTA→verify. Device-detail panel with two file pickers. **Verified end-to-end on a real Gamma (2.14.0→2.14.1, and a same-version reflash via the manual path).**
4. ✅ **DONE — Pro: catalog download + bulk state machine.** `POST /api/firmware/flash` (json `{ips,version?}`) auto-fetches + sha256-verifies the blessed pair, flashes selected miners **sequentially, stop-on-failure**. Dashboard notice-bar "Update all →" opens a bulk modal (per-device progress + identify); device page gets a one-click "Update this miner". `GET /api/firmware/flash-progress` drives the UI. **Verified end-to-end on a real Gamma.** Ships in **v1.18.0**.

**On-device OTA upload format (verified on a real Gamma):** AxeOS reads the **raw request body** (`Content-Type: application/octet-stream`) for both `/api/system/OTAWWW` and `/api/system/OTA` — NOT multipart. The firmware OTA reboots and often drops the connection before sending its HTTP response, so a post-upload `ConnectionError`/timeout is treated as success and confirmed via a version poll, not as a failure.

## Open questions
- Beta channel exposure (opt-in per user)? (auto-import currently tags prereleases `beta` but only imports `/releases/latest`, i.e. stable.)
- Roll-forward only, or keep last-known-good for a manual re-flash on failure?
