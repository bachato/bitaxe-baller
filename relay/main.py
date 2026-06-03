"""Bitaxe Baller remote-access relay.

Run with::

    uvicorn main:app --host 0.0.0.0 --port 8787

See README.md for env vars and architecture notes.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import Optional

from pathlib import Path

from fastapi import (
    FastAPI,
    Form,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

import config
import device_lookup
import licensing
import protocol
import tokens
from registry import AppConn, Registry


log = logging.getLogger("relay")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


registry = Registry()
_idle_task: Optional[asyncio.Task] = None


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    global _idle_task
    _idle_task = asyncio.create_task(_idle_disconnect_loop())
    log.info("relay started host=%s port=%s", config.HOST, config.PORT)
    try:
        yield
    finally:
        if _idle_task:
            _idle_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await _idle_task


app = FastAPI(title="bitaxe-baller-relay", lifespan=lifespan)

# CORS: the mobile Capacitor wrapper runs from https://localhost (Android) or
# capacitor://localhost (iOS) and needs to fetch /login from this origin.
# WebSockets aren't CORS-checked, so it's the HTTP routes that need this.
# We're permissive (allow_origins=["*"]) because:
#   - the license key in POST /login is body-auth, not a cookie,
#   - allow_credentials=False so no cookies/auth headers cross-origin,
#   - the only HTTP routes here are /, /health, /login — none mutate state
#     based on the requester's origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)


_WEB_DIR = Path(__file__).parent / "web"


@app.get("/")
def index():
    """Single-page client. Login form + minimal dashboard. The browser then
    talks to the relay via WS on the same origin, so no CORS dance."""
    return FileResponse(_WEB_DIR / "index.html")


@app.get("/health")
def health():
    return {
        "ok": True,
        "connected_apps": len(registry.all_apps()),
        "version": "0.1.0",
    }


@app.post("/login")
def login(license_key: str = Form(...), activation_id: Optional[str] = Form(None)):
    """Exchange a license key (+ optional activation_id) for a session token.

    Form-encoded to match the LS conventions the app already uses.
    """
    try:
        info = licensing.validate(license_key, activation_id)
    except licensing.LicenseError as e:
        # 401 is correct here — caller authentication failed.
        return JSONResponse(status_code=401, content={"ok": False, "error": str(e)})

    token = tokens.mint(info.key)
    return {
        "ok": True,
        "token": token,
        "expires_in": config.SESSION_TTL_S,
        "email": info.email,
    }


def _extract_bearer(request_headers: dict, query_param: Optional[str]) -> Optional[str]:
    """Pull a credential from `Authorization: Bearer <x>` header, or fall
    back to a query parameter. Returns None if neither is present."""
    auth = request_headers.get("authorization") or request_headers.get("Authorization")
    if auth:
        parts = auth.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    return (query_param or "").strip() or None


@app.websocket("/ws/app")
async def ws_app(
    ws: WebSocket,
    key: Optional[str] = None,
    activation_id: Optional[str] = None,
    install_uuid: Optional[str] = None,
):
    """App-side socket.

    Auth paths:
      - Pro (existing): license key via Authorization Bearer or `?key=`.
        Validates against LS once at connect time. install_uuid optional;
        when present, the connection is dual-indexed so paired iOS devices
        can find it.
      - Free (new, requires config.PAIRING_ENABLED): `?install_uuid=...`
        only. No license validation. Tier='free'. Paired iOS devices find
        the connection by install_uuid; response stripping limits them to
        1 device's data.
    """
    headers = {k.decode().lower(): v.decode() for k, v in ws.scope.get("headers", [])}
    license_key = _extract_bearer(headers, key)
    install_uuid = (install_uuid or "").strip()

    # No credentials at all → reject.
    if not license_key and not install_uuid:
        await ws.close(code=4401)
        return

    # Free-tier path: install_uuid without a license. Gated on the feature
    # flag so existing Pro-only relay behavior is preserved until rollout.
    if not license_key:
        if not config.PAIRING_ENABLED:
            await ws.accept()
            await ws.close(code=4401, reason="Pairing not enabled.")
            return
        if not _is_valid_install_uuid(install_uuid):
            await ws.accept()
            await ws.close(code=4401, reason="install_uuid format invalid.")
            return
        await ws.accept()
        conn = AppConn(license_key="", ws=ws, tier="free", install_uuid=install_uuid)
        await registry.register_app(conn)
        log.info("app connected (free) install_uuid=%s", _redact(install_uuid))
        try:
            await _app_read_loop(conn)
        except WebSocketDisconnect:
            pass
        except Exception:
            log.exception("app loop error install_uuid=%s", _redact(install_uuid))
        finally:
            await registry.unregister_app(conn)
            log.info("app disconnected (free) install_uuid=%s", _redact(install_uuid))
        return

    # Pro path: validate license.
    try:
        info = licensing.validate(license_key, activation_id)
    except licensing.LicenseError as e:
        log.info("app reject license=%s reason=%s", _redact(license_key), e)
        await ws.accept()
        await ws.close(code=4401, reason=str(e)[:120])
        return

    await ws.accept()
    conn = AppConn(
        license_key=info.key,
        ws=ws,
        tier="pro",
        install_uuid=install_uuid if _is_valid_install_uuid(install_uuid) else "",
    )
    await registry.register_app(conn)
    log.info(
        "app connected license=%s email=%s install_uuid=%s",
        _redact(info.key), info.email, _redact(conn.install_uuid) or "-",
    )

    try:
        await _app_read_loop(conn)
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("app loop error license=%s", _redact(info.key))
    finally:
        await registry.unregister_app(conn)
        log.info("app disconnected license=%s", _redact(info.key))


def _is_valid_install_uuid(s: str) -> bool:
    """Lightweight format check — same shape the leaderboard endpoint
    accepts: hex with dashes, 20+ chars (full UUIDs are 32 hex + 4 dashes = 36)."""
    import re
    return bool(re.fullmatch(r"[0-9a-fA-F-]{20,}", s or ""))


async def _app_read_loop(conn: AppConn) -> None:
    while True:
        raw = await conn.ws.receive_text()
        if len(raw) > protocol.MAX_BODY_BYTES:
            log.warning("app message too big license=%s bytes=%d", _redact(conn.license_key), len(raw))
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(msg, dict):
            continue

        mtype = msg.get("type")
        if mtype == "response":
            req_id = msg.get("id")
            fut = conn.pending.pop(req_id, None) if req_id else None
            if fut is not None and not fut.done():
                fut.set_result(msg)
        elif mtype == "hello":
            log.info(
                "app hello license=%s version=%s",
                _redact(conn.license_key),
                msg.get("version"),
            )
        elif mtype == "ping":
            await _send_json(conn, {"type": "pong"})
        # silently ignore other types — forward-compat


@app.websocket("/ws/client")
async def ws_client(ws: WebSocket, token: Optional[str] = None):
    """Client-side socket (browser, mobile).

    Auth paths:
      - Session token (existing): minted by /login, signed JWT-shaped
        `<payload>.<sig>`. Verifies against tokens.verify() → license_key
        → routes to AppConn keyed by license.
      - Device token (new, iOS pairing): opaque base64url string from
        /api/relay/pair-redeem. No dots. Validated by calling the site
        server's /api/relay/device-info → install_uuid + tier_at_pair →
        routes to AppConn keyed by install_uuid. Tier-limit (1 device
        max for free) applied to response bodies before forwarding.
    """
    headers = {k.decode().lower(): v.decode() for k, v in ws.scope.get("headers", [])}
    bearer = _extract_bearer(headers, token)
    if not bearer:
        await ws.close(code=4401)
        return

    # Shape disambiguation: session tokens have a dot separating payload
    # and signature; device tokens are 32-char base64url with no dots.
    is_session_token = "." in bearer

    route_license_key: Optional[str] = None
    route_install_uuid: Optional[str] = None
    route_tier: str = "pro"
    log_label: str = ""

    if is_session_token:
        try:
            route_license_key = tokens.verify(bearer)
        except tokens.TokenError as e:
            await ws.accept()
            await ws.close(code=4401, reason=str(e)[:120])
            return
        log_label = f"license={_redact(route_license_key)}"
    else:
        if not config.PAIRING_ENABLED:
            await ws.accept()
            await ws.close(code=4401, reason="Pairing not enabled.")
            return
        try:
            info = device_lookup.lookup(bearer)
        except device_lookup.DeviceLookupError as e:
            await ws.accept()
            await ws.close(code=4401, reason=str(e)[:120])
            return
        route_install_uuid = info.install_uuid_paired
        route_tier = info.tier_at_pair
        log_label = f"device=ios install_uuid={_redact(route_install_uuid)} tier={route_tier}"

    await ws.accept()
    log.info("client connected %s", log_label)

    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > protocol.MAX_BODY_BYTES:
                await ws.send_text(json.dumps(
                    protocol.make_error_response("", 413, "Request too large.")
                ))
                continue
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            await _handle_client_request(
                ws,
                license_key=route_license_key,
                install_uuid=route_install_uuid,
                client_tier=route_tier,
                msg=msg,
            )
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("client loop error %s", log_label)
    finally:
        log.info("client disconnected %s", log_label)


async def _handle_client_request(
    client_ws: WebSocket,
    license_key: Optional[str],
    install_uuid: Optional[str],
    client_tier: str,
    msg: dict,
) -> None:
    if isinstance(msg, dict) and msg.get("type") == "ping":
        await client_ws.send_text(json.dumps({"type": "pong"}))
        return

    # Capture the client-allocated id (if any) so responses can be matched
    # back. The relay still mints its own id for the app conversation,
    # since clients sharing a license key could otherwise collide.
    client_id = msg.get("id") if isinstance(msg, dict) else None

    try:
        method, path, body = protocol.validate_client_request(msg)
    except ValueError as e:
        await client_ws.send_text(json.dumps(
            protocol.make_error_response(client_id or "", 400, str(e))
        ))
        return

    # Free-tier paired iOS clients are read-only — reject mutations.
    if client_tier == "free" and method != "GET":
        await client_ws.send_text(json.dumps(
            protocol.make_error_response(client_id or "", 403, "Free tier is read-only on the paired companion app.")
        ))
        return

    # Route lookup: session-token clients use license_key; paired iOS
    # clients use install_uuid. The desktop AppConn is dual-indexed.
    conn: Optional[AppConn] = None
    if license_key:
        conn = registry.get_app_by_license(license_key)
    elif install_uuid:
        conn = registry.get_app_by_install_uuid(install_uuid)

    if conn is None:
        await client_ws.send_text(json.dumps(
            protocol.make_error_response(client_id or "", 502, "App is not connected to the relay.")
        ))
        return

    # Effective tier for stripping = max(client_tier, conn.tier). If a Pro
    # desktop paired an iPhone but the device_token was issued back when
    # the desktop was free (tier_at_pair='free'), we still respect the
    # snapshot. Worst case: user re-pairs to refresh tier.
    effective_tier = "free" if (client_tier == "free" or conn.tier == "free") else "pro"

    req_id = protocol.new_request_id()
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    conn.pending[req_id] = fut
    conn.touch()

    try:
        await _send_json(conn, protocol.make_request(req_id, method, path, body))
    except Exception as e:
        conn.pending.pop(req_id, None)
        await client_ws.send_text(json.dumps(
            protocol.make_error_response(client_id or "", 502, f"Failed to reach app: {e.__class__.__name__}")
        ))
        return

    try:
        response_msg = await asyncio.wait_for(fut, timeout=config.REQUEST_TIMEOUT_S)
    except asyncio.TimeoutError:
        conn.pending.pop(req_id, None)
        await client_ws.send_text(json.dumps(
            protocol.make_error_response(client_id or "", 504, "App did not respond in time.")
        ))
        return
    except Exception as e:
        await client_ws.send_text(json.dumps(
            protocol.make_error_response(client_id or "", 502, str(e))
        ))
        return

    # Stamp the client's original id on the way out so they can match
    # this response to their request. If they didn't supply one we emit
    # empty rather than the relay's internal id — never leak that.
    out = dict(response_msg)
    out["type"] = "response"
    out["id"] = client_id or ""

    # Free-tier paired iOS clients: strip device-list responses to a
    # single device. Pro paths skip this entirely. The desktop app's
    # /api/devices returns {"devices": [...], ...} — we keep [0] only.
    if effective_tier == "free":
        out = _apply_free_tier_response_filter(method, path, out)

    await client_ws.send_text(json.dumps(out))


def _apply_free_tier_response_filter(method: str, path: str, response_msg: dict) -> dict:
    """Trim response bodies so free-tier paired clients see at most one
    device's data. Defensive: keeps the response shape intact if anything
    unexpected appears, so a future schema change doesn't break free users.

    /api/devices on the desktop returns a JSON LIST of device summaries
    (not a wrapper dict). The earlier version of this code assumed a dict
    shape and would AttributeError on every free-tier iOS request. Now
    handles both: list-of-summaries (current shape) AND dict with
    "devices" key (defensive for any future wrapper).
    """
    if method != "GET" or path != "/api/devices":
        return response_msg

    body = response_msg.get("body")

    # Current shape: bare list of device summaries.
    if isinstance(body, list):
        if len(body) > 1:
            response_msg = dict(response_msg)
            response_msg["body"] = body[:1]
        return response_msg

    # Defensive: wrapper dict shape, in case the desktop ever changes to
    # {"devices": [...], ...}. Trim the devices key only; leave any other
    # summary fields intact.
    if isinstance(body, dict):
        devices = body.get("devices")
        if isinstance(devices, list) and len(devices) > 1:
            new_body = dict(body)
            new_body["devices"] = devices[:1]
            response_msg = dict(response_msg)
            response_msg["body"] = new_body

    # /api/device/<ip> isn't filtered — a free-tier client only ever knows
    # about device[0]'s IP from /api/devices, so they can't request the
    # others by accident. If they do construct a request out-of-band, we
    # let it through; the relay doesn't pre-resolve which IP is "first".
    return response_msg


async def _send_json(conn: AppConn, payload: dict) -> None:
    data = json.dumps(payload)
    async with conn.write_lock:
        await conn.ws.send_text(data)


async def _idle_disconnect_loop() -> None:
    """Closes app sockets that haven't seen client traffic in IDLE_DISCONNECT_S.
    Keeps long-idle tabs from chewing bandwidth.
    """
    interval = max(30, config.IDLE_DISCONNECT_S // 10)
    while True:
        await asyncio.sleep(interval)
        for conn in registry.all_apps():
            if conn.idle_seconds() > config.IDLE_DISCONNECT_S:
                log.info(
                    "app idle disconnect id=%s idle_s=%d",
                    _redact(conn.license_key) or _redact(conn.install_uuid) or "?",
                    int(conn.idle_seconds()),
                )
                with contextlib.suppress(Exception):
                    await conn.ws.close(code=1000, reason="idle")


def _redact(license_key: str) -> str:
    if not license_key:
        return ""
    if len(license_key) <= 8:
        return "***"
    return f"{license_key[:4]}…{license_key[-4:]}"
