#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Automatically raise file descriptor limit for 20k+ concurrent sockets
ulimit -n 65535 2>/dev/null || true

export BASE_URL="${BASE_URL:-https://api01.spycenow.com}"
export MAGIC_OTP="${MAGIC_OTP:-123456}"
export USE_TEST_OTP=True
export REQUIRE_CAPTCHA=False
export FACE_VERIFICATION=False

USERS="${LOCUST_USERS:-20000}"
SPAWN="${LOCUST_SPAWN_RATE:-200}"
TIME="${LOCUST_RUN_TIME:-10m}"

echo "==> SPYCE 20k Load test ${BASE_URL} users=${USERS} spawn=${SPAWN} time=${TIME}"
echo "    MAGIC_OTP=${MAGIC_OTP} bot=off face=mock"

locust -f load/locustfile.py \
  --host "${BASE_URL}" \
  --users "${USERS}" \
  --spawn-rate "${SPAWN}" \
  --run-time "${TIME}" \
  --web-host 0.0.0.0 \
  --web-port 8089 \
  "$@"
