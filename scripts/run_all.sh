#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export USE_TEST_OTP=True
export MAGIC_OTP="${MAGIC_OTP:-123456}"
export REQUIRE_CAPTCHA=False
export FACE_VERIFICATION=False
export ALLOW_MOCK_VERIFICATION=True
export BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "========== 1/3 Unit =========="
bash scripts/run_unit.sh || {
  echo "Unit tests failed (Django/DB may be required for some)."
  exit 1
}

echo "========== 2/3 Integration =========="
bash scripts/run_integration.sh || {
  echo "Integration tests failed or API not running at ${BASE_URL}."
  exit 1
}

echo "========== 3/3 Load (short) =========="
LOCUST_USERS="${LOCUST_USERS:-5}" \
LOCUST_SPAWN_RATE="${LOCUST_SPAWN_RATE:-2}" \
LOCUST_RUN_TIME="${LOCUST_RUN_TIME:-15s}" \
  bash scripts/run_load.sh || {
  echo "Load test failed."
  exit 1
}

echo "========== All suites finished =========="
