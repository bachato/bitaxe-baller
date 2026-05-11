# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Bitaxe Baller. Builds:
#   - dist/Bitaxe Baller.app (macOS, when run on macOS)
#   - dist/Bitaxe Baller/Bitaxe Baller.exe (Windows, when run on Windows)
#
# Invoke from the repo root:
#   pyinstaller --noconfirm build/bitaxe-baller.spec
#
# Code signing + notarization happen in build-mac.sh after this produces the .app.

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = os.path.abspath(os.path.dirname(SPEC) if "SPEC" in globals() else os.getcwd())
# Allow running the spec from either the repo root or build/ dir
if not os.path.exists(os.path.join(ROOT, "app.py")):
    ROOT = os.path.abspath(os.path.join(ROOT, ".."))

# zeroconf has many private submodules that PyInstaller's static analysis
# can't all detect — the package uses lazy imports in places. collect_submodules
# walks the install and grabs every importable module.
ZEROCONF_HIDDEN = collect_submodules("zeroconf")

# pywebview ships platform-specific backends (cocoa on macOS, edgechromium on
# Windows, gtk on Linux) loaded via importlib at runtime. Same trick: grab
# everything in the package so the right backend module is bundled.
WEBVIEW_HIDDEN = collect_submodules("webview")
WEBVIEW_DATA = collect_data_files("webview")

ICON_MAC = os.path.join(ROOT, "build", "icons", "icon.icns")
ICON_WIN = os.path.join(ROOT, "build", "icons", "icon.ico")

block_cipher = None

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[
        (os.path.join(ROOT, "templates"), "templates"),
        (os.path.join(ROOT, "static"), "static"),
    ] + WEBVIEW_DATA,
    hiddenimports=ZEROCONF_HIDDEN + WEBVIEW_HIDDEN,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Trim things we definitely don't need
        "tkinter",
        "test",
        "unittest",
        "pdb",
        "doctest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Bitaxe Baller",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,           # windowed — no terminal popup on launch
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,        # arm64 on Apple Silicon, x86_64 on Intel; universal2 needs special setup
    codesign_identity=None,  # signing happens in build-mac.sh
    entitlements_file=None,
    icon=ICON_MAC if sys.platform == "darwin" else ICON_WIN,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Bitaxe Baller",
)

# Wrap as a proper Mac .app bundle on macOS
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Bitaxe Baller.app",
        icon=ICON_MAC,
        bundle_identifier="com.465-media.bitaxe-baller",
        version="1.6.2",
        info_plist={
            "CFBundleShortVersionString": "1.6.2",
            "CFBundleVersion": "1.6.2",
            "NSHumanReadableCopyright": "© 2026 Nathan Baldwin / 465 Media. MIT-licensed source.",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
            # Bitaxes serve plaintext HTTP only — Apple Transport Security
            # needs an exception so we can talk to local IPs over http://
            "NSAppTransportSecurity": {
                "NSAllowsArbitraryLoads": True,
                "NSAllowsLocalNetworking": True,
            },
            # Triggers the macOS Local Network privacy prompt the first time
            # the app polls a Bitaxe. Wording shows up in the prompt.
            "NSLocalNetworkUsageDescription":
                "Bitaxe Baller talks to Bitaxe miners on your local network to monitor temps, hashrate, and apply tuning.",
            # mDNS service we publish for the dashboard URL
            "NSBonjourServices": ["_http._tcp"],
            # No dock icon hopping — we're a monitor, not a foreground app per se,
            # but keep agent-mode off so users see a normal dock icon and can quit.
            "LSUIElement": False,
        },
    )
