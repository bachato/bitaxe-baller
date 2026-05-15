#!/usr/bin/env python3
"""
Build/refresh appcast.xml — the feed the app polls to discover updates.

Schema: Sparkle 2.x appcast (https://sparkle-project.org/documentation/publishing/).
We follow Sparkle's schema even though we're using a pure-Python updater on
the client side, so the file stays compatible if we ever swap consumers
(e.g. dropping Sparkle.framework in later).

Usage:
    python build/build-appcast.py \\
        --version 1.8.2 \\
        --mac-dmg dist/Bitaxe-Baller-Mac.dmg \\
        --win-exe dist/Bitaxe-Baller-Windows.exe \\
        --release-notes-url https://github.com/465media/bitaxe-baller/releases/tag/v1.8.2 \\
        --out dist/appcast.xml

You can omit --win-exe (or --mac-dmg) if you're only producing one platform's
artifact in this run — the script merges into an existing appcast.xml at --out
if it exists, so successive runs accumulate.
"""

import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime


GITHUB_RELEASE_BASE = "https://github.com/465media/bitaxe-baller/releases/download"

NS_SPARKLE = "http://www.andymatuschak.org/xml-namespaces/sparkle"
ET.register_namespace("sparkle", NS_SPARKLE)


def sign(artifact: str) -> str:
    """Shell out to sign-release.py so the signing-key plumbing lives in one place."""
    here = os.path.dirname(os.path.abspath(__file__))
    out = subprocess.check_output(
        [sys.executable, os.path.join(here, "sign-release.py"), artifact],
        text=True,
    )
    return out.strip()


def make_item(version: str, platform: str, artifact_path: str, notes_url: str) -> ET.Element:
    """Build one <item> for the given platform. `platform` is 'macos' or 'windows'."""
    size = os.path.getsize(artifact_path)
    filename = os.path.basename(artifact_path)
    url = f"{GITHUB_RELEASE_BASE}/v{version}/{filename}"
    signature = sign(artifact_path)
    pub_date = format_datetime(datetime.now(timezone.utc))

    item = ET.Element("item")
    ET.SubElement(item, "title").text = f"Version {version}"
    ET.SubElement(item, "pubDate").text = pub_date
    if notes_url:
        ET.SubElement(item, "{%s}releaseNotesLink" % NS_SPARKLE).text = notes_url

    enclosure = ET.SubElement(item, "enclosure")
    enclosure.set("url", url)
    enclosure.set("length", str(size))
    enclosure.set("type", "application/octet-stream")
    enclosure.set("{%s}version" % NS_SPARKLE, version)
    enclosure.set("{%s}shortVersionString" % NS_SPARKLE, version)
    enclosure.set("{%s}edSignature" % NS_SPARKLE, signature)
    enclosure.set("{%s}os" % NS_SPARKLE, platform)
    if platform == "macos":
        enclosure.set("{%s}minimumSystemVersion" % NS_SPARKLE, "12.0")
    return item


def load_or_create_channel(out_path: str) -> tuple[ET.ElementTree, ET.Element]:
    if os.path.exists(out_path):
        tree = ET.parse(out_path)
        channel = tree.getroot().find("channel")
        if channel is None:
            sys.exit(f"existing {out_path} has no <channel> — refusing to clobber")
        return tree, channel

    rss = ET.Element("rss", attrib={"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Bitaxe Baller"
    ET.SubElement(channel, "link").text = "https://bitaxeballer.com/appcast.xml"
    ET.SubElement(channel, "description").text = "Auto-update feed for Bitaxe Baller."
    ET.SubElement(channel, "language").text = "en"
    return ET.ElementTree(rss), channel


def drop_existing_version(channel: ET.Element, version: str, platform: str) -> None:
    """Replace any existing item for this (version, platform) so reruns are idempotent."""
    for item in list(channel.findall("item")):
        enc = item.find("enclosure")
        if enc is None:
            continue
        v = enc.get("{%s}shortVersionString" % NS_SPARKLE)
        p = enc.get("{%s}os" % NS_SPARKLE)
        if v == version and p == platform:
            channel.remove(item)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True, help="e.g. 1.8.2 (no leading v)")
    p.add_argument("--mac-dmg", help="path to the signed/notarized .dmg")
    p.add_argument("--win-exe", help="path to the signed .exe installer")
    p.add_argument("--release-notes-url", default="")
    p.add_argument("--out", default="dist/appcast.xml")
    args = p.parse_args()

    if not args.mac_dmg and not args.win_exe:
        p.error("at least one of --mac-dmg / --win-exe is required")

    tree, channel = load_or_create_channel(args.out)

    if args.mac_dmg:
        drop_existing_version(channel, args.version, "macos")
        channel.append(make_item(args.version, "macos", args.mac_dmg, args.release_notes_url))

    if args.win_exe:
        drop_existing_version(channel, args.version, "windows")
        channel.append(make_item(args.version, "windows", args.win_exe, args.release_notes_url))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    ET.indent(tree, space="  ")
    tree.write(args.out, encoding="utf-8", xml_declaration=True)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
