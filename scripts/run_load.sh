#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
export MAGIC_OTP="${MAGIC_OTP:-123456}"
export USE_TEST_OTP=True
export REQUIRE_CAPTCHA=False
export FACE_VERIFICATION=False

USERS="${LOCUST_USERS:-20}"
SPAWN="${LOCUST_SPAWN_RATE:-5}"
TIME="${LOCUST_RUN_TIME:-60s}"

echo "==> Load test ${BASE_URL} users=${USERS} spawn=${SPAWN} time=${TIME}"
echo "    MAGIC_OTP=${MAGIC_OTP} bot=off face=mock"

locust -f load/locustfile.py \
  --host "${BASE_URL}" \
  --users "${USERS}" \
  --spawn-rate "${SPAWN}" \
  --run-time "${TIME}" \
  --headless \
  "$@"
