#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export USE_TEST_OTP=True
export MAGIC_OTP="${MAGIC_OTP:-123456}"
export REQUIRE_CAPTCHA=False
export FACE_VERIFICATION=False
export ALLOW_MOCK_VERIFICATION=True
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.dev}"

# Backend import path
export PYTHONPATH="${ROOT}/../backend/datingapp:${ROOT}/../backend/datingapp/core:${ROOT}:${PYTHONPATH:-}"

# Prefer a venv that has Django (backend modules). Fall back to testing/.venv.
if ! python -c "import django" 2>/dev/null; then
  for cand in \
    "${ROOT}/.venv/bin/activate" \
    "${ROOT}/../backend/datingapp/test_env/bin/activate" \
    "${ROOT}/../backend/test_env/bin/activate" \
    "${ROOT}/../backend/datingapp/core/.venv/bin/activate"
  do
    if [[ -f "$cand" ]]; then
      # shellcheck disable=SC1090
      source "$cand"
      echo "==> Using venv: $cand"
      if python -c "import django" 2>/dev/null; then
        break
      fi
    fi
  done
fi

echo "==> Unit tests (magic OTP, bot=off, face=off)"
# -p no:django avoids pytest-django auto-setup (we use unit/conftest django_ready)
python -m pytest unit/ -v -p no:django "$@"
