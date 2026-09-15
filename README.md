# SPYCE Backend Testing Suite

Standalone test suite for the SPYCE dating app backend. Lives **outside** `backend/` — no backend source files are modified.

## Test modes

| Folder | Purpose | Needs running API? |
|--------|---------|--------------------|
| `unit/` | Pure / Django-import unit tests of backend logic | No (uses Django + DB/Redis for some) |
| `integration/` | Full HTTP flows against a live API | Yes |
| `load/` | Locust load tests | Yes |

## Forced test flags (matching your QA setup)

These are applied by the suite (and expected on the server for integration/load):

| Flag | Value | Effect |
|------|-------|--------|
| `USE_TEST_OTP` | `True` | Magic OTP path |
| `ENABLE_LEGACY_OTP_AUTH` | `True` | Keep Email OTP APIs while Firebase login is tested |
| `MAGIC_OTP` | `123456` | Fixed OTP (no real email) |
| `REQUIRE_CAPTCHA` | `False` | Bot / Turnstile off |
| `FACE_VERIFICATION` | `False` | Mock face path |
| `ALLOW_MOCK_VERIFICATION` | `True` | `/verification/mock-complete/` allowed |

## Quick start

```bash
cd "DatingApp Full directory/testing"

# Optional: dedicated venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and edit env if needed
cp .env.example .env
```

### 1. Unit tests

Imports backend code (read-only). Pure suite-flag tests always run. Django-import tests need a full backend venv (Django + deps) and usually Postgres/Redis.

```bash
./scripts/run_unit.sh
# or
pytest unit/ -v -p no:django
```

If Django deps are incomplete, those tests **skip** cleanly (they do not fail the suite).

### 2. Integration tests

Start the backend first (`runserver` or Docker), then:

```bash
export BASE_URL=http://127.0.0.1:8000
./scripts/run_integration.sh
# or
pytest integration/ -v
```

### 3. Load tests

Product capacity test uses **seeded complete users** and one-time login
only (no auth APIs in the loop):

```bash
export BASE_URL=https://api01.spycenow.com
export SEED_USERS_FILE=load/load_users.jsonl
./scripts/run_seeded_load.sh
# or
locust -f load/locustfile_seeded.py --host "$BASE_URL"
```

`load/locustfile.py` is the older signup-onboard file, not a product-capacity test.

### Run everything

```bash
./scripts/run_all.sh
```

## Layout

```text
testing/
├── suite_config/     # Shared test config (magic OTP, flags, paths)
├── helpers/          # HTTP client, auth helpers
├── unit/             # Unit tests
├── integration/      # API integration tests
├── load/             # Locust load scenarios
├── scripts/          # Runners
├── conftest.py
├── pytest.ini
├── requirements.txt
└── README.md
```

> Package is named `suite_config` (not `config`) so it never shadows Django’s `config.settings`.

## Coverage map (backend APIs)

| Area | Endpoints exercised |
|------|---------------------|
| Health | `GET /health/`, `/health/live/`, `/health/ready/` |
| Auth | `POST /api/v1/auth/register/`, `otp/verify/`, `session/`, `logout/`, `ws-ticket/` |
| Users | `GET /api/v1/users/me/`, `POST last-active/` |
| Profile | `GET/PATCH /api/v1/profile/me/`, options (genders, intents, …) |
| Feed | `GET /api/v1/feed/` |
| Interaction | `POST /api/v1/interaction/send/`, `pass/`, `GET received/` |
| Verification | `GET status/`, `POST mock-complete/` (face off) |
| Geo | `GET /api/v1/geo/cities/` |
| Subscriptions | `GET /api/v1/subscriptions/status/` |

## Notes

- Integration tests use a unique email per run (`pytest+{uuid}@example.com`).
- OTP verification always uses `MAGIC_OTP` from config (`123456` by default).
- Captcha tokens are omitted (`REQUIRE_CAPTCHA=False`).
- Face liveness uses mock complete, not AWS Rekognition.
- Do **not** enable `USE_TEST_OTP` / `MAGIC_OTP` when backend `ENV=production`.
# datingapp_testing
