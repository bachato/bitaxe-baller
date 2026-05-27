# Bitaxe Baller v1.11.0

**Headline: live share feed + best-shares leaderboards — local *and* public.** Every device's detail page now streams "share accepted / new personal best" events in real time. The home dashboard adds a fleet leaderboard ranking your devices by best-share difficulty. And Pro users can opt-in to a public cross-user leaderboard at **bitaxeballer.com/leaderboard** with four categories so big and small miners both have a way to climb.

## New (free tier)

### Live share feed

A new section on the device detail page between **solo block probability** and **tune & control**. Streams the last 50 share events synthesized from polling deltas:

- `✓ N accepted` — counter went up between polls
- `✗ N rejected` — HW errors landed (red border)
- `★ NEW PERSONAL BEST · 12.5G` — `bestDiff` crossed upward (gold border, special highlight)

We don't have access to per-share difficulty values — firmware exposes counters and the running best, not the stream itself — so the feed is what we can synthesize from those signals. New-best events fire when `bestDiff` increments, which is what most users care about anyway.

Updates every 5 seconds along with the rest of the page. Ring buffer of 50 events per device; resets on app restart.

### Fleet best-shares leaderboard (home dashboard)

New widget under the device cards, hidden when only one device is online. Ranks your fleet by:

- **All-time best** — career `bestDiff` per firmware (lifetime since last factory reset)
- **Session best** — `bestSessionDiff` (resets when the device restarts)

Top 5 in each. Click any row to jump to that device's detail page. Gold/silver/bronze left-border accents for ranks 1/2/3.

### Per-device best-share badges

Every device card on the home dashboard now shows two small badges next to the stats row:

- `BEST 1.68G` — all-time best diff
- `SESSION 412M` — session best diff

Tooltip explains that best-share is a lottery metric — small miners can occasionally beat big ones on luck.

## New (Pro)

### Public leaderboard opt-in

Inside the Pro modal, a new **Public leaderboard** section with a display-name input and a "Submit my best shares" toggle. When enabled, the desktop app POSTs your device data to `https://bitaxeballer.com/api/leaderboard/submit` on every new personal-best and on a 5-minute heartbeat.

What's sent per device:
- Display name (user-chosen, 30 chars max, letters/numbers/spaces/`._-`)
- MAC address (the unique device key)
- Model (Gamma / Supra / Ultra / Hex / NerdQaxe)
- Best-share difficulty (career + session)
- 15-minute average hashrate (for the "lucky" leaderboard)
- App version (for support / compat tracking)

What's NOT sent: IP address, location, email, license key (only a SHA-256 hash of the key is stored server-side, so a full DB leak wouldn't reveal license keys). License keys are validated against the existing licenses table before any data is stored — invalid/expired keys are rejected with 401.

### Public leaderboard page

Live at `bitaxeballer.com/leaderboard` — four side-by-side categories so different miner sizes have different races to win:

1. **All-time best** — career best-share diff across everyone (big miners dominate; the "glory" board)
2. **This week** — rolling 7-day window, resets weekly per device; anyone can spike here on a lucky hour
3. **Per-model** — separate Gamma / Supra / Ultra / Hex / NerdQaxe rankings; solo Gamma owners only rank against other Gammas
4. **Lucky** — best-share diff ÷ avg hashrate; pure "who beat the odds"

Entries are hidden after 30 days of no activity. Display names go through a profanity blocklist on submission. Stale entries decay; no manual moderation queue.

## Free tier — unchanged otherwise

The LAN dashboard, mDNS publishing, network scanner, recommendation engine, tuning controls, fan control, light/dark theme, daily CSV logs, the solo block probability widget — all unchanged. The new live share feed, fleet leaderboard widget, and per-device best-share badges are in the free tier.

## Upgrading

- **Mac (Pro users):** Sparkle auto-update delivers v1.11.0 in-place. Banner on next launch, click "install & restart."
- **Mac (free users):** Banner with a one-click download link.
- **Windows:** Banner-with-download flow. Authenticode-signed via Azure Trusted Signing.
- **From source:** `git pull && python app.py` — no new dependencies.

## Under the hood — for developers

- `app.py` gains a share-event detection block in `poll_one` (~30 lines) and three small leaderboard helpers (`_leaderboard_cfg`, `_leaderboard_submit_one`, `_maybe_submit_leaderboard`). The submitter is throttled to one submission per device per 5 minutes, with an immediate force-push on new-best.
- `device_summary` adds `macAddr`, `metrics.bestDiffValue`, `metrics.bestSessionDiffValue`, and a `shareEvents` array (last 50). All additive — clients that ignore unknown keys keep working.
- Two new endpoints: `GET /api/leaderboard/status` and `POST /api/leaderboard/save`. Both Pro-gated (402 if not).
- `bitaxe-baller-site/server/index.js` gets a `leaderboard` SQLite table (mac_addr PK, license_key_hash, display_name, model, best_diff_career, best_diff_session, best_diff_week, week_started_at, hashrate_th_avg, app_version, first_seen, last_seen) and two new routes: `POST /api/leaderboard/submit` (license-authenticated, upsert by mac) and `GET /api/leaderboard/data?category=...` with four categories.
- `bitaxe-baller-site/public/leaderboard.html` is new — a self-contained page that fetches each category in parallel every 60s, formats diffs the same way the desktop app does, and respects the site's theme toggle.
- No new Python or JS dependencies.

## Compatibility

- The new `/api/devices` fields are additive; existing clients that ignore unknown JSON keys keep working. The remote SPA at `relay.bitaxeballer.com` already does — Pro users on the remote view get the new fields served through but won't see the widgets until the remote SPA gets the matching UI update (tracked separately).
- `config.json` gains an optional `public_leaderboard: {enabled, display_name}` key. Existing configs without it default to disabled.
- The auto-update appcast format is unchanged; v1.10.x Pro users get this through Sparkle as expected.

## Known limitations in v1.11.0

- Live share feed synthesizes events from counter deltas — we never see individual per-share difficulty values, only the running best. A burst of low-difficulty shares between polls shows up as a single "+N accepted" event with no per-share detail.
- Display names go through a small profanity blocklist on submit, not a content moderation queue. Edge cases will get through; we'll iterate based on what actually shows up.
- Best-share-week resets per-device on a 7-day rolling window from the device's `week_started_at`, which is set when the device first appears in the leaderboard. Devices that join mid-week have a "shorter first week."
- Per-model leaderboard is capped at 10 entries per model. If you mine on an exotic ASIC the model field stays whatever the firmware reports — we don't try to normalize names.
- Mobile companion apps don't render the live feed or leaderboard yet — that's a mobile-side UI task tracked separately, will land after the next App Store / Play Store update.
