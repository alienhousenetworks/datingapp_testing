# k6 Load Testing Suite (JS)

This directory contains standalone JavaScript load testing scripts for **k6**, tailored for testing the SPYCE DatingApp 3-VPS production backend (`api01.spycenow.com`) from a 4th load generator VPS.

---

## Active Application Endpoints Tested

The k6 scripts perform non-stop active application requests across all core features:

1. **Feed Discovery (FastAPI v2)**: `GET /api/v2/feed/?count=10`
2. **Confessions & Social**: `GET /api/v1/social/` (Feed) & `POST /api/v1/social/` (Create Confession Post)
3. **Interactions**: `POST /api/v1/interaction/send/` (Like) & `POST /api/v1/interaction/pass/` (Pass)
4. **Matches & Messaging**: `GET /api/v1/matches/` & `GET /api/v1/conversations/`
5. **Profile & User Me**: `GET /api/v1/users/me/` & `GET /api/v1/profile/me/`
6. **Presence & Geolocation**: `POST /api/v1/users/last-active/` (`lat`, `lon`)
7. **Options & Catalogs**: `GET /api/v1/genders/`, `GET /api/v1/sexualities/`, `GET /api/v1/intents/`

---

## Files in this Directory

* **`high_concurrency_20k.js`**: Tuned for **20,000 Virtual Users (20k VUs)**. Performs active application traffic across Feed, Confessions, Like/Pass Interactions, Matches, Conversations, Profile, and Presence updates.
* **`locust_equivalent.js`**: Mirrors the complete user lifecycle flow from `testing/load/locustfile.py` (Registration $\rightarrow$ Magic OTP verification $\rightarrow$ Mock Face verification $\rightarrow$ Catalog lookup $\rightarrow$ Profile onboarding $\rightarrow$ Feed discovery $\rightarrow$ Like/Pass interactions).

---

## 1. Backend Environment Setup (`.env` on KVM-B APP server)

Ensure your backend `.env` on `KVM-B` has rate limits disabled or set high so your load generator IP is not throttled:

```bash
# Set in backend .env on KVM-B
DISABLE_RATE_LIMITING=True

# Or set high limits per IP
REST_FRAMEWORK_RATE_LIMIT_PER_MINUTE=999999
AUTH_RATE_LIMIT_PER_MINUTE=999999

# Test Auth Settings
USE_TEST_OTP=True
MAGIC_OTP=123456
REQUIRE_CAPTCHA=False
FACE_VERIFICATION=False
```

Restart the backend container on KVM-B after updating `.env`:
```bash
docker compose -f docker/production/triad/app/docker-compose.yml restart
```

---

## 2. 4th VPS OS Tuning (Before Running 20k Test)

On your 4th VPS (Ubuntu), increase the Linux file descriptor limit and socket memory before executing tests:

```bash
# 1. Set open file limit for active shell
ulimit -n 100000

# 2. Add to /etc/security/limits.conf for permanent persistence:
# * soft nofile 100000
# * hard nofile 100000

# 3. Optimize kernel TCP parameters
sudo sysctl -w net.core.somaxconn=65535
sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535"
sudo sysctl -w net.ipv4.tcp_tw_reuse=1
```

---

## 3. Installing k6 on 4th VPS (Ubuntu)

```bash
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

---

## 4. Execution Commands

### Run 20k Concurrent Virtual Users Full Application Test
```bash
k6 run --environment BASE_URL=https://api01.spycenow.com \
       --environment MAGIC_OTP=123456 \
       testing/k6/high_concurrency_20k.js
```

### Run Lifecycle Flow Test
```bash
k6 run --environment BASE_URL=https://api01.spycenow.com \
       --environment MAGIC_OTP=123456 \
       testing/k6/locust_equivalent.js
```
