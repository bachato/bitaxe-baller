# Bitaxe Baller v1.12.0

**Headline: the public leaderboard is now free to enter for everyone, and the top miner in each Bitaxe model wins a free month of Pro every month.** Free-tier users sign up with a display name and an email (used solely to deliver prizes — no marketing). Pro users keep their existing license-key authentication. Places 2-5 in each model get a one-time 20%-off Pro coupon emailed automatically. The mechanic is a top-of-funnel growth loop, not a Pro perk.

## What changed since v1.11.0

### Submission is now free (the big one)

v1.11 launched the leaderboard with submission gated behind a Pro subscription. That inverted the funnel — the leaderboard should *attract* people to the product, not exclude the people we want most. v1.12 opens it:

- Any Bitaxe Baller user can opt-in from the Pro modal's **Public leaderboard** section
- **Free users** authenticate with a locally-generated `install_uuid` (stored in `config.json`) plus a verified email
- **Pro users** still authenticate with their license key (no email needed)
- Both flows hit the same `/api/leaderboard/submit` endpoint with different credentials; the server validates each and tags the row's `tier` accordingly

### Monthly prize draw

Runs the **last day of each month at 23:00 UTC**. Per Bitaxe model with ≥3 eligible entries:

- **#1** receives a real Pro license key with `tier='pro-monthly'` and a 30-day `expires_at`. Paste it into the Pro modal and your subscription unlocks for 30 days; if you already have Pro, your existing renewal extends by 30 days.
- **#2 through #5** receive a one-time Stripe promotion code for **20% off Pro**, valid for 60 days, redeemable at `bitaxeballer.com/pro`.

Both arrive by email automatically — no manual fulfillment, no claim form, no waiting.

### Eligibility filters

Designed to balance "anyone can play" with "no dominators":

- Verified email (one-click link, valid 7 days)
- ≥ 24 hours of polled activity (`first_seen` must be at least 24h before the draw)
- Not flagged by admin or auto-detection
- Not in the bans table (uuid + email + IP OR-blacklist)
- Email hasn't won the #1 spot in any model in the last 90 days

Models with fewer than 3 eligible entries skip the draw that month (no contest with one player).

### Email verification

Free-tier first-time submission triggers a one-click verification email via Resend. Verified emails are eligible for monthly prizes; unverified emails can climb the board but can't win. Tokens expire after 7 days; re-submit to get a new one.

### Anti-abuse

- **Per-IP throttle** at submit: max 10 distinct MAC addresses registered from one IP per day
- **Daily auto-detection** (runs via the in-process cron):
  - IP burst: > 3 MACs from one IP in 7 days → flag all
  - Absurd hashrate: > 50 TH/s for a single device (no Bitaxe does that — flag)
  - Non-Espressif MAC OUI: if the MAC's vendor prefix isn't in our hardcoded Espressif list, flag (Bitaxes use ESP32)
  - Best-share mimic: career best within 1% of an older entry → flag the newer
- Flagged rows are hidden from the public board until admin clears them

### Admin moderation panel

New section in `/admin` between Licenses and Downloads:

- Paginated table of all entries with email / install_uuid / IP / last-seen / tier badges
- Three per-row actions: **Remove** (delete row; user re-submits fresh), **Ban** (uuid + email + IP added to blacklist; future submissions silently 403), **Flag** (mark for review, hide from public board)
- Filters: "show flagged only," "show unverified free-tier only"
- All bans logged with `banned_by` (admin username) and `reason`
- Active-bans panel at the bottom with one-click unban

### Public page updates

- **Prize callout** at the top with countdown to month-end at 00:00 UTC
- **PRO / FREE / unverified badges** on every row in every category
- **Past winners** section showing the last 3 months of #1 winners per model
- Flagged rows are excluded from all four categories (silent)

### IP capture disclosure

The submit endpoint records the connecting IP **for abuse moderation only**. Never shared, never analyzed for marketing, never geolocated, auto-purged 30 days after the row's last activity. Disclosed in [the privacy policy](https://bitaxeballer.com/privacy.html) and the [support FAQ](https://bitaxeballer.com/support.html).

### Stripe coupon generation

Runner-up coupons are generated via the Stripe API at draw time: a one-time `Coupon` (20% off, single redemption, 60-day `redeem_by`) plus a memorable `PromotionCode` (format `BB-MODEL-RANK-YYYYMM-XXXX`). Stripe handles the redemption logic; we just store the code reference in `leaderboard_winners` for audit.

## Compatibility

- v1.11 leaderboard rows are still on the board — they're treated as `tier='pro'` by default and remain eligible.
- The schema migration is idempotent and additive (`ALTER TABLE ... ADD COLUMN` wrapped in defensive try/catch for SQLite's missing `IF NOT EXISTS`).
- Existing `config.json` files without `install_uuid` get one auto-generated on first read. Existing `public_leaderboard` config without `email` is fine; it stays empty until the user opens the modal and fills it in.
- The auto-update appcast format is unchanged; v1.11.x Pro users get this through Sparkle as expected.

## Upgrading

- **Mac (Pro users):** Sparkle auto-update delivers v1.12.0 in-place. Banner on next launch, click "install & restart."
- **Mac (free users):** Banner with a one-click download link.
- **Windows:** Banner-with-download flow. Authenticode-signed via Azure Trusted Signing.
- **From source:** `git pull && python app.py` — no new dependencies.

## Under the hood — for developers

- `app.py`: `_install_uuid()` helper generates and persists a UUID4 in `config.json`. `_leaderboard_submit_one()` now branches on `is_pro_active()` — Pro path sends `license_key`; free path sends `install_uuid` + `email`. The `public_leaderboard` config block gains an `email` key.
- `bitaxe-baller-site/server/leaderboard-jobs.js` is new (~270 lines). Exports `monthKey`, `classifyModel`, `shortlistByModel`, `runMonthlyDraw`, `runDailyAutoDetection`. Idempotent draw — `(month_key, model, rank)` tuple in `leaderboard_winners` locks each prize.
- `bitaxe-baller-site/server/index.js`: schema migrations for `email`, `email_verified`, `install_uuid`, `tier`, `best_diff_month`, `month_started_at`, `ip_last_seen`, `flagged_at`, `flagged_reason` on `leaderboard`. Two new tables: `leaderboard_bans`, `leaderboard_verifications`, `leaderboard_winners`. Submit endpoint accepts both auth flows, captures IP from `X-Real-IP` / `CF-Connecting-IP`, enforces per-IP MAC throttle, triggers Resend verification email on new free-tier email. New routes: `GET /api/leaderboard/verify`, `GET /api/leaderboard/winners`, plus four admin POSTs (`/admin/leaderboard/:mac/{remove,ban,flag,unflag}` and `/admin/leaderboard/bans/:id/unban`).
- Cron loop: single `setInterval` that wakes every 30 minutes, runs daily detection once per UTC day, and runs the monthly draw on the first wake of day 1.
- No new Python dependencies. Node-side: no new npm packages — uses existing `stripe`, `better-sqlite3`, `crypto`.

## Known limitations in v1.12.0

- The auto-detection rule for MAC OUIs uses a hardcoded list of known Espressif prefixes. New ESP32 variants released after this codebase will need the list updated. False positives surface as flagged rows in `/admin`; manual unflag clears them.
- The 90-day winner cooldown is per-email. Someone with two emails could theoretically win consecutively under each. We considered IP-based or device-based cooldowns but went with email for simplicity; tighten if abuse appears.
- Stripe promotion codes are generated synchronously inside the draw cron. If Stripe is down at 00:00 UTC on the 1st, the runner-up coupons fail to mint and those rows get logged in `leaderboard_winners` with `email_sent_at = null` and no `stripe_promo_code`. Admin can manually issue replacements; cron will not retry the same `(month_key, model, rank)` tuple.
- Mobile apps don't render the prize callout or the verification flow yet. Native iOS / Android wrapper UI work tracked separately.
