# Bitaxe Baller v1.10.0

**Headline: solo block probability widget.** Every device's detail page now answers the question solo miners actually care about — *how close am I to finding a block?* — with the same daily/monthly/yearly "1 in X" odds you'd compute by hand, plus a log-scaled proximity bar showing how close your best share has gotten to the network target. No telemetry, no calls home; just math against your live hashrate and a 10-minute-cached fetch of network difficulty + USD price from free public APIs.

## New (free tier)

### Solo block probability

A new section on the device detail page, between **live metrics** and **tune & control**, showing:

- **Daily / Monthly / Yearly "1 in X" odds.** Pure math: `1 / (hashrate × seconds / (2³² × network_difficulty))`. Average odds — solo mining is a lottery, this is the ticket count.
- **Diff + reward + USD line.** Current network difficulty, post-2024-halving block subsidy (3.125), and live USD price. Diff and price refresh every 10 minutes; reward is a constant until the next halving.
- **Block proximity bar.** A cold-to-hot gradient (teal → blue → purple → orange → red) with a marker positioned by `log₁₀(best_diff + 1) / log₁₀(network_diff + 1)`. Log-scaled on purpose — raw `best/network` would peg the bar at zero forever; the log scale moves the marker linearly across orders-of-magnitude closer to a solved block.

### Chain auto-detection

The stratum URL drives which chain we compute against. v1.10.0 ships with six — every SHA-256d chain a Bitaxe can realistically solo:

| Coin | Symbol | Subsidy | URL needles |
|---|---|---|---|
| Bitcoin | BTC | 3.125 | (fall-through default) |
| Bitcoin Cash | BCH | 3.125 | `bch.`, `-bch.`, `bitcoin-cash`, `bcash`, solohash port 3337 |
| Bitcoin SV | BSV | 3.125 | `bsv.`, `-bsv.`, `bitcoin-sv` |
| eCash | XEC | 3,125,000 | `xec.`, `-xec.`, `ecash`, `bcha` |
| DigiByte | DGB | ~575 | `dgb.`, `-dgb.`, `digibyte` |
| Namecoin | NMC | 0.78125 | `nmc.`, `-nmc.`, `namecoin` |

XEC and NMC have unusual subsidy units — XEC retained BCHA's 8-decimal redenomination so a "block" pays ~3.125M XEC at penny-fraction prices, and NMC sits low on its BTC-mirrored halving schedule. The USD figure renders with extra decimals when the value is below $100 so you actually see the number rather than a rounded "$0". For Namecoin specifically: it's merge-mined with BTC, so if you're solo-mining NMC you're effectively *also* mining BTC on the same hashes; the widget's math is independent per-chain.

### Data sources

| Chain | Difficulty | USD price |
|---|---|---|
| BTC | mempool.space (latest block) | mempool.space `/prices` |
| BCH | blockchair `/bitcoin-cash/stats` | blockchair (same call) |
| XEC | blockchair `/ecash/stats` | blockchair (same call) |
| BSV | whatsonchain `/v1/bsv/main/chain/info` | CoinGecko (`bitcoin-cash-sv`) |
| DGB | chainz `/dgb/api.dws?q=getdifficulty` | CoinGecko (`digibyte`) |
| NMC | chainz `/nmc/api.dws?q=getdifficulty` | CoinGecko (`namecoin`) |

Every endpoint is no-auth, no-key, no-rate-limit-at-our-cadence. Cache TTL is 10 minutes per chain. On a transient fetch failure, the widget keeps showing the last-good values rather than blanking out.

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

- Block proximity is a log-scaled best-share-vs-network ratio, not a luck-streak indicator. Two miners with the same best share will show the same bar position regardless of recent share history.
- Reward shown is the block subsidy only. Mempool fees are omitted from the USD figure — they're highly variable and would invalidate the cache every block. For BTC that's a 0–10% understatement on a typical block; for the alts it's usually negligible.
- DigiByte uses a smooth subsidy decay rather than discrete halvings. The constant in `_BLOCK_REWARDS["dgb"]` will drift slowly; we'll bump it in a future release. Today's number is within 1% of reality.
- Namecoin is merge-mined with BTC — the same hashes that win BTC blocks can also win NMC blocks at NMC's much lower difficulty. The widget treats NMC standalone (computes against NMC's network diff), which is the right math but doesn't capture the "you're also mining BTC" upside.
- Mobile companion app shows the new field via the relay but doesn't render the widget yet — that's a mobile-side UI task tracked separately.
