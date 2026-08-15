# Load testing (Locust)

## Product test (seeded complete users) — use this

Auth is **not** part of the load mix. Each virtual user logs in **once**
on start (only if the seed row has no access token). The loop then hits
real product APIs only.

Signup-on-start cannot use feed/like/confession/chat (incomplete + unverified).
Seed 10k complete users **on KVM-B (APP)**, then run `locustfile_seeded.py`.

```bash
# 1) On KVM-B (APP) only — not DATA, not EDGE
cd /opt/spyce/backend
bash docker/production/triad/scripts/seed-load-users.sh --count 10000

# 2) Copy credentials to the Locust machine
scp root@KVM_B:/opt/spyce/seed/load_users.jsonl testing/load/load_users.jsonl

# 3) APP .env on KVM-B for the test window
#    ALLOW_LOAD_TESTING=true
#    USE_TEST_OTP=true
#    MAGIC_OTP=123456
#    DISABLE_RATE_LIMITING=true

# 4) Run Locust (laptop or any box with the JSONL)
cd testing
SEED_USERS_FILE=load/load_users.jsonl \
  locust -f load/locustfile_seeded.py --host https://api01.spycenow.com \
  --users 500 --spawn-rate 20 --run-time 10m
```

Or: `./scripts/run_seeded_load.sh`

Keep `--users` at or below the seeded count.

Optional JSONL columns: `access` / `access_token` / `token` (and
`refresh` / `refresh_token`). If `access` is present, Locust skips login
entirely.

## What the seeded loop hits

| Area | Requests |
|------|----------|
| Feed load | `GET /api/v2/feed/`, `GET /api/v1/feed/` |
| Like / pass / interested | `POST /interaction/send/`, `/pass/`, `POST /interested/`, `GET /received/` |
| Send request | `POST /interaction/start_conversation/`, `POST /interaction/accept_request/` |
| Chat | `GET /conversations/`, `GET /conversations/{id}/`, `GET /messages/`, `POST /messages/` |
| Confessions | list, geo feed, create, detail, relate (like), repost, comments, chat-request |
| Profile | `GET /profile/me/`, `GET /users/me/`, `GET /profile/{id}/` |
| Matches | `GET /matches/` |

**Not** in the loop: register, OTP, token refresh, session, ws-ticket.

## Signup-storm file (old)

`locustfile.py` still exists for auth/onboarding stress. It is **not** a product-capacity test.

## Prerequisites

- Backend running with:
  - `USE_TEST_OTP=True`
  - `MAGIC_OTP=123456`
  - `REQUIRE_CAPTCHA=False`
  - `FACE_VERIFICATION=False`
  - `ALLOW_LOAD_TESTING=true` when `ENV=production`
- Redis + Postgres healthy
- For `locustfile_seeded.py`: `SEED_USERS_FILE` from `seed_load_users`

## Run (UI)

```bash
cd testing
source .venv/bin/activate   # if used
locust -f load/locustfile_seeded.py --host https://api01.spycenow.com
```

Open http://localhost:8089

## Run (headless)

```bash
SEED_USERS_FILE=load/load_users.jsonl \
  locust -f load/locustfile_seeded.py --host https://api01.spycenow.com \
  --users 500 --spawn-rate 20 --run-time 10m --headless
```

Or:

```bash
./scripts/run_seeded_load.sh
```

## User classes

| Class | File | Behavior |
|-------|------|----------|
| `SeededProductUser` | `locustfile_seeded.py` | One login if needed, then feature APIs only |
| `SpyceUser` | `locustfile.py` | Signup + onboard once, then feature APIs (no auth storm) |

## Notes

- Seeded VUs claim one row from `load_users.jsonl` (email + device + partner chat).
- OTP is always `MAGIC_OTP` (default `123456`) and is used at most once per VU.
- Captcha tokens are never sent.
- Failed login stops that VU instead of retrying auth in the loop.
