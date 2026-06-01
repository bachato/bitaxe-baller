from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import WebSocket


@dataclass
class AppConn:
    """One connected app instance.

    Phase 1 (pre-pairing): keyed by license_key only, allowed only one app
    socket per license key — a new connection evicts the old one (e.g. user
    restarts the app, the stale socket gets closed).

    iOS v1.1 (pairing): AppConn can now also carry an install_uuid, allowing
    free-tier desktops (no license) to connect using install_uuid as their
    identity. Pro desktops can send both. Registry indexes by whichever
    fields are populated. `tier` snapshots the desktop's tier at connect
    time and drives response stripping for paired iOS devices (free=1 miner
    max, pro=full fleet).

    `pending` maps relay-allocated request IDs → Futures that resolve when
    the app sends back a matching response. The Future's result is the raw
    decoded message dict.
    """
    license_key: str                                   # empty string for free-tier-only connections
    ws: WebSocket
    tier: str = "pro"                                  # 'pro' (license-validated) or 'free'
    install_uuid: str = ""                             # empty for legacy Pro connections that don't send it
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    pending: dict[str, asyncio.Future] = field(default_factory=dict)
    connected_at: float = field(default_factory=time.time)
    last_client_traffic: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_client_traffic = time.time()

    def idle_seconds(self) -> float:
        return time.time() - self.last_client_traffic


class Registry:
    """In-memory registry of currently-connected apps. Dual-indexed by
    license_key and install_uuid (either may be empty; never both).

    Stateless across restarts — every connected client/app has to re-handshake
    after a relay restart. That's the trade-off we accepted for single-VPS
    simplicity; multi-instance would need Redis pub/sub here.
    """

    def __init__(self) -> None:
        self._by_license: dict[str, AppConn] = {}
        self._by_install_uuid: dict[str, AppConn] = {}
        self._lock = asyncio.Lock()

    async def register_app(self, conn: AppConn) -> AppConn:
        """Register a new app connection. Evicts any prior conn matching
        EITHER the license_key OR the install_uuid (we want both indices
        to point at the live socket; can't have stragglers in either)."""
        async with self._lock:
            to_evict: list[AppConn] = []
            if conn.license_key:
                prior = self._by_license.get(conn.license_key)
                if prior is not None and prior not in to_evict:
                    to_evict.append(prior)
            if conn.install_uuid:
                prior = self._by_install_uuid.get(conn.install_uuid)
                if prior is not None and prior not in to_evict:
                    to_evict.append(prior)

            for stale in to_evict:
                # Close best-effort; don't await — we don't want a hung old
                # socket to block the new one.
                try:
                    asyncio.create_task(stale.ws.close(code=1000))
                except Exception:
                    pass
                self._fail_pending(stale, "App reconnected; request dropped.")
                # Drop from both indices to avoid dangling refs.
                if stale.license_key:
                    self._by_license.pop(stale.license_key, None)
                if stale.install_uuid:
                    self._by_install_uuid.pop(stale.install_uuid, None)

            if conn.license_key:
                self._by_license[conn.license_key] = conn
            if conn.install_uuid:
                self._by_install_uuid[conn.install_uuid] = conn
            return conn

    async def unregister_app(self, conn: AppConn) -> None:
        async with self._lock:
            if conn.license_key and self._by_license.get(conn.license_key) is conn:
                del self._by_license[conn.license_key]
            if conn.install_uuid and self._by_install_uuid.get(conn.install_uuid) is conn:
                del self._by_install_uuid[conn.install_uuid]
        self._fail_pending(conn, "App disconnected.")

    def get_app_by_license(self, license_key: str) -> Optional[AppConn]:
        if not license_key:
            return None
        return self._by_license.get(license_key)

    def get_app_by_install_uuid(self, install_uuid: str) -> Optional[AppConn]:
        if not install_uuid:
            return None
        return self._by_install_uuid.get(install_uuid)

    # Backward-compat alias for v1.0 callers that used get_app(license_key).
    def get_app(self, license_key: str) -> Optional[AppConn]:
        return self.get_app_by_license(license_key)

    def all_apps(self) -> list[AppConn]:
        # Dedup across both indices (an AppConn keyed by both license and
        # install_uuid appears once in each dict — same object).
        seen: set[int] = set()
        out: list[AppConn] = []
        for conn in list(self._by_license.values()) + list(self._by_install_uuid.values()):
            if id(conn) in seen:
                continue
            seen.add(id(conn))
            out.append(conn)
        return out

    @staticmethod
    def _fail_pending(conn: AppConn, reason: str) -> None:
        for fut in list(conn.pending.values()):
            if not fut.done():
                fut.set_exception(RuntimeError(reason))
        conn.pending.clear()
