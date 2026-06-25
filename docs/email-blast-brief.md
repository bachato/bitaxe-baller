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
