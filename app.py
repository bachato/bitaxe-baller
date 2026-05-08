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


def device_summary(s):
    if not s["latest"]:
        return {
            "ip": s["ip"],
            "label": s["label"],
            "online": s["online"],
            "lastError": s["last_error"],
            "history": [],
            "events": list(s["events"]),
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
            "fanSpeed": latest.get("fanrpm", 0),
            "fanPercent": latest.get("fanspeed", 0),
            "autofanspeed": latest.get("autofanspeed", 0),
            "sharesAccepted": latest.get("sharesAccepted", 0),
            "sharesRejected": latest.get("sharesRejected", 0),
            "bestDiff": latest.get("bestDiff", "0"),
            "bestSessionDiff": latest.get("bestSessionDiff", "0"),
            "uptime": latest.get("uptimeSeconds", 0),
            "stratumUrl": latest.get("stratumURL", ""),
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


@app.route("/api/devices")
def api_devices():
    with state_lock:
        return jsonify([device_summary(s) for s in state.values()])


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


PORT = int(os.environ.get("PORT", 5050))
HOST = os.environ.get("HOST", "0.0.0.0")


def main():
    cfg = load_config()
    with state_lock:
        for d in cfg.get("devices", []):
            state[d["ip"]] = init_device_state(d["ip"], d["label"])

    global poll_thread
    poll_thread = threading.Thread(target=poll_loop, daemon=True)
    poll_thread.start()

    lan_ip = detect_lan_ip()
    print()
    print("=" * 64)
    print("  Bitaxe Baller  -  open the dashboard at:")
    print(f"    http://localhost:{PORT}".ljust(40) + "(this machine)")
    if lan_ip:
        print(f"    http://{lan_ip}:{PORT}".ljust(40) + "(from any device on your LAN)")
    else:
        print(f"    http://<this-machine-ip>:{PORT}".ljust(40) + "(from other devices)")
    print("=" * 64)
    if HOST == "0.0.0.0":
        print("  Bound to 0.0.0.0 - reachable from other devices on the network.")
        print("  macOS may prompt about incoming connections on first run; allow it.")
        print("=" * 64)
    print()
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
