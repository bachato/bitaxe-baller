"""Permanent demo desktop for App Review testing.

Runs as a long-lived process on the bitaxeballer.com VPS. Connects to
the relay as a free-tier desktop with a fixed install_uuid (env var
DEMO_INSTALL_UUID). Responds to /api/devices and /api/device/<ip>
requests with a static-but-realistic mock fleet of 3 Bitaxe Gamma
miners. Lets Apple App Review reviewers self-test the iOS app by
visiting bitaxeballer.com/test-pair, getting a fresh 60-second pair
code, and pairing their reviewer iPhone with this demo desktop.

Free-tier means the relay only streams the FIRST device to any paired
iOS client (the tier-limit response filter we added in relay/main.py).
Reviewer sees a single Gamma; that's enough to validate the app works.

This is the desktop side of the App Review test arrangement. The
matching pair code generator is the /test-pair route on the site
server.

Run with:
    DEMO_INSTALL_UUID=<uuid> \\
    RELAY_WS=wss://relay.bitaxeballer.com \\
    python3 demo_desktop.py

Auto-reconnects on disconnect with exponential backoff capped at 60s.
Logs to stdout (systemd journal picks it up).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from urllib.parse import quote

import websockets


log = logging.getLogger("demo-desktop")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


# ----- Config -----
DEMO_INSTALL_UUID = os.environ.get("DEMO_INSTALL_UUID", "").strip()
RELAY_WS = os.environ.get("RELAY_WS", "wss://relay.bitaxeballer.com").rstrip("/")
PING_INTERVAL_S = 30

if not DEMO_INSTALL_UUID:
    raise SystemExit("DEMO_INSTALL_UUID env var is required (must match site server's value).")


# ----- Mock fleet -----
# Three Bitaxe Gammas at realistic-looking operating points. Free-tier
# relay only streams [0] to iOS, but we include all three so the desktop
# /api/devices response looks complete from the relay's perspective.
_BOOT_TIME = time.time()


def _uptime() -> int:
    return int(time.time() - _BOOT_TIME) + 3 * 86400  # pretend it's been up 3 days


def _device_summary(idx: int, ip: str, label: str, freq: int, voltage: int, temp: float) -> dict:
    """Build a device summary matching app.py's device_summary() shape."""
    ghs = round(freq * 2.04, 1)  # the BM1370 empirical ratio used by app.py
    power = round(ghs * 0.018, 2)  # ~18 J/TH ≈ 18 W per TH/s
    j_per_th = round(power / (ghs / 1000), 2) if ghs > 0 else 0
    return {
        "ip": ip,
        "label": label,
        "online": True,
        "lastError": "",
        "model": "BM1370",
        "version": "2.13.1",
        "hostname": f"bitaxe{idx}",
        "macAddr": f"D8:3B:DA:00:00:{idx:02X}",
        "metrics": {
            "hashRate": ghs,
            "temp": temp,
            "vrTemp": round(temp - 3.0, 1),
            "power": power,
            "voltage": voltage * 4,  # board voltage ≈ 4x core
            "coreVoltage": voltage,
            "frequency": freq,
            "fanSpeed": 4200,
            "fanPercent": 65,
            "autofanspeed": 1,
            "sharesAccepted": 1234 + idx * 100,
            "sharesRejected": 2 + idx,
            "bestDiff": ("1.21G", "892M", "445M")[idx % 3],
            "bestDiffValue": (1210000000.0, 892000000.0, 445000000.0)[idx % 3],
            "bestSessionDiff": ("234M", "189M", "112M")[idx % 3],
            "bestSessionDiffValue": (234000000.0, 189000000.0, 112000000.0)[idx % 3],
            "poolDifficulty": 2048,
            "uptime": _uptime(),
            "stratumUrl": "solo.ckpool.org",
        },
        "shares": {
            "sessionAccepted": 1234 + idx * 100,
            "sessionRejected": 2 + idx,
            "lifetimeAccepted": 23456 + idx * 1000,
            "lifetimeRejected": 18 + idx * 2,
            "perMin": round(1.4 + idx * 0.1, 2),
            "sessionSecs": _uptime(),
        },
        "rolling": {
            "1m": ghs,
            "5m": round(ghs * 0.99, 1),
            "15m": round(ghs * 0.98, 1),
            "1h": round(ghs * 0.97, 1),
        },
        "efficiency": {
            "jPerTh": j_per_th,
            "expectedGhs": ghs,
        },
        "history": [
            {
                "ts": int(time.time()) - i * 5,
                "hashRate": round(ghs + (i % 5 - 2) * 5, 1),
                "temp": round(temp + (i % 4 - 1) * 0.4, 1),
                "vrTemp": round(temp - 3.0 + (i % 4 - 1) * 0.3, 1),
                "power": power,
                "fanPercent": 65,
                "frequency": freq,
                "coreVoltage": voltage,
            }
            for i in range(60)
        ],
        "events": [],
        "shareEvents": [],
        "recommendations": [],
        "severity": None,
        "blockProbability": {
            "chain": "BTC",
            "networkDifficultyT": 110000,
            "rewardUsd": 250000,
            "daily": {"odds": int(60000 * 1e12 / (ghs * 1e9 * 86400 + 1)), "label": "1 in 60k"},
            "monthly": {"odds": int(2000 * 1e12 / (ghs * 1e9 * 86400 * 30 + 1)), "label": "1 in 2k"},
            "yearly": {"odds": int(150 * 1e12 / (ghs * 1e9 * 86400 * 365 + 1)), "label": "1 in 150"},
            "proximity": 0.62,
            "bestDiff": (1210000000.0, 892000000.0, 445000000.0)[idx % 3],
        },
    }


def fleet_summary() -> list:
    """Return the demo fleet's full /api/devices response."""
    return [
        _device_summary(0, "192.168.50.137", "demo-gamma-1", 575, 1185, 61.5),
        _device_summary(1, "192.168.50.138", "demo-gamma-2", 550, 1170, 59.8),
        _device_summary(2, "192.168.50.139", "demo-gamma-3", 600, 1200, 64.2),
    ]


def one_device(ip: str) -> tuple[int, dict | list]:
    """Return (status, body) for /api/device/<ip>."""
    for d in fleet_summary():
        if d["ip"] == ip:
            return 200, d
    return 404, {"error": "device not found"}


# ----- Relay client -----
async def _serve_one_request(ws, msg: dict) -> None:
    """Handle one parsed message from the relay."""
    mtype = msg.get("type")
    if mtype == "ping":
        await ws.send(json.dumps({"type": "pong"}))
        return
    if mtype != "request":
        # Forward-compat: ignore unknown
        return

    req_id = msg.get("id") or ""
    method = (msg.get("method") or "").upper()
    path = msg.get("path") or ""

    log.info("relay request id=%s method=%s path=%s", req_id, method, path)

    if method != "GET":
        body = {"error": "Demo desktop is read-only."}
        status = 403
    elif path == "/api/devices":
        body = fleet_summary()
        status = 200
    elif path.startswith("/api/device/") and not path.endswith("/history"):
        ip = path[len("/api/device/"):]
        status, body = one_device(ip)
    elif path == "/api/leaderboard/status":
        body = {"pro_active": False, "configured": {"enabled": False}, "install_uuid": DEMO_INSTALL_UUID}
        status = 200
    elif path == "/api/remote/status":
        body = {"pro_required": False, "pro_active": False, "configured": {"enabled": True}, "runtime": {"connected": True}}
        status = 200
    elif path == "/api/config":
        body = {"poll_interval_s": 5, "devices": [d["ip"] for d in fleet_summary()]}
        status = 200
    elif path == "/api/update-check":
        # Match the shape used by the real desktop's auto-update flow
        body = {"current": "demo-1.0.0", "latest": "demo-1.0.0", "newer_available": False}
        status = 200
    else:
        body = {"error": f"Demo desktop does not implement {path}"}
        status = 404

    await ws.send(json.dumps({"type": "response", "id": req_id, "status": status, "body": body}))


async def _connect_and_serve() -> None:
    url = f"{RELAY_WS}/ws/app?install_uuid={quote(DEMO_INSTALL_UUID, safe='')}"
    log.info("connecting url=%s", url)
    async with websockets.connect(
        url,
        open_timeout=15,
        close_timeout=5,
        ping_interval=PING_INTERVAL_S,
        ping_timeout=15,
        max_size=512 * 1024,
    ) as ws:
        log.info("connected as demo desktop install_uuid=%s", DEMO_INSTALL_UUID)
        await ws.send(json.dumps({"type": "hello", "version": "demo-1.0.0"}))

        while True:
            raw = await ws.recv()
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if not isinstance(msg, dict):
                continue
            try:
                await _serve_one_request(ws, msg)
            except Exception:
                log.exception("error handling msg=%r", msg)


async def main() -> None:
    backoff = 1.0
    while True:
        try:
            await _connect_and_serve()
            backoff = 1.0
        except websockets.ConnectionClosed as e:
            log.warning("connection closed code=%s reason=%s", e.code, e.reason)
        except Exception as e:
            log.warning("relay connect failed: %s: %s", e.__class__.__name__, e)
        log.info("reconnecting in %.1fs", backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60.0)


if __name__ == "__main__":
    asyncio.run(main())
