import os
import secrets


HOST = os.environ.get("RELAY_HOST", "0.0.0.0")
PORT = int(os.environ.get("RELAY_PORT", "8787"))

# Self-hosted license server. JSON response shape matches the legacy
# Lemon Squeezy `/v1/licenses/*` endpoints — that's intentional, the
# desktop app was written against that shape before we self-hosted, so
# the only difference is the base URL and the path prefix.
LICENSE_API_BASE = os.environ.get(
    "RELAY_LICENSE_API_BASE", "https://bitaxeballer.com/api/license"
)
LICENSE_VALIDATE_TIMEOUT_S = float(os.environ.get("RELAY_LICENSE_TIMEOUT_S", "8.0"))

SESSION_TTL_S = int(os.environ.get("RELAY_SESSION_TTL_S", str(24 * 3600)))
IDLE_DISCONNECT_S = int(os.environ.get("RELAY_IDLE_DISCONNECT_S", str(3600)))
LICENSE_REVALIDATE_S = int(os.environ.get("RELAY_LICENSE_REVALIDATE_S", str(3600)))

REQUEST_TIMEOUT_S = float(os.environ.get("RELAY_REQUEST_TIMEOUT_S", "15.0"))

DEV_LICENSE_KEY = os.environ.get("RELAY_DEV_LICENSE_KEY", "").strip()

# Signing secret for session tokens. Must be stable across restarts in
# production; ephemeral here is intentional for dev (every restart logs
# everyone out, which is a feature not a bug).
SECRET = os.environ.get("RELAY_SECRET", "").strip() or secrets.token_hex(32)

# iOS v1.1 pairing feature flag. When unset, /ws/app rejects connections
# missing a license key (existing Pro-only behavior) and /ws/client only
# accepts session tokens from /login (existing flow). When set to "1",
# also accepts install_uuid-only connections (free-tier desktops) and
# device_token Bearer auth on /ws/client (paired iOS devices), with
# tier-limit response interception (free desktops stream max 1 device).
PAIRING_ENABLED = os.environ.get("RELAY_PAIRING_ENABLED", "").strip() == "1"

# Site server base URL — relay calls /api/relay/device-info on paired
# iOS connects to resolve which install_uuid + tier the device_token
# belongs to. Same host as LICENSE_API_BASE for now (single VPS deploy).
SITE_API_BASE = os.environ.get(
    "RELAY_SITE_API_BASE", "https://bitaxeballer.com"
)
DEVICE_INFO_TIMEOUT_S = float(os.environ.get("RELAY_DEVICE_INFO_TIMEOUT_S", "5.0"))
DEVICE_INFO_CACHE_S = int(os.environ.get("RELAY_DEVICE_INFO_CACHE_S", "60"))
