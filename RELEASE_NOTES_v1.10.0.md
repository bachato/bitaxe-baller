# Bitaxe Baller v1.10.0

**Headline: solo block probability widget.** Every device's detail page now answers the question solo miners actually care about — *how close am I to finding a block?* — with the same daily/monthly/yearly "1 in X" odds you'd compute by hand, plus a log-scaled proximity bar showing how close your best share has gotten to the network target. No telemetry, no calls home; just math against your live hashrate and a 10-minute-cached fetch of network difficulty + USD price from free public APIs.

## New (free tier)

### Solo block probability

A new section on the device detail page, between **live metrics** and **tune & control**, showing:

- **Daily / Monthly / Yearly "1 in X" odds.** Pure math: `1 / (hashrate × seconds / (2³² × network_difficulty))`. Average odds — solo mining is a lottery, this is the ticket count.
- **Diff + reward + USD line.** Current network difficulty, post-2024-halving block subsidy (3.125), and live USD price. Diff and price refresh every 10 minutes; reward is a constant until the next halving.
- **Block proximity bar.** A cold-to-hot gradient (teal → blue → purple → orange → red) with a marker positioned by `log₁₀(best_diff + 1) / log₁₀(network_diff + 1)`. Log-scaled on purpose — raw `best/network` would peg the bar at zero forever; the log scale moves the marker linearly across orders-of-magnitude closer to a solved block.

### Chain auto-detection

The stratum URL drives which chain we compute against. v1.10.0 ships with two:

- **BTC** is the fall-through default — matches `solo.ckpool.org`, `public-pool.io`, `solo.solomining.io:3333`, `*.solohash.co.uk:3333`, etc.
- **BCH** is detected via host substrings (`bch.`, `-bch.`, `bitcoin-cash`, `bcash`) or the solohash.co.uk port 3337 convention.

More SHA-256 chains (BSV, eCash, Digibyte) are a 15-LOC drop-in per chain — file an issue or PR if you want a specific pool target supported.

### Data sources

- BTC: latest block + USD price from `mempool.space` (no auth, no key, no rate limit at our cadence).
- BCH: difficulty + USD price from `api.blockchair.com/bitcoin-cash/stats`.

Cache TTL is 10 minutes. On a transient fetch failure, the widget keeps showing the last-good values rather than blanking out.

## Free tier — unchanged

The LAN dashboard, mDNS publishing, network scanner, recommendation engine, tuning controls, fan control, light/dark theme, daily CSV logs, and the Pro remote-access toggle — all unchanged. The new widget is in the free tier; nothing about Pro changed in this release.

## Upgrading

- **Mac (Pro users):** Sparkle auto-update delivers v1.10.0 in-place. Banner on next launch, click "install & restart."
- **Mac (free users):** Banner with a one-click download link.
- **Windows:** Banner-with-download flow. Authenticode-signed via Azure Trusted Signing.
- **From source:** `git pull && python app.py` — no new dependencies.

## Under the hood — for developers

- `app.py` gains a small block-probability module (about 130 lines): `_infer_chain()`, `_chain_stats()` with a TTL-based cache, `_block_probability_math()`, `_parse_diff()`. All pure functions except the cache.
- `device_summary()` emits a new top-level `blockProbability` field on `/api/devices` and `/api/device/<ip>`. Null when the device is offline or when chain stats can't be fetched.
- `templates/device.html` gets a `blockProbPanel()` function and a new `.detail-section.block-prob` markup block. It bails to an empty string if `d.blockProbability` is null — no special handling needed in the renderer.
- `static/style.css` adds a `.bp-*` class family for the widget. All colors come from CSS variables; the rainbow gradient is hardcoded (the gradient is the same in both themes — only the marker's fill/border swap).
- No new Python or JS dependencies.

## Compatibility

- The new `/api/devices` field is additive; existing clients that ignore unknown JSON keys keep working. The remote SPA at `relay.bitaxeballer.com` already does — Pro users on the remote view get the new field served through but won't see the widget until the remote SPA gets the matching UI update (tracked separately).
- `config.json`, log files, recommendation engine — all unchanged.
- The auto-update appcast format is unchanged; v1.9.x Pro users get this through Sparkle as expected.

## Math sanity-check

Reference: a competitor app's screenshot at 621.89 GH/s solo BCH against 680.89 G diff showed daily 1 in 54,426, monthly 1 in 1,815, yearly 1 in 150. Our implementation gives 1 in 54,426 (exact), 1 in 1,814 (off-by-one rounding), 1 in 149 (off-by-one rounding). Same formula, just different floor/ceil direction on the rounding step.

## Known limitations in v1.10.0

- BTC + BCH only. BSV, eCash, Digibyte are trivial to add — see the new helpers in `app.py` for the pattern.
- Block proximity is a log-scaled best-share-vs-network ratio, not a luck-streak indicator. Two miners with the same best share will show the same bar position regardless of recent share history.
- Reward shown is the block subsidy only (3.125 BTC / 3.125 BCH post-2024-halving). Mempool fees are omitted from the USD figure — they're highly variable and add ~5–20% on a typical block but would invalidate the cache every block.
- Mobile companion app shows the new field via the relay but doesn't render the widget yet — that's a mobile-side UI task tracked separately.
