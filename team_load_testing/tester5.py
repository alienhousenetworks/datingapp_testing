"""
================================================================================
LOAD TESTER 5 (Laptop 5) - Full Platform All-Features Load Test
================================================================================
Capacity: 2,000 - 3,000+ Concurrent Virtual Users.
Features: 100% of platform features (Feed v1/v2, Swipes, Chat, Confessions,
          Profile, Matches, Notifications, Subscriptions, Catalogs, Analytics).

HOW TO RUN ON LAPTOP 5:
    1. cd testing/team_load_testing
    2. pip install -r requirements.txt
    3. locust -f tester5.py
    4. Open http://localhost:8089 in your browser
    5. Enter Host (e.g. https://api01.spycenow.com or http://127.0.0.1:8000)
    6. Set Number of Users (e.g. 2000 or 3000) & Spawn Rate (e.g. 50-100/s)
    7. Click 'Start Swarming'
"""
from locust import events
from full_app_load_suite import create_full_suite_user_class

# All-feature test user class for Laptop 5
Laptop5_FullPlatformUser = create_full_suite_user_class("Laptop5", 5)


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    print("\n" + "=" * 70)
    print("🔥 [LOAD TESTER 5] Laptop 5 Ready — Full Platform Load Test (All Features)")
    print("👥 Target Capacity: 2,000 - 3,000 Concurrent Virtual Users")
    print(f"🎯 Target Host: {getattr(environment, 'host', 'http://127.0.0.1:8000')}")
    print("🌐 Open Web UI: http://localhost:8089 to control and start testing")
    print("=" * 70 + "\n")
