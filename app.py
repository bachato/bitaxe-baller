"""
Bitaxe Baller
Run: python app.py
Then open http://localhost:5050 in your browser. Add devices and tune from there.
"""

import json
import socket
import time
import threading
import os
from collections import deque
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

DEFAULT_POLL = 5
HISTORY_POINTS = 720  # 1 hour at 5s
ROLLING_WINDOWS = {"1m": 12, "5m": 60, "15m": 180, "1h": 720}

# Tuning presets for Gamma (BM1370)
PRESETS = {
    "stock":      {"frequency": 525, "coreVoltage": 1150, "label": "Stock"},
    "mild":       {"frequency": 550, "coreVoltage": 1170, "label": "Mild OC"},
    "balanced":   {"frequency": 575, "coreVoltage": 1185, "label": "Balanced"},
    "aggressive": {"frequency": 600, "coreVoltage": 1200, "label": "Aggressive"},
    "max":        {"frequency": 625, "coreVoltage": 1225, "label": "Max (risky)"},
}

# Sane bounds — refuse to send anything outside these
BOUNDS = {
    "frequency": (400, 700),     # MHz
    "coreVoltage": (1000, 1300), # mV
    "fanspeed": (0, 100),        # %
}

state_lock = threading.Lock()
state = {}                # ip -> device state
config_lock = threading.Lock()
poll_thread = None
poll_stop_flag = threading.Event()


def default_config():
    return {"devices": [], "poll_interval": DEFAULT_POLL}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(default_config())
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def init_device_state(ip, label):
    return {
        "ip": ip,
        "label": label,
        "history": deque(maxlen=HISTORY_POINTS),
        "latest": None,
        "online": False,
        "consecutive_errors": 0,
        "last_error": "",
        "session_start": time.time(),
        "session_shares_start": None,
        "session_hwerrors_start": None,
        "events": deque(maxlen=50),  # tuning changes, restarts, etc
    }


def fetch_device(ip, timeout=3):
    r = requests.get(f"http://{ip}/api/system/info", timeout=timeout)
    r.raise_for_status()
    return r.json()


def patch_device(ip, settings, timeout=5):
    r = requests.patch(
        f"http://{ip}/api/system",
        json=settings,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    r.raise_for_status()
    return True


def restart_device(ip, timeout=5):
    r = requests.post(f"http://{ip}/api/system/restart", timeout=timeout)
    r.raise_for_status()
    return True


def log_event(ip, msg):
    with state_lock:
        if ip in state:
            state[ip]["events"].appendleft({
                "t": time.time(),
                "msg": msg,
            })


def poll_one(ip, label):
    ts = time.time()
    try:
        data = fetch_device(ip)
        with state_lock:
            if ip not in state:
                return
            s = state[ip]
            was_offline = not s["online"]
            s["online"] = True
            s["consecutive_errors"] = 0
            s["last_error"] = ""
            s["latest"] = data

            if s["session_shares_start"] is None:
                s["session_shares_start"] = data.get("sharesAccepted", 0)
                s["session_hwerrors_start"] = data.get("sharesRejected", 0)

            point = {
                "t": ts,
                "hashRate": data.get("hashRate", 0),
                "temp": data.get("temp", 0),
                "vrTemp": data.get("vrTemp", 0),
                "power": data.get("power", 0),
                "voltage": data.get("voltage", 0),
                "coreVoltage": data.get("coreVoltage", 0),
                "frequency": data.get("frequency", 0),
                "sharesAccepted": data.get("sharesAccepted", 0),
                "sharesRejected": data.get("sharesRejected", 0),
                "bestDiff": data.get("bestDiff", "0"),
                "bestSessionDiff": data.get("bestSessionDiff", "0"),
                "uptime": data.get("uptimeSeconds", 0),
            }
            s["history"].append(point)

        if was_offline:
            log_event(ip, "Device back online")
        append_csv(label, point)
    except Exception as e:
        with state_lock:
            if ip not in state:
                return
            s = state[ip]
            was_online = s["online"]
            s["consecutive_errors"] += 1
            s["last_error"] = str(e)[:100]
            if s["consecutive_errors"] >= 3:
                s["online"] = False
        if was_online and state.get(ip, {}).get("consecutive_errors", 0) == 3:
            log_event(ip, f"Device went offline: {str(e)[:60]}")


def poll_loop():
    while not poll_stop_flag.is_set():
        with config_lock:
            cfg = load_config()
            interval = cfg.get("poll_interval", DEFAULT_POLL)
            devices = list(cfg.get("devices", []))

        if devices:
            t0 = time.time()
            with ThreadPoolExecutor(max_workers=max(4, len(devices))) as ex:
                futures = [ex.submit(poll_one, d["ip"], d["label"]) for d in devices]
                for f in futures:
                    try:
                        f.result(timeout=10)
                    except Exception:
                        pass
            elapsed = time.time() - t0
            time.sleep(max(0.5, interval - elapsed))
        else:
            time.sleep(2)


def append_csv(label, point):
    safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(LOG_DIR, f"{safe_label}_{date_str}.csv")
    new_file = not os.path.exists(path)
    with open(path, "a") as f:
        if new_file:
            f.write("timestamp,iso_time,hashrate_ghs,asic_temp_c,vr_temp_c,power_w,"
                    "voltage_mv,core_voltage_mv,frequency_mhz,"
                    "shares_accepted,shares_rejected,uptime_s\n")
        iso = datetime.fromtimestamp(point["t"]).isoformat()
        f.write(f"{point['t']:.0f},{iso},{point['hashRate']:.2f},{point['temp']:.1f},"
                f"{point['vrTemp']:.1f},{point['power']:.2f},{point['voltage']:.0f},"
                f"{point['coreVoltage']:.0f},{point['frequency']:.0f},"
                f"{point['sharesAccepted']},{point['sharesRejected']},"
                f"{point['uptime']}\n")


def rolling_avg(history, window_size, key="hashRate"):
    if not history:
        return 0
    pts = list(history)[-window_size:]
    if not pts:
        return 0
    return sum(p[key] for p in pts) / len(pts)


def _clamp(val, key):
    lo, hi = BOUNDS[key]
    return max(lo, min(hi, val))


_SEVERITY_RANK = {"crit": 4, "warn": 3, "good": 2, "info": 1}


def _max_severity(recs):
    """Highest-severity rec (excluding the 'warming up' info rec). Drives the
    health border on the home page card. Returns None if nothing actionable."""
    actionable = [r for r in recs if r.get("id") != "warming_up"]
    if not actionable:
        return None
    return max(actionable, key=lambda r: _SEVERITY_RANK.get(r.get("severity"), 0))["severity"]


def compute_recommendations(s, hist, avgs, hw_rate_pct, shares_delta, j_per_th, ghs, expected_ghs):
    """Rule-based suggestions tied to current telemetry. Returns up to 3 recs,
    most-severe first. Each rec has an optional `action` the UI can fire one-click."""
    if not s["latest"]:
        return []

    age_s = time.time() - s["session_start"]
    samples = len(hist)
    latest = s["latest"]
    freq = latest.get("frequency", 525)
    volt = latest.get("coreVoltage", 1150)
    asic = latest.get("temp", 0)
    vr = latest.get("vrTemp", 0)
    autofan = latest.get("autofanspeed", 0)

    recs = []

    # Need a few minutes of data before tuning suggestions are meaningful.
    if age_s < 180 or samples < 30:
        recs.append({
            "id": "warming_up",
            "severity": "info",
            "title": "Gathering baseline data",
            "body": f"Wait {max(0, int(180 - age_s))}s — recommendations stabilize after ~3 min of polling.",
        })
        return recs

    # 1. CRIT: VR temp in danger zone
    if vr >= 65:
        new_v = _clamp(volt - 15, "coreVoltage")
        recs.append({
            "id": "vr_critical",
            "severity": "crit",
            "title": f"VR temp {vr:.0f}°C — danger zone",
            "body": f"VR is the part that kills boards. Drop core voltage to {new_v} mV and check airflow.",
            "action": {"type": "tune", "params": {"coreVoltage": new_v}, "label": f"set {new_v}mV"},
        })

    # 2. CRIT: HW error rate too high
    if shares_delta >= 20 and hw_rate_pct >= 1.0:
        new_v = _clamp(volt - 10, "coreVoltage")
        recs.append({
            "id": "hw_high",
            "severity": "crit",
            "title": f"HW error rate {hw_rate_pct:.2f}% — chip unstable",
            "body": f"Errors above 1% mean the chip is fighting the settings. Drop core voltage to {new_v} mV.",
            "action": {"type": "tune", "params": {"coreVoltage": new_v}, "label": f"set {new_v}mV"},
        })

    # 3. WARN: HW errors climbing (0.5 - 1%)
    elif shares_delta >= 20 and hw_rate_pct >= 0.5:
        new_v = _clamp(volt + 10, "coreVoltage")
        recs.append({
            "id": "hw_climbing",
            "severity": "warn",
            "title": f"HW errors at {hw_rate_pct:.2f}% — getting unstable",
            "body": f"You can either give it more voltage ({new_v} mV) for stability, or drop frequency to back off.",
            "action": {"type": "tune", "params": {"coreVoltage": new_v}, "label": f"add 10mV"},
        })

    # 4. WARN: ASIC running hot (and VR isn't already crit)
    if asic >= 65 and vr < 65:
        if autofan:
            recs.append({
                "id": "asic_hot",
                "severity": "warn",
                "title": f"ASIC at {asic:.0f}°C — hot",
                "body": "Auto-fan is on but the chip is still climbing. Consider dropping voltage 5–10 mV or improving case airflow.",
            })
        else:
            recs.append({
                "id": "asic_hot_manual",
                "severity": "warn",
                "title": f"ASIC at {asic:.0f}°C — hot",
                "body": "Switch fan to auto, or bump fan speed up.",
                "action": {"type": "tune", "params": {"autofanspeed": 1}, "label": "enable auto-fan"},
            })

    # 5. WARN: 5m hashrate noticeably below 15m — recent destabilization
    h5 = avgs.get("5m", 0)
    h15 = avgs.get("15m", 0)
    if h15 > 0 and h5 > 0 and (h5 / h15) < 0.92:
        recs.append({
            "id": "hash_dropping",
            "severity": "warn",
            "title": f"5m avg ({h5:.0f}) trailing 15m avg ({h15:.0f})",
            "body": "Hashrate destabilized recently. Reset the benchmark to re-baseline cleanly, or back off frequency 25 MHz.",
            "action": {"type": "reset_session", "label": "reset benchmark"},
        })

    # 6. GOOD: stable + low errors + has headroom → suggest pushing frequency
    has_headroom_freq = freq + 25 <= BOUNDS["frequency"][1]
    stable_long = age_s >= 900 and samples >= 150  # 15+ minutes of data
    if (stable_long and hw_rate_pct < 0.1 and vr < 60 and asic < 60
            and has_headroom_freq):
        new_f = _clamp(freq + 25, "frequency")
        recs.append({
            "id": "push_freq",
            "severity": "good",
            "title": "Stable for 15m+ with headroom",
            "body": f"Errors <0.1%, temps healthy. Try {new_f} MHz to push for more hashrate.",
            "action": {"type": "tune", "params": {"frequency": new_f}, "label": f"try {new_f}MHz"},
        })

    # 7. INFO: underperforming vs expected (only flag after 5 min of data)
    if (age_s >= 300 and expected_ghs > 0 and ghs > 0
            and (ghs / expected_ghs) < 0.85):
        pct = (ghs / expected_ghs) * 100
        recs.append({
            "id": "below_expected",
            "severity": "info",
            "title": f"Hashrate at {pct:.0f}% of expected",
            "body": "Could be silicon lottery, or chip is throttling on errors. Check HW error rate; if 0, this is just chip variance.",
        })

    # 8. GOOD: excellent efficiency, hold the line
    if (stable_long and j_per_th and j_per_th <= 16 and hw_rate_pct < 0.1
            and asic < 60 and vr < 60):
        recs.append({
            "id": "great_eff",
            "severity": "good",
            "title": f"Excellent efficiency — {j_per_th:.2f} J/TH",
            "body": "This is a solid operating point. Pushing harder may improve hashrate but cost efficiency.",
        })

    # Severity priority for trimming: crit > warn > good > info
    order = {"crit": 0, "warn": 1, "good": 2, "info": 3}
    recs.sort(key=lambda r: order.get(r["severity"], 9))
    return recs[:3]


def device_summary(s):
    if not s["latest"]:
        return {
            "ip": s["ip"],
            "label": s["label"],
            "online": s["online"],
            "lastError": s["last_error"],
            "history": [],
            "events": list(s["events"]),
            "recommendations": [],
            "severity": "crit" if not s["online"] else None,
        }

    latest = s["latest"]
    hist = list(s["history"])
    avgs = {name: rolling_avg(s["history"], n) for name, n in ROLLING_WINDOWS.items()}

    hw_delta = 0
    shares_delta = 0
    if s["session_shares_start"] is not None and hist:
        latest_pt = hist[-1]
        shares_delta = latest_pt["sharesAccepted"] - s["session_shares_start"]
        hw_delta = latest_pt["sharesRejected"] - (s["session_hwerrors_start"] or 0)

    hw_rate_pct = 0
    if shares_delta + hw_delta > 0:
        hw_rate_pct = (hw_delta / (shares_delta + hw_delta)) * 100

    ghs = latest.get("hashRate", 0)
    power = latest.get("power", 0)
    j_per_th = (power / (ghs / 1000)) if ghs > 0 else 0

    freq = latest.get("frequency", 0)
    expected_ghs = freq * 2.28 if freq > 0 else 0

    session_secs = max(1, time.time() - s["session_start"])
    shares_per_min = (shares_delta / (session_secs / 60)) if session_secs >= 60 else 0

    recs = compute_recommendations(s, hist, avgs, hw_rate_pct, shares_delta, j_per_th, ghs, expected_ghs)

    return {
        "ip": s["ip"],
        "label": s["label"],
        "online": s["online"],
        "lastError": s["last_error"],
        "model": latest.get("ASICModel", "unknown"),
        "version": latest.get("version", ""),
        "hostname": latest.get("hostname", ""),
        "metrics": {
            "hashRate": round(ghs, 1),
            "temp": round(latest.get("temp", 0), 1),
            "vrTemp": round(latest.get("vrTemp", 0), 1),
            "power": round(power, 2),
            "voltage": latest.get("voltage", 0),
            "coreVoltage": latest.get("coreVoltage", 0),
            "frequency": latest.get("frequency", 0),
            "fanSpeed": int(latest.get("fanrpm", 0) or 0),
            "fanPercent": round(latest.get("fanspeed", 0) or 0),
            "autofanspeed": int(latest.get("autofanspeed", 0) or 0),
            "sharesAccepted": latest.get("sharesAccepted", 0),
            "sharesRejected": latest.get("sharesRejected", 0),
            "bestDiff": latest.get("bestDiff", "0"),
            "bestSessionDiff": latest.get("bestSessionDiff", "0"),
            "poolDifficulty": latest.get("poolDifficulty", 0),
            "uptime": latest.get("uptimeSeconds", 0),
            "stratumUrl": latest.get("stratumURL", ""),
        },
        "shares": {
            "sessionAccepted": max(0, shares_delta),
            "sessionRejected": max(0, hw_delta),
            "lifetimeAccepted": latest.get("sharesAccepted", 0),
            "lifetimeRejected": latest.get("sharesRejected", 0),
            "perMin": round(shares_per_min, 2),
            "sessionSecs": int(session_secs),
        },
        "rolling": {k: round(v, 1) for k, v in avgs.items()},
        "efficiency": {
            "jPerTh": round(j_per_th, 2),
            "expectedGhs": round(expected_ghs, 1),
            "actualPctOfExpected": round((ghs / expected_ghs * 100) if expected_ghs > 0 else 0, 1),
        },
        "hwErrors": {
            "shares": shares_delta,
            "hwErrors": hw_delta,
            "ratePct": round(hw_rate_pct, 3),
        },
        "stratum": {
            "url": latest.get("stratumURL", ""),
            "port": latest.get("stratumPort", 0),
            "user": latest.get("stratumUser", ""),
            "tls": int(latest.get("stratumTLS", 0) or 0),
            "suggestedDifficulty": latest.get("stratumSuggestedDifficulty", 0),
            "fallbackUrl": latest.get("fallbackStratumURL", ""),
            "fallbackPort": latest.get("fallbackStratumPort", 0),
            "fallbackUser": latest.get("fallbackStratumUser", ""),
            "fallbackTls": int(latest.get("fallbackStratumTLS", 0) or 0),
            "fallbackSuggestedDifficulty": latest.get("fallbackStratumSuggestedDifficulty", 0),
            "usingFallback": int(latest.get("isUsingFallbackStratum", 0) or 0),
            "connectionInfo": latest.get("poolConnectionInfo", ""),
        },
        "recommendations": recs,
        "severity": _max_severity(recs),
        "history": [
            {
                "t": p["t"],
                "h": round(p["hashRate"], 1),
                "asic": round(p["temp"], 1),
                "vr": round(p["vrTemp"], 1),
                "p": round(p["power"], 2),
            }
            for p in hist[-180:]
        ],
        "events": [{"t": e["t"], "msg": e["msg"]} for e in list(s["events"])[:10]],
    }


# ---------- Routes ----------

@app.route("/")
def index():
    return render_template("dashboard.html", presets=PRESETS, bounds=BOUNDS)


@app.route("/device/<ip>")
def device_detail(ip):
    """Per-device detail page — full metrics, tuning, pool config, event log."""
    with state_lock:
        if ip not in state:
            return ("Device not found. <a href='/'>Back to overview</a>", 404)
    return render_template("device.html", ip=ip, presets=PRESETS, bounds=BOUNDS)


@app.route("/api/devices")
def api_devices():
    with state_lock:
        return jsonify([device_summary(s) for s in state.values()])


@app.route("/api/device/<ip>")
def api_device_one(ip):
    with state_lock:
        if ip not in state:
            return jsonify({"error": "device not found"}), 404
        return jsonify(device_summary(state[ip]))


@app.route("/api/config", methods=["GET"])
def api_config_get():
    return jsonify(load_config())


@app.route("/api/devices/add", methods=["POST"])
def api_device_add():
    body = request.get_json(force=True)
    ip = (body.get("ip") or "").strip()
    label = (body.get("label") or "").strip()

    if not ip:
        return jsonify({"error": "IP required"}), 400
    if not label:
        label = ip.replace(".", "-")

    # Try to reach it
    try:
        info = fetch_device(ip, timeout=4)
    except Exception as e:
        return jsonify({"error": f"Could not reach {ip}: {str(e)[:120]}"}), 400

    with config_lock:
        cfg = load_config()
        if any(d["ip"] == ip for d in cfg["devices"]):
            return jsonify({"error": f"{ip} is already added"}), 400
        cfg["devices"].append({"ip": ip, "label": label})
        save_config(cfg)

    with state_lock:
        state[ip] = init_device_state(ip, label)

    log_event(ip, f"Device added (model: {info.get('ASICModel', '?')}, fw: {info.get('version', '?')})")
    return jsonify({"ok": True, "ip": ip, "label": label, "model": info.get("ASICModel")})


@app.route("/api/devices/remove", methods=["POST"])
def api_device_remove():
    body = request.get_json(force=True)
    ip = body.get("ip")
    if not ip:
        return jsonify({"error": "IP required"}), 400

    with config_lock:
        cfg = load_config()
        cfg["devices"] = [d for d in cfg["devices"] if d["ip"] != ip]
        save_config(cfg)

    with state_lock:
        state.pop(ip, None)

    return jsonify({"ok": True})


@app.route("/api/devices/rename", methods=["POST"])
def api_device_rename():
    body = request.get_json(force=True)
    ip = body.get("ip")
    label = (body.get("label") or "").strip()
    if not ip or not label:
        return jsonify({"error": "ip and label required"}), 400

    with config_lock:
        cfg = load_config()
        for d in cfg["devices"]:
            if d["ip"] == ip:
                d["label"] = label
        save_config(cfg)

    with state_lock:
        if ip in state:
            state[ip]["label"] = label

    return jsonify({"ok": True})


@app.route("/api/devices/tune", methods=["POST"])
def api_device_tune():
    """Apply settings (frequency, coreVoltage, fanspeed, autofanspeed) to a device."""
    body = request.get_json(force=True)
    ip = body.get("ip")
    if not ip:
        return jsonify({"error": "IP required"}), 400

    settings = {}
    for key in ("frequency", "coreVoltage", "fanspeed", "autofanspeed"):
        if key in body and body[key] is not None:
            try:
                val = int(body[key])
            except (TypeError, ValueError):
                return jsonify({"error": f"{key} must be a number"}), 400

            if key in BOUNDS:
                lo, hi = BOUNDS[key]
                if val < lo or val > hi:
                    return jsonify({"error": f"{key}={val} outside safe range {lo}-{hi}"}), 400
            settings[key] = val

    if not settings:
        return jsonify({"error": "No settings to apply"}), 400

    try:
        patch_device(ip, settings)
    except Exception as e:
        return jsonify({"error": f"Failed to apply: {str(e)[:120]}"}), 500

    parts = ", ".join(f"{k}={v}" for k, v in settings.items())
    log_event(ip, f"Tuning applied: {parts}")

    # Settings are usually applied without restart, but bump any ongoing baseline tracking
    with state_lock:
        if ip in state:
            # Reset hardware-error baseline so we measure errors at the new setting
            s = state[ip]
            if s["latest"]:
                s["session_shares_start"] = s["latest"].get("sharesAccepted", 0)
                s["session_hwerrors_start"] = s["latest"].get("sharesRejected", 0)
                s["session_start"] = time.time()

    return jsonify({"ok": True, "applied": settings})


@app.route("/api/devices/preset", methods=["POST"])
def api_device_preset():
    body = request.get_json(force=True)
    ip = body.get("ip")
    name = body.get("preset")
    if not ip or name not in PRESETS:
        return jsonify({"error": "Bad preset"}), 400
    p = PRESETS[name]
    settings = {"frequency": p["frequency"], "coreVoltage": p["coreVoltage"]}
    try:
        patch_device(ip, settings)
    except Exception as e:
        return jsonify({"error": f"Failed: {str(e)[:120]}"}), 500
    log_event(ip, f"Preset applied: {p['label']} ({p['frequency']} MHz / {p['coreVoltage']} mV)")
    with state_lock:
        if ip in state and state[ip]["latest"]:
            s = state[ip]
            s["session_shares_start"] = s["latest"].get("sharesAccepted", 0)
            s["session_hwerrors_start"] = s["latest"].get("sharesRejected", 0)
            s["session_start"] = time.time()
    return jsonify({"ok": True, "applied": settings, "preset": p["label"]})


@app.route("/api/devices/restart", methods=["POST"])
def api_device_restart():
    body = request.get_json(force=True)
    ip = body.get("ip")
    if not ip:
        return jsonify({"error": "IP required"}), 400
    try:
        restart_device(ip)
    except Exception as e:
        return jsonify({"error": str(e)[:120]}), 500
    log_event(ip, "Restart command sent")
    return jsonify({"ok": True})


POOL_FIELDS = {
    "stratumURL", "stratumPort", "stratumUser", "stratumPassword",
    "stratumTLS", "stratumSuggestedDifficulty",
    "fallbackStratumURL", "fallbackStratumPort", "fallbackStratumUser", "fallbackStratumPassword",
    "fallbackStratumTLS", "fallbackStratumSuggestedDifficulty",
}


@app.route("/api/devices/pool", methods=["POST"])
def api_device_pool():
    """Update primary and/or fallback stratum config on a device. The Bitaxe
    firmware applies pool changes on the next stratum reconnect, so a restart
    is usually needed. Caller is expected to follow up with /api/devices/restart
    if `restart` is truthy in the body."""
    body = request.get_json(force=True)
    ip = body.get("ip")
    if not ip:
        return jsonify({"error": "IP required"}), 400

    settings = {}
    for key in POOL_FIELDS:
        if key in body and body[key] not in (None, ""):
            v = body[key]
            if key.endswith("Port"):
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    return jsonify({"error": f"{key} must be an integer"}), 400
                if v <= 0 or v > 65535:
                    return jsonify({"error": f"{key} out of range"}), 400
            elif key.endswith("TLS") or key.endswith("SuggestedDifficulty"):
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    return jsonify({"error": f"{key} must be an integer"}), 400
            else:
                v = str(v).strip()
            settings[key] = v

    if not settings:
        return jsonify({"error": "No pool settings to apply"}), 400

    try:
        patch_device(ip, settings)
    except Exception as e:
        return jsonify({"error": f"Failed to apply: {str(e)[:120]}"}), 500

    safe_keys = sorted(k for k in settings if "Password" not in k)
    log_event(ip, f"Pool config updated: {', '.join(safe_keys)}")

    restarted = False
    if body.get("restart"):
        try:
            restart_device(ip)
            restarted = True
            log_event(ip, "Restart sent (pool config change)")
        except Exception as e:
            return jsonify({"ok": True, "applied": safe_keys, "restartError": str(e)[:120]}), 200

    return jsonify({"ok": True, "applied": safe_keys, "restarted": restarted})


@app.route("/api/devices/reset_session", methods=["POST"])
def api_reset_session():
    """Reset the rolling-average / HW-error baseline so a tuning experiment starts clean."""
    body = request.get_json(force=True)
    ip = body.get("ip")
    if not ip:
        return jsonify({"error": "IP required"}), 400
    with state_lock:
        if ip in state:
            s = state[ip]
            s["history"].clear()
            if s["latest"]:
                s["session_shares_start"] = s["latest"].get("sharesAccepted", 0)
                s["session_hwerrors_start"] = s["latest"].get("sharesRejected", 0)
            s["session_start"] = time.time()
    log_event(ip, "Benchmark session reset")
    return jsonify({"ok": True})


def detect_lan_ip():
    """Best-effort: find the LAN IP this machine uses to reach the local network.
    No packet is actually sent — the UDP socket only triggers a routing decision."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return None


HOST = os.environ.get("HOST", "0.0.0.0")
MDNS_NAME = os.environ.get("MDNS_NAME", "bitaxe-baller")
MDNS_ENABLED = os.environ.get("MDNS_ENABLED", "1") not in ("0", "false", "no", "")


def _can_bind(port):
    """Best-effort check that we can bind HOST:port. Closes immediately."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, port))
        s.close()
        return True
    except OSError:
        return False


def _pick_port():
    """If PORT env var is set, honor it. Otherwise prefer 80 for clean URLs
    (no :port in the address bar) and fall back to 5050 when port 80 isn't
    available — typically because the app isn't running as root."""
    if "PORT" in os.environ:
        return int(os.environ["PORT"])
    if _can_bind(80):
        return 80
    return 5050


PORT = _pick_port()


def _url(host, port):
    """Format URL, omitting :80 since browsers default to it for http://."""
    return f"http://{host}" if port == 80 else f"http://{host}:{port}"


def start_mdns(lan_ip, port, name=MDNS_NAME):
    """Publish an mDNS / Bonjour service so the dashboard is reachable at
    http://<name>.local:<port> from any device on the LAN. Returns
    (zeroconf, info) or (None, None) on any failure."""
    try:
        from zeroconf import IPVersion, ServiceInfo, Zeroconf
    except ImportError:
        print(f"[mdns] zeroconf not installed; skipping. pip install zeroconf to enable")
        return None, None
    if not lan_ip:
        return None, None
    try:
        zc = Zeroconf(ip_version=IPVersion.V4Only)
        info = ServiceInfo(
            "_http._tcp.local.",
            f"{name}._http._tcp.local.",
            addresses=[socket.inet_aton(lan_ip)],
            port=port,
            properties={"path": "/"},
            server=f"{name}.local.",
        )
        zc.register_service(info)
        return zc, info
    except Exception as e:
        print(f"[mdns] failed to register: {e}")
        return None, None


def main():
    cfg = load_config()
    with state_lock:
        for d in cfg.get("devices", []):
            state[d["ip"]] = init_device_state(d["ip"], d["label"])

    global poll_thread
    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()

    lan_ip = detect_lan_ip()

    zc = info = None
    if MDNS_ENABLED and HOST == "0.0.0.0":
        zc, info = start_mdns(lan_ip, PORT)

    print()
    print("=" * 64)
    print("  Bitaxe Baller  -  open the dashboard at:")
    print(f"    {_url('localhost', PORT)}".ljust(40) + "(this machine)")
    if lan_ip:
        print(f"    {_url(lan_ip, PORT)}".ljust(40) + "(from any device on your LAN)")
    else:
        print(f"    {_url('<this-machine-ip>', PORT)}".ljust(40) + "(from other devices)")
    if zc:
        print(f"    {_url(MDNS_NAME + '.local', PORT)}".ljust(40) + "(via mDNS / Bonjour)")
    print("=" * 64)
    if HOST == "0.0.0.0":
        print("  Bound to 0.0.0.0 - reachable from other devices on the network.")
        print("  macOS may prompt about incoming connections on first run; allow it.")
        if zc:
            print(f"  mDNS published as '{MDNS_NAME}.local' (Bonjour/Avahi).")
        if PORT != 80:
            print(f"  Tip: run with sudo to bind port 80 and drop ':{PORT}' from the URL")
            print(f"       sudo $(which python) app.py")
        print("=" * 64)
    print()
    try:
        app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
    finally:
        if zc:
            try:
                zc.unregister_service(info)
                zc.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
