#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
export USE_TEST_OTP=True
export ENABLE_LEGACY_OTP_AUTH=True
export MAGIC_OTP="${MAGIC_OTP:-123456}"
export REQUIRE_CAPTCHA=False
export FACE_VERIFICATION=False
export ALLOW_MOCK_VERIFICATION=True
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"

echo "==> Integration tests against ${BASE_URL}"
echo "    (MAGIC_OTP=${MAGIC_OTP}, captcha=off, face=off)"
python -m pytest integration/ -v -m integration "$@"
