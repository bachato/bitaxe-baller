"""Look up a paired iOS/Android device_token against the site server.

Wrapper around GET /api/relay/device-info (defined in bitaxe-baller-site/
server/index.js). Caches results briefly to avoid hammering the site
server on every iOS WebSocket message (we look up once at connect time,
re-fetch only after DEVICE_INFO_CACHE_S has elapsed).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

import config


class DeviceLookupError(Exception):
    """Raised when device_token validation fails (revoked, unknown, network)."""


@dataclass
class DeviceInfo:
    id: str
    install_uuid_paired: str
    tier_at_pair: str                       # 'free' or 'pro'
    device_label: Optional[str]
    platform: Optional[str]                 # 'ios' | 'android'


_cache: dict[str, tuple[float, DeviceInfo]] = {}


def lookup(device_token: str) -> DeviceInfo:
    """Resolve a device_token → which install_uuid it pairs to + tier.

    Raises DeviceLookupError on any failure mode. Caches successful
    lookups for `config.DEVICE_INFO_CACHE_S` seconds.
    """
    key = (device_token or "").strip()
    if not key:
        raise DeviceLookupError("Missing device_token.")

    now = time.time()
    cached = _cache.get(key)
    if cached is not None and (now - cached[0]) < config.DEVICE_INFO_CACHE_S:
        return cached[1]

    try:
        r = requests.get(
            f"{config.SITE_API_BASE}/api/relay/device-info",
            headers={
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
            },
            timeout=config.DEVICE_INFO_TIMEOUT_S,
        )
    except requests.RequestException as e:
        raise DeviceLookupError(f"Device lookup unavailable: {e.__class__.__name__}.") from e

    try:
        payload = r.json()
    except ValueError:
        raise DeviceLookupError(f"Device lookup returned HTTP {r.status_code}.")

    if r.status_code == 401:
        # Negative cache for revoked tokens to avoid hammering the site
        # server with bad attempts. Short TTL so legitimate re-pairs
        # become visible quickly.
        raise DeviceLookupError(payload.get("error") or "Device token is invalid or revoked.")
    if r.status_code == 503:
        raise DeviceLookupError("Pairing is disabled on the site server.")
    if r.status_code >= 400:
        raise DeviceLookupError(payload.get("error") or f"Device lookup returned HTTP {r.status_code}.")

    install_uuid = payload.get("install_uuid_paired") or ""
    tier = (payload.get("tier_at_pair") or "").lower()
    if not install_uuid or tier not in ("free", "pro"):
        raise DeviceLookupError("Device lookup returned an unexpected payload.")

    info = DeviceInfo(
        id=payload.get("id") or key,
        install_uuid_paired=install_uuid,
        tier_at_pair=tier,
        device_label=payload.get("device_label"),
        platform=payload.get("platform"),
    )
    _cache[key] = (now, info)
    return info


def invalidate(device_token: str) -> None:
    """Drop a cached lookup. Call when the relay detects the token is
    no longer valid (e.g. /device-info returned 401 mid-session)."""
    _cache.pop((device_token or "").strip(), None)
