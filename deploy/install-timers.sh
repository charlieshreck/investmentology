#!/bin/bash
# Install investmentology systemd timers
set -euo pipefail

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"

TIMERS=(
  investmentology-screen
  investmentology-post-screen
  investmentology-daily-analyze
  investmentology-monitor
  investmentology-premarket
)

echo "Copying service and timer units..."
for name in "${TIMERS[@]}"; do
  cp "$DEPLOY_DIR/${name}.service" /etc/systemd/system/
  cp "$DEPLOY_DIR/${name}.timer" /etc/systemd/system/
done

echo "Reloading systemd..."
systemctl daemon-reload

echo "Enabling and starting timers..."
for name in "${TIMERS[@]}"; do
  systemctl enable "${name}.timer"
  systemctl start "${name}.timer"
done

echo "Timer status:"
systemctl list-timers | grep investmentology || true

echo "Done."
