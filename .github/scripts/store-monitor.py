#!/usr/bin/env python3
"""
Store-version monitor for the Bitaxe Baller mobile companion.

Runs hourly via .github/workflows/store-version-monitor.yml. Polls:

  - Apple App Store via the public iTunes Search API (clean JSON, no auth).
    Returns `version` + `currentVersionReleaseDate` reliably.

  - Google Play Store via the unofficial google-play-scraper Python library
    (it parses Play's internal JSON callback blob). The public Play HTML
    returns "Varies with device" for version because of multi-ABI bundles,
    so we instead watch (recentChanges text, released date, summary).
    When any of those change we treat it as "a new release went live" and
    ping Discord.

State is persisted to .github/store-versions.json (committed back by the
workflow). On every state change we POST a Discord message via the
DISCORD_RELEASE_WEBHOOK secret — same channel that gets desktop release
pings, so all platform shipping news lands in one place.

Exit codes:
  0 = ran clean (state may or may not have changed)
  1 = transient fetch error (workflow will alert if it persists)
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

IOS_APP_ID = "6773373318"
ANDROID_PKG = "com.bitaxeballer.mobile"
STATE_PATH = Path(__file__).resolve().parent.parent / "store-versions.json"
WEBHOOK_URL = os.environ.get("DISCORD_RELEASE_WEBHOOK", "").strip()


def fetch_app_store():
    """Returns {version, currentVersionReleaseDate, releaseNotes} or raises."""
    url = f"https://itunes.apple.com/lookup?id={IOS_APP_ID}&country=us"
    req = urllib.request.Request(url, headers={"User-Agent": "BitaxeBaller-Monitor/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    results = data.get("results") or []
    if not results:
        raise RuntimeError("iTunes lookup returned no results")
    r = results[0]
    return {
        "version": r.get("version"),
        "currentVersionReleaseDate": r.get("currentVersionReleaseDate"),
        "releaseNotes": (r.get("releaseNotes") or "").strip()[:1000],
        "trackName": r.get("trackName"),
    }


def fetch_play_store():
    """Returns {released, recentChanges, realInstalls, summary, ...} or raises."""
    try:
        from google_play_scraper import app
    except ImportError as e:
        raise RuntimeError(
            "google-play-scraper not installed. "
            "Add `pip install google-play-scraper` to the workflow."
        ) from e
    r = app(ANDROID_PKG, country="us", lang="en")
    return {
        "version": r.get("version"),
        "released": r.get("released"),
        "recentChanges": (r.get("recentChanges") or "").strip()[:1000] or None,
        "realInstalls": r.get("realInstalls"),
        "summary": (r.get("summary") or "").strip()[:200],
    }


def post_discord(message):
    if not WEBHOOK_URL:
        print("DISCORD_RELEASE_WEBHOOK not set — skipping post", file=sys.stderr)
        return
    body = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        print(f"Discord webhook returned {e.code}: {e.read()[:200]}", file=sys.stderr)
        raise


def ios_changed(old, new):
    if not old:
        return False
    return (
        old.get("version") != new.get("version")
        or old.get("currentVersionReleaseDate") != new.get("currentVersionReleaseDate")
    )


def android_changed(old, new):
    if not old:
        return False
    return (
        old.get("recentChanges") != new.get("recentChanges")
        or old.get("released") != new.get("released")
        or old.get("summary") != new.get("summary")
    )


def fmt_ios_msg(new):
    notes = new.get("releaseNotes") or "(no release notes provided)"
    return (
        f"\U0001F34E **iOS — Bitaxe Baller v{new['version']} is LIVE on the App Store** "
        f"(released {new['currentVersionReleaseDate']}).\n\n"
        f"**What's new:**\n```\n{notes}\n```\n"
        f"<https://apps.apple.com/us/app/bitaxe-baller/id{IOS_APP_ID}>"
    )


def fmt_android_msg(new, changed_fields):
    bits = ["\U0001F916 **Android — Bitaxe Baller updated on Google Play**"]
    if new.get("recentChanges"):
        bits.append(f"\n**What's new:**\n```\n{new['recentChanges']}\n```")
    bits.append(f"Released: {new.get('released')}")
    bits.append(f"Installs: {new.get('realInstalls')}")
    bits.append(f"Changed fields: {', '.join(changed_fields)}")
    bits.append(f"<https://play.google.com/store/apps/details?id={ANDROID_PKG}>")
    return "\n".join(bits)


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def main():
    state = load_state()
    old_ios = state.get("ios") or {}
    old_android = state.get("android") or {}

    try:
        new_ios = fetch_app_store()
        if ios_changed(old_ios, new_ios):
            print(f"iOS change: {old_ios.get('version')} -> {new_ios.get('version')}")
            post_discord(fmt_ios_msg(new_ios))
    except Exception as e:
        print(f"App Store fetch failed: {e}", file=sys.stderr)
        new_ios = old_ios or None

    try:
        new_android = fetch_play_store()
        changed_fields = []
        for field in ("recentChanges", "released", "summary"):
            if old_android.get(field) != new_android.get(field):
                changed_fields.append(field)
        if android_changed(old_android, new_android):
            print(f"Android change in fields: {changed_fields}")
            post_discord(fmt_android_msg(new_android, changed_fields))
    except Exception as e:
        print(f"Play Store fetch failed: {e}", file=sys.stderr)
        new_android = old_android or None

    new_state = {}
    if new_ios:
        new_state["ios"] = new_ios
    if new_android:
        new_state["android"] = new_android
    save_state(new_state)
    print(f"State saved to {STATE_PATH}")


if __name__ == "__main__":
    main()
