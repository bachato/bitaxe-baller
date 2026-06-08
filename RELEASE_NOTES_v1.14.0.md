# Bitaxe Baller v1.14.0

**Headline: full multi-coin awareness, fleet-wide outlier detection, and a critical auto-tune fix for Gamma 602 boards.** If you've been mining on a non-BTC pool (BCH / BSV / eCash / DigiByte / Namecoin), the Solo Block Probability widget now reports the correct chain. If you have a mixed fleet, the home dashboard groups cards by pool. If you've been getting "auto-tune aborted on VR temp" on a 602 board, that bug is gone.

## What changed since v1.13.0

### Multi-coin Solo Block Probability (the headline)

The block-probability widget on each device page now detects which chain the Bitaxe is actually mining and reports against that chain's network difficulty + block reward + USD price — instead of always assuming BTC.

- **Detection priority** is the payout-address prefix on the stratum user (`bitcoincash:` → BCH, `ecash:` → XEC), then known multi-coin pool subdomains (`xec.`, `-bsv.`, `bitcoin-sv`, `bitcoin-cash`, `digibyte`, `namecoin`, etc.), then the solohash.co.uk port heuristic (port 3337 → BCH). Cashaddr prefixes are the strongest signal — pool URLs rebrand, but a cashaddr-encoded address can only encode one chain.
- **Supported chains:** Bitcoin (default), Bitcoin Cash, Bitcoin SV, eCash, DigiByte, Namecoin. All SHA-256-family — the probability math (`hashrate / (2³² × network_difficulty)`) is generic across them.
- **Live stats per chain:** difficulty + block reward fetched from chain-appropriate APIs (mempool.space for BTC, blockchair.com for BCH/eCash, whatsonchain.com for BSV, chainz.cryptoid.info for DGB/NMC). Cached 10 minutes.

### Pool grouping on the home dashboard

When your fleet spans multiple chains, the home dashboard now groups device cards by pool, with a section header listing the chain name, pool host, and device count:

```
BITCOIN · solo.ckpool.org · 3 devices
[gamma-1]  [Gamma 2]  [Gamma 3]

BITCOIN CASH · gb1.letsmine.it · 1 device
[bitaxe_004]
```

Single-chain fleets render flat — no headers, no behavior change.

### Fleet outlier detection

A new informational recommendation surfaces when a device is materially behind its same-chain siblings. Compares each device against the median of its chain group (≥3 devices required for statistical meaning):

- **Hashrate floor:** flagged when GH/s drops below 80% of the fleet median for that chain
- **HW-error ceiling:** flagged when the device's hardware-error rate is more than 2× the fleet median (and above 1% absolute)

The rec body shows the actual numbers, e.g. *"hashing 18% below fleet median (1108 vs 1350 GH/s)"* or *"HW errors 4.2% vs fleet median 0.3%"*. Useful for spotting silicon-lottery duds, mounting issues, or one Bitaxe that's running hot.

### Auto-tune VR temp threshold fix (critical for Gamma 602 boards)

The single 65 °C abort threshold for both ASIC and VR temps was wrong — VR can safely run much hotter than ASIC. Gamma 602-revision boards routinely idle their VR at 68-70 °C, which was tripping the abort instantly and making auto-tune appear broken on any 602.

- **ASIC abort:** stays at **65 °C** (chip thermal envelope)
- **VR abort:** raised to **85 °C** (BM1370 VR pads are spec'd around 95 °C; 85 is conservative)

If auto-tune kept aborting on you with a *"VR temp 68 °C ≥ 65 °C"* message, this is the fix.

### Roadmap

Three ideas added to `PRO_FEATURES.md`'s "Ideas under consideration" — parked for future scoping:

- **Fleet auto-tune campaign** — tune multiple selected devices sequentially with a rollup view (Pro candidate).
- **Chip-level normalized comparison** — GH/s per Watt per MHz leaderboard across your fleet (free).
- **Fleet ROI overlay** — "your fleet will solve a block in ~X days" headline number (free, per-chain).

## Compatibility

- Existing single-chain BTC fleets see no behavior change. The new `chain` field is additive; pool grouping only activates when more than one chain is present.
- Auto-tune behavior on existing 601 boards is unchanged — those boards never hit the 65 °C VR threshold in the first place.
- Mac DMG, Windows installer, Linux from-source, and Umbrel image all share the same `app.py` — every channel gets every change.

## Upgrade

- **Mac:** click "Update available" in the dashboard banner (if you have Pro auto-update) or download the new `.dmg` from [bitaxeballer.com/download/mac](https://bitaxeballer.com/download/mac).
- **Windows:** download the new `.exe` from [bitaxeballer.com/download/windows](https://bitaxeballer.com/download/windows).
- **Umbrel:** community store update coming in a v1.14.1 follow-up (the Docker image needs a separate rebuild + digest pin).
- **From source:** `git pull && python app.py`.
