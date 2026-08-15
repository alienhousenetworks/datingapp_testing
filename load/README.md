# Load testing (Locust)

## Product test (seeded complete users) — use this

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

| Class | Weight | Behavior |
|-------|--------|----------|
| `SpyceUser` | 10 | Full session: magic OTP signup → mock face → complete profile → loop every client API |
| `AuthOnlyUser` | 1 | Auth storm only (register + verify) |

`SpyceUser` hits the real product paths, not just onboarding:

| Area | Requests |
|------|----------|
| Feed | `GET /api/v1/feed/`, `GET /api/v2/feed/` |
| Likes / match | `POST /interaction/send/`, `/pass/`, `/interested/`, `GET /received/`, `GET /matches/` |
| Chat | `GET /conversations/`, `GET /messages/`, `POST /messages/` |
| Confessions | list, geo feed, create, relate, repost, comments, chat-request |
| Profile | `GET/PATCH /profile/me/`, `GET /profile/{id}/`, username check, avatars, mood |
| Presence / geo | `POST /users/last-active/`, reverse + city autocomplete |
| Catalogs / theme | genders, sexualities, intents, turn_ons, moods, languages, theme |
| Wallet / calls | subscription status, ICE servers, call quota/wallet |
| Other | session, token refresh, WS ticket, analytics, verification, blocks |

Virtual users share a pool of IDs so likes can land on other load-test users and produce matches.

## Notes

- Each virtual user creates a unique email (`load+…@example.com`).
- OTP is always `MAGIC_OTP` (default `123456`).
- Captcha tokens are never sent.
- Real face liveness is never called; mock-complete runs once on start.
