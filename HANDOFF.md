# Bitaxe Baller — Project Handoff

Living state snapshot for picking this up in a fresh Claude Code session. **Keep this current** — stale handoffs are the #1 cause of lost context between sessions. Update the "Current state" and "Open threads" sections whenever something meaningful ships.

_Last updated: 2026-06-18 · Current version: **v1.16.3** (shipped 2026-06-17)_

## What this is

A monitoring + tuning product for Bitaxe Gamma (BM1370) miners, built around a Flask app + vanilla-JS dashboard. It is **not** a single app — it ships through five distribution channels across three repos. The checked-in `CLAUDE.md` has the authoritative architecture + ecosystem map; read it first. Don't trust version strings in any doc — verify against `git`/`gh`.

Built for Nate's Gammas. Test device on his LAN: `192.168.1.223` (BM1370, firmware v2.13.1).

## The five channels (see CLAUDE.md for the full table)

1. **macOS desktop** — signed + notarized DMG. Built locally (`build/build-mac.sh` + `release-mac.sh`). ✅ on 1.16.3.
2. **Windows desktop** — Authenticode-signed EXE, built in CI on tag push. ✅ on 1.16.3.
3. **Umbrel self-host** — Docker image + `465media/umbrel-bitaxe-baller-store`. ⚠️ manifests still at **1.16.2** — not yet bumped.
4. **iOS** — live in App Store (v1.2.2). Source **not in `465media`** — location TBD.
5. **Android** — live in Play Store. Source **not in `465media`** — location TBD.

The **relay** (`relay/`, deployed at `relay.bitaxeballer.com`) is the spine connecting desktop ⇄ remote browser ⇄ mobile.

## Current state (2026-06-18)

- v1.16.3 is a no-op maintenance/version bump, shipped to verify the in-app update banner. Live on Mac + Windows + Docker; appcast serves both desktop platforms.
- Umbrel manifests NOT yet bumped to 1.16.3 (deliberate — it's a separate digest-pin step, and avoids surfacing a no-op release to Umbrel users).
- Update-banner UX gap noted: the dashboard only checks for updates once at page load + a 1h server cache, so a left-open tab won't notice a new release until reloaded. A periodic `setInterval` re-check is a cheap fix that's been discussed but not built.

## How to release

Follow the `release-process` memory file — the steps are order-sensitive (version-bump checklist → merge to main → `gh release create` triggers Win/Docker/Discord CI → local Mac build → `release-mac.sh` merges the Mac entry into the appcast AFTER Windows CI → separate Umbrel digest bump). Signing secrets live in the **main** repo's `build/` (`.env.signing`, `.update-signing-key`), not in worktrees.

## Open threads / roadmap (see PRO_FEATURES.md for full scoping)

- **Umbrel 1.16.3 bump** — pin new Docker digest + manifest notes (small, finishes the current release).
- **Pool scheduler + Power scheduler / standby (Pro)** — should ship as one combined per-device "Schedule" engine (timezone + offline-retry). Builds on the shipped pool-profiles MVP. ~1 day.
- **Bulk firmware / AxeOS flasher (Pro)** — phased, sequential-only. ~3 days Phase 1.
- **Live share feed + best-shares leaderboard** — mostly UI, free-tier candidate.
- **Tuning-over-relay** — remote dashboard is read-only today; write/tune path was parked.
- **Mobile build-out** — continue iOS + Android (need their source location first).

## Picking up cold

> Read CLAUDE.md and the memory files (`project-ecosystem-map`, `release-process`), then verify the live version with `gh release list`. Tell me which of the five channels we're touching and I'll confirm current state before changing anything.
