# Email Blast Brief — point Cowork at this

Source for the next Bitaxe Baller newsletter (sent from **Acumbamail**). Audience: Bitaxe
solo miners. Tone: friendly, no-fluff, builder-to-builder.

> ⚠️ **Sequencing:** the firmware + remote fixes are **not released yet** — they ship in
> **v1.17.0**. Send the blast *after* that release. The YouTube channel is **already live**
> and can be announced now if you want a content-only send first.

---

## 1. 🎬 NEW: Bitaxe Baller is on YouTube (the headline)

We launched a YouTube channel with **13 short, no-fluff walkthrough videos** — dashboard
tour, tuning a Gamma, pool setup, adding miners, fixing the wrong-coin grouping, remote
access, viewing your fleet on your phone, what Pro includes, running on Umbrel, the
leaderboard, install warnings, and health/recommendations.

- **Channel:** https://www.youtube.com/@bitaxeballer
- **Why it matters to users:** quick visual how-tos for getting the most out of Baller —
  no digging through docs.
- The videos are also embedded in the matching FAQs at https://bitaxeballer.com/support.html

## 2. 🔧 v1.17.0: AxeOS firmware update alerts + Umbrel remote fix

- **AxeOS firmware update alerts.** Baller now tells you when your miners' firmware is
  out of date — a clear notice with "what's new" + "how to update" links. **Curated:**
  only versions we've vetted are flagged, so you're never nudged toward a risky release.
  - ⚠️ **Built today = the ALERTS only.** One-click bulk *updating* is the next phase —
    do **not** announce one-click updating as shipped unless that lands in this release.
- **Umbrel Pro remote fix.** Pro fleets on Umbrel now show your *full* fleet on the phone
  app / remote view immediately after activating Pro (it could previously stay capped at
  one miner until a restart).

### Free vs Pro on firmware updates — the upsell angle (use this!)

The firmware feature is built to grow into a clear Free/Pro split. **Be honest about what's
live vs coming** — the alert is the same for everyone today; the *effortless updating* is
the Pro payoff that's on the way.

| | **Free** | **Pro** |
|---|---|---|
| Out-of-date firmware alert | ✅ now | ✅ now |
| "What's new" + safe/vetted version info | ✅ now | ✅ now |
| How you actually update | Manually, **one miner at a time** — grab the two files (`www.bin` + `esp-miner.bin`) and flash each device yourself *(coming)* | **One click, whole fleet** — Baller fetches the vetted files and flashes every selected miner for you, in the right order *(coming)* |

- **The pitch:** "Got 4+ miners? Updating firmware by hand — two files, every device, in the
  right order — is the kind of chore Pro is *for*. One click, the whole fleet, safe versions
  only." That's the quality-of-life win that pushes a multi-miner owner from Free to Pro.
- ⚠️ Phrase the updating rows as **coming / in the works**, not shipped. What's shipped today
  is the alert (both tiers) — see the don'ts.

### While you're at it — the rest of what Pro already does (reminder block)

A blast is a good moment to re-pitch Pro to free users. **These are all LIVE today:**
bulk tuning across selected miners, auto-tune frequency sweeps with safety guardrails,
90 days of local SQLite history, Discord webhook alerts, email alerts, and remote dashboard
access to your **full** fleet (free remote is capped at 1 miner). **$29/year.**

## 3. (minor) Leaderboard verification email — self-resend

Didn't get your leaderboard verification email? There's now a self-serve resend at
https://bitaxeballer.com/leaderboard#resend (and Pro users' verification emails now send
correctly).

---

## Ready-to-paste changelog entry (when you cut v1.17.0)

The matching `<h2>` entry is **already staged as an HTML comment** at the top of
`public/changelog.html` in the site repo — just uncomment it, set the real date + release
URL, and deploy. (It deliberately says "alerts," not "updating.")

## Don'ts

- ❌ Don't announce one-click firmware **updating** — only the **alerts** are built.
- ❌ Don't send before **v1.17.0 is actually released** (the firmware alerts + Umbrel fix
  need that release — and the Umbrel image rebuild specifically — to reach users).
- ✅ Safe to send the **YouTube channel** announcement any time (it's live now).
