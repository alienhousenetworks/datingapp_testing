#!/usr/bin/env bash
# Product load test using pre-seeded complete users (no signup storm).
#
# Seed first on KVM-B:
#   bash docker/production/triad/scripts/seed-load-users.sh
# Copy credentials here:
#   scp root@KVM_B:/opt/spyce/seed/load_users.jsonl testing/load/load_users.jsonl
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ulimit -n 65535 2>/dev/null || true

export BASE_URL="${BASE_URL:-https://api01.spycenow.com}"
export MAGIC_OTP="${MAGIC_OTP:-123456}"
export SEED_USERS_FILE="${SEED_USERS_FILE:-$ROOT/load/load_users.jsonl}"

USERS="${LOCUST_USERS:-500}"
SPAWN="${LOCUST_SPAWN_RATE:-20}"
TIME="${LOCUST_RUN_TIME:-10m}"

if [[ ! -f "$SEED_USERS_FILE" ]]; then
  echo "Missing $SEED_USERS_FILE"
  echo "Seed on KVM-B then copy load_users.jsonl here."
  exit 1
fi

echo "==> Seeded product load ${BASE_URL}"
echo "    users=${USERS} spawn=${SPAWN} time=${TIME}"
echo "    file=${SEED_USERS_FILE} ($(wc -l < "$SEED_USERS_FILE" | tr -d ' ') accounts)"

locust -f load/locustfile_seeded.py \
  --host "${BASE_URL}" \
  --users "${USERS}" \
  --spawn-rate "${SPAWN}" \
  --run-time "${TIME}" \
  --web-host 0.0.0.0 \
  --web-port 8089 \
  "$@"
