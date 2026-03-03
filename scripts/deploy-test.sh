#!/usr/bin/env bash
# Deploy PWA changes to the test instance at 10.10.0.102
# Usage: ./scripts/deploy-test.sh
#
# Syncs the pwa/ directory to the Vite dev server on the test LXC.
# Vite HMR picks up changes automatically — no restart needed.

set -euo pipefail

TEST_HOST="root@10.10.0.102"
TEST_PATH="/home/pwa-demo/pwa/"
SOURCE_PATH="$(cd "$(dirname "$0")/.." && pwd)/pwa/"

echo "Deploying PWA to test instance ($TEST_HOST)..."

rsync -avz --delete \
  --exclude node_modules \
  --exclude dist \
  --exclude .vite \
  --exclude vite.config.ts \
  "$SOURCE_PATH" "${TEST_HOST}:${TEST_PATH}"

echo "Done. Test instance updated at http://10.10.0.102:3000"
