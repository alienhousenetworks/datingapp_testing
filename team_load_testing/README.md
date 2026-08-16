# 🚀 SPYCE 5-Laptop Distributed Load Testing Suite

This folder contains **5 independent Locust load test scripts** created for a team of **5 people running tests simultaneously from their own laptops**.

Each person runs the **exact same complete, all-feature load test** (Feed v1/v2, Swiping, Matching, Chat, Confessions, Profile, Notifications, Catalogs, Subscriptions, Analytics, Health), calibrated to easily push **2,000 to 3,000+ virtual users** per machine.

---

## 👥 Laptop Assignment Matrix

| Laptop / Person | Script to Run | Capacity per Node | Total Swarm with 5 Laptops |
| :--- | :--- | :--- | :--- |
| **Laptop 1 (Person 1)** | `tester1.py` | 2,000 - 3,000 VUs | **10,000 - 15,000+ Users** |
| **Laptop 2 (Person 2)** | `tester2.py` | 2,000 - 3,000 VUs | (Simultaneously across all |
| **Laptop 3 (Person 3)** | `tester3.py` | 2,000 - 3,000 VUs | subsystems & DB connections) |
| **Laptop 4 (Person 4)** | `tester4.py` | 2,000 - 3,000 VUs | |
| **Laptop 5 (Person 5)** | `tester5.py` | 2,000 - 3,000 VUs | |

---

## 🛠️ Step-by-Step Instructions for Each Team Member

### 1️⃣ Step 1: Pull Code & Install Dependencies
Open a Terminal on your laptop and navigate to this folder:
```bash
cd testing/team_load_testing
pip install -r requirements.txt
```

---

### 2️⃣ Step 2: Start Your Assigned Script

#### 💻 Person on Laptop 1:
```bash
locust -f tester1.py
```
*(Or run `./run_tester1.sh`)*

#### 💻 Person on Laptop 2:
```bash
locust -f tester2.py
```
*(Or run `./run_tester2.sh`)*

#### 💻 Person on Laptop 3:
```bash
locust -f tester3.py
```
*(Or run `./run_tester3.sh`)*

#### 💻 Person on Laptop 4:
```bash
locust -f tester4.py
```
*(Or run `./run_tester4.sh`)*

#### 💻 Person on Laptop 5:
```bash
locust -f tester5.py
```
*(Or run `./run_tester5.sh`)*

---

### 3️⃣ Step 3: Open Web UI & Start Test
1. Open your browser and go to: **[http://localhost:8089](http://localhost:8089)**
2. In the Locust Web UI form:
   - **Host:** Enter your backend URL:
     - Remote/Staging: `https://api01.spycenow.com`
     - Local Dev: `http://127.0.0.1:8000`
   - **Number of users (peak concurrency):** `2000` (or `3000`)
   - **Ramp up (users spawned/second):** `50` to `100`
3. Click **"Start swarming"**!

---

## 🌟 What Every Script Tests (100% Full Feature Coverage)

Every single virtual user created across all 5 laptops automatically exercises:

1. **Auto-Signup & Onboarding:** Magic OTP verification, mock verification, profile initialization, DPDP consent.
2. **Discovery & Feeds:**
   - Django v1 Feed (pagination & cursor scrolling)
   - Feed AI cache refresh with multi-attribute filtering (age, online status, city)
   - FastAPI v2 high-concurrency feed + dynamic geo nearby recalculation
3. **Swipes & Matches:**
   - Send Like
   - Send Pass
   - Send Superlike / Interested
   - Received Likes feed
   - Direct Icebreaker Conversation Requests + Accept/Reject
   - Match list & Match card details
4. **Instant Messaging & Real-Time Chat:**
   - Active conversation list & conversation detail
   - Message history retrieval
   - Sending live text chat messages
   - Message draft checking
5. **Confession Wall & Social Feed:**
   - Geo-located confession feed & general list
   - Publishing confessions with mood tags (`LONELY`, `CURIOUS`, `HAPPY`, `ANXIOUS`, etc.)
   - Relate / Like confessions
   - Reposting confessions
   - Viewing & posting comments
   - Sending anonymous Confession Chat Requests
   - Checking badge counts, accepting & rejecting confession chat requests
6. **Profile, Media & Mood:**
   - Fetch own profile (`/profile/me/`)
   - Profile patch (bio updates, coordinate jitter)
   - Checking other user profiles (`/profile/{id}/`)
   - Real-time username availability checks
   - Image upload status & avatar catalogs
   - Mood options & current mood update
7. **Presence & Push Notifications:**
   - Last-active presence heartbeats
   - FCM push device registration
   - Notification inbox polling
8. **System Catalogs & Themes:**
   - Genders, Sexualities, Intents, Turn-ons, Languages catalogs
   - Theme options and active theme
   - Geo city autocomplete & reverse geocoding
9. **Wallet, Subscriptions & Calls:**
   - Subscription tier & billing history check
   - Coin wallet balance & call time packages
   - Calling quota check & WebRTC ICE servers
10. **Analytics & Health:**
    - Live telemetry beacon events
    - Health, Liveness, and Readiness endpoints (`/health/`, `/health/live/`, `/health/ready/`)
