# Pro tier testing checklist

Built across two sessions (2026-05-13 + 2026-05-14). Nothing is committed — review `git diff` before staging.

## Setup

1. `cd /Users/nbaldwin/development/bitaxe-baller`
2. `source venv/bin/activate`
3. `BITAXE_BALLER_DEV_PRO=1 python app.py` — flips Pro on locally without a real license
4. Open `http://localhost` (or whatever port the banner prints)

You should see a green **Pro** button in the header. Click it — the modal shows an **orange "Dev override"** badge confirming you're in dev mode (not a real subscription). The deactivate button is hidden in dev mode (you turn it off by unsetting the env var).

## What to test

### 1. License flow (dev override path)

- [ ] With `BITAXE_BALLER_DEV_PRO=1`: Pro button glows green, modal shows orange dev badge
- [ ] Without the env var: Pro button is dim, modal shows the paste-key form, all Pro features show "Activate Pro →" teasers
- [ ] Activate modal: paste any fake `bb-...` string → friendly error: "License key not recognized..."

### 2. Bulk tuning (home page)

- [ ] Each card has a checkbox in the top-left corner
- [ ] Click checkbox → toolbar appears between the summary cards and the device grid showing "N selected"
- [ ] "select all" / "clear" buttons work
- [ ] Click a preset button (e.g. "Balanced") → confirm dialog → all selected devices change to that preset
- [ ] Verify by curling one of the Gammas: `curl http://192.168.1.223/api/system/info | jq '.frequency, .coreVoltage'`
- [ ] "manual settings…" expands a row with freq / voltage / fan / autofan inputs + "apply manual" button — verify out-of-bounds values get rejected server-side
- [ ] Free tier: checkboxes show as locked (dashed border). Clicking opens the Pro modal instead of selecting.

### 3. Long-term history (device detail page)

- [ ] Click any device card → device detail page
- [ ] Scroll down — see new "long-term history" section with `24h | 7d | 30d | 90d` buttons
- [ ] After running Pro for ~5 minutes, the 24h chart should show data (30s buckets)
- [ ] Switch between ranges — chart redraws with appropriate bucket size
- [ ] Header text shows "N points · X-min buckets"
- [ ] Free tier: same section shows a "Pro unlocks..." teaser with an Activate button

### 4. Auto-tune sweep (device detail page)

⚠ **This one actually drives your hardware.** Test on `192.168.1.223` (your test Gamma), not on your production setup if you have one.

- [ ] Idle state: "Probe this chip's stable frequency ceiling. Starts at <current> MHz, steps +25 MHz every 90s." + max freq input + start button
- [ ] Click start → confirm dialog → status flips to "● running" with step counter + countdown
- [ ] Watch the events log inside the panel as the sweep progresses
- [ ] Stop button → "stopped by user" → status="aborted" → verify the Gamma's frequency reverted to baseline: `curl http://192.168.1.223/api/system/info | jq '.frequency'`
- [ ] If you let it run to completion: should declare a "best stable" frequency and apply it (could be unchanged, +25, +50, etc. depending on the chip)
- [ ] Hard safety: it'll abort instantly if VR or ASIC temp ≥ 65°C, or HW errors ≥ 5%. The baseline always gets restored on abort.
- [ ] Free tier: locked teaser, no controls

### 5. Alerts (collapsible section near footer of home page)

- [ ] Find the "🔔 alerts PRO" section at the bottom of the dashboard, above the footer
- [ ] Click to expand
- [ ] Pro: shows the config form with rules + cooldown + Discord webhook input + save/test buttons
- [ ] Free tier: shows "Get pinged on Discord..." teaser
- [ ] Paste an invalid webhook URL (not starting with `https://discord.com/api/webhooks/`) → 400 error
- [ ] Paste your real Discord webhook URL + save
- [ ] Hit "test" → check the Discord channel — you should get a test message
- [ ] To smoke-test the offline alert: unplug one of your Gammas. After `offline_minutes` (default 5), you should get a Discord alert. Plug it back in to clear.
- [ ] To smoke-test the temp alert: temporarily set VR or ASIC threshold to a value below the current actual temp + save. You should get an alert within one poll cycle.

### 6. Expected hashrate fix (any device card)

- [ ] On the device detail page, find the "expected" metric — should now match AxeOS exactly (uses firmware's `expectedHashrate` field, not the old 2.28 multiplier)
- [ ] Tooltip on that row should mention "taken directly from the firmware's reported value"
- [ ] If your Gamma is at 575 MHz, expected should read 1173 GH/s (575 × 2040 / 1000)

## Payment processor — switched to Lemon Squeezy

Polar denied 465 Media's account for crypto-adjacency. Pivoted to Lemon Squeezy (Stripe-backed). Same general pattern: embed checkout overlay, license-key validation API, webhooks.

**LS identifiers (already wired in code + on the site):**
- Store ID: `375578` (BitAxe Baller, `bitaxe-baller.lemonsqueezy.com`)
- Product ID: `1055450` (Yearly Pro, $29/year, license keys enabled, 5 activations)
- Variant ID: `1655081`
- Public buy URL: `https://bitaxe-baller.lemonsqueezy.com/checkout/buy/fcc9e248-8900-447c-9d79-d59e4c879057`
- Embed script: `https://assets.lemonsqueezy.com/lemon.js` (auto-intercepts `.lemonsqueezy-button` clicks)

### Still needed before launch

- [ ] **LS store approval** — variant currently shows status `pending` in the API. Likely waiting on KYC / payouts setup. Until approved, real charges won't go through. (API + integration work fine in the meantime.)
- [ ] **Success URL** in LS dashboard → Settings → Store / variant settings → Redirect URL: `https://bitaxeballer.com/pro/thanks.html` (LS auto-appends `?order_id=...&order_number=...`; the thanks page reads those)
- [ ] **Webhook endpoint** — LS dashboard → Settings → Webhooks → Create. Point at `https://bitaxeballer.com/api/webhooks/lemonsqueezy`. Subscribe to events: `order_created`, `subscription_created`, `subscription_payment_success`, `subscription_payment_failed`, `subscription_cancelled`, `license_key_created`. LS gives you a signing secret — drop it in `/etc/bitaxe-baller-site.env` as `LEMONSQUEEZY_WEBHOOK_SECRET=...` when we get to building the route.
- [ ] **Real test license** — once LS supports comp grants (or after store approval), issue yourself a $0 license to verify the real activation flow end-to-end. Until then, dev override (`BITAXE_BALLER_DEV_PRO=1`) covers all Pro-feature testing.

## After testing

If everything looks good:
1. `git diff` to review (4 files: `app.py`, `static/common.js`, `static/style.css`, `templates/dashboard.html`, `templates/device.html`, plus the new `TESTING_PRO.md`)
2. Bump the version in `app.py:28` (APP_VERSION), `build/bitaxe-baller.spec`, `build/installer.iss`, `templates/dashboard.html` footer, `templates/device.html` footer to `1.8.0`
3. Update `CHANGELOG.md` (or whatever you use) with the v1.8 entries:
   - Pro tier launched: license activation via Lemon Squeezy
   - Pro: bulk tuning across selected devices
   - Pro: long-term history (90 days persistent SQLite)
   - Pro: auto-tune frequency sweeps with safety guardrails
   - Pro: Discord webhook alerts (offline / VR / ASIC thresholds)
   - Fix: "expected hashrate" now matches AxeOS (uses firmware's reported value)
4. Commit, tag `v1.8.0`, push, let CI build the Mac + Windows binaries

## Known limitations / explicitly NOT in v1.8

- **Email alerts** — punted to v1.8.1. Discord covers most Bitaxe folks.
- **HW-error-rate-sustained alert** — punted to v1.8.1. Bigger logic, more state to track.
- **Voltage tuning in auto-tune** — punted to v2.0. v1 is frequency-only on purpose for safety.
- **Auto-updates (Sparkle/WinSparkle)** — depends on Windows code-signing cert. Free-tier v1.7 banner stays in place until that lands.
- **Fleet-across-networks** — significant cloud relay infra. Not on the v1.8 launch list.
