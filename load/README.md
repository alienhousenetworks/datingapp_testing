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
