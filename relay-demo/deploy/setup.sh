#!/usr/bin/env bash
# One-time setup for the demo desktop on the VPS. Idempotent.
#
#   sudo bash /opt/bitaxe-baller-demo/deploy/setup.sh
#
# Expects files already scp'd to /opt/bitaxe-baller-demo/:
#   demo_desktop.py
#   requirements.txt
#   deploy/bitaxe-baller-demo.service
#   .env  (contains DEMO_INSTALL_UUID=<uuid>)
set -euo pipefail

APP_DIR="/opt/bitaxe-baller-demo"
APP_USER="bitaxeballer"

cd "${APP_DIR}"

echo "==> creating venv if needed"
if [[ ! -d venv ]]; then
  python3 -m venv venv
fi

echo "==> installing python deps"
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet -r requirements.txt

echo "==> chowning ${APP_DIR} to ${APP_USER}"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

echo "==> installing systemd unit"
install -m 644 deploy/bitaxe-baller-demo.service /etc/systemd/system/bitaxe-baller-demo.service
systemctl daemon-reload

echo "==> enabling + starting bitaxe-baller-demo"
systemctl enable bitaxe-baller-demo
systemctl restart bitaxe-baller-demo
sleep 2
systemctl status bitaxe-baller-demo --no-pager | head -10

echo "==> done"
