# Load testing (Locust)

## Prerequisites

- Backend running with:
  - `USE_TEST_OTP=True`
  - `MAGIC_OTP=123456`
  - `REQUIRE_CAPTCHA=False`
  - `FACE_VERIFICATION=False`
- Redis + Postgres healthy

## Run (UI)

```bash
cd testing
source .venv/bin/activate   # if used
locust -f load/locustfile.py --host http://127.0.0.1:8000
```

Open http://localhost:8089

## Run (headless)

```bash
locust -f load/locustfile.py --host http://127.0.0.1:8000 \
  --users 20 --spawn-rate 5 --run-time 60s --headless
```

Or:

```bash
./scripts/run_load.sh
```

## User classes

| Class | Behavior |
|-------|----------|
| `SpyceUser` | Full session: magic OTP signup → mock face → feed/me/heartbeat loop |
| `AuthOnlyUser` | Auth storm only (register + verify) |

## Notes

- Each virtual user creates a unique email (`load+…@example.com`).
- OTP is always `MAGIC_OTP` (default `123456`).
- Captcha tokens are never sent.
- Real face liveness is never called; mock-complete runs once on start.
