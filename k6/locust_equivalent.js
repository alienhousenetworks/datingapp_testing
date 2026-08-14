import http from 'k6/http';
import { check, sleep, group } from 'k6';

/**
 * k6 Load Test Script for SPYCE Backend (Equivalent to Locust test suite)
 * 
 * Target Server Requirements:
 *   - DISABLE_RATE_LIMITING=True (or RATE_LIMIT=999999 per IP)
 *   - USE_TEST_OTP=True, MAGIC_OTP=123456
 *   - REQUIRE_CAPTCHA=False
 *   - FACE_VERIFICATION=False
 * 
 * Execution on 4th VPS:
 *   k6 run --environment BASE_URL=https://api01.spycenow.com testing/k6/locust_equivalent.js
 */

// Global Configs from Environment Variables or Defaults
const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const MAGIC_OTP = __ENV.MAGIC_OTP || '123456';

// k6 Load Test Execution Stages (Scales up to 5,000 VUs, customizable)
export const options = {
  stages: [
    { duration: '30s', target: 500 },   // Warm-up ramp
    { duration: '1m',  target: 2000 },  // Steady load 2,000 users
    { duration: '2m',  target: 5000 },  // Peak load 5,000 users
    { duration: '30s', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],     // < 5% errors
    http_req_duration: ['p(95)<500'],   // 95% of requests below 500ms
  },
};

// Helper Utilities
function randomHex(length) {
  const chars = 'abcdef0123456789';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

function generateEmail() {
  return `load+${randomHex(10)}@example.com`;
}

function generateDeviceId() {
  return `load-device-${randomHex(8)}-${randomHex(4)}-${randomHex(4)}-${randomHex(12)}`;
}

function getHeaders(deviceId, token = null) {
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-Device-ID': deviceId,
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// User Context Initialization
function authenticateUser(email, deviceId) {
  let headers = getHeaders(deviceId);

  // 1. Register (OTP Request)
  let regRes = http.post(
    `${BASE_URL}/api/v1/auth/register/`,
    JSON.stringify({ email: email, device_id: deviceId, intent: 'signup' }),
    { headers: headers, tags: { name: 'auth:register' } }
  );

  check(regRes, {
    'register success (200)': (r) => r.status === 200,
  });

  if (regRes.status !== 200) {
    return null;
  }

  // 2. Verify OTP
  let verRes = http.post(
    `${BASE_URL}/api/v1/auth/otp/verify/`,
    JSON.stringify({ email: email, otp: MAGIC_OTP, device_id: deviceId }),
    { headers: headers, tags: { name: 'auth:otp_verify' } }
  );

  let isVerified = check(verRes, {
    'verify success (200)': (r) => r.status === 200,
    'has access token': (r) => r.json('access') !== undefined,
  });

  if (!isVerified) {
    return null;
  }

  const verData = verRes.json();
  const token = verData.access;
  const userId = verData.user_id;

  headers = getHeaders(deviceId, token);

  // 3. Mock Face Verification
  http.post(
    `${BASE_URL}/api/v1/verification/mock-complete/`,
    JSON.stringify({}),
    { headers: headers, tags: { name: 'verification:mock_complete' } }
  );

  // 4. Catalog Lookup
  let genderId = 1;
  let sexualityId = 1;

  let gRes = http.get(`${BASE_URL}/api/v1/genders/`, { headers: headers, tags: { name: 'options:genders' } });
  if (gRes.status === 200 && Array.isArray(gRes.json()) && gRes.json().length > 0) {
    genderId = gRes.json()[0].id || 1;
  }

  let sRes = http.get(`${BASE_URL}/api/v1/sexualities/`, { headers: headers, tags: { name: 'options:sexualities' } });
  if (sRes.status === 200 && Array.isArray(sRes.json()) && sRes.json().length > 0) {
    sexualityId = sRes.json()[0].id || 1;
  }

  // 5. Populate Onboarding Details
  const username = `usr_${randomHex(10)}`;
  const onboardingPayload = {
    username: username,
    name: `User ${username.substring(0, 6)}`,
    date_of_birth: '1998-05-15',
    gender: genderId,
    sexuality: sexualityId,
    preferred_genders: [genderId],
    bio: 'k6 load test simulated user profile for discovery feed.',
    latitude: 12.9716,
    longitude: 77.5946,
  };

  http.patch(
    `${BASE_URL}/api/v1/profile/me/`,
    JSON.stringify(onboardingPayload),
    { headers: headers, tags: { name: 'profile:onboarding_patch' } }
  );

  // 6. Init Location / Presence
  http.post(
    `${BASE_URL}/api/v1/users/last-active/`,
    JSON.stringify({ lat: 12.9716, lon: 77.5946 }),
    { headers: headers, tags: { name: 'users:last_active_init' } }
  );

  return { token: token, userId: userId, deviceId: deviceId, seenCandidates: [] };
}

// Default Main Function executed per VU iteration
export default function () {
  const email = generateEmail();
  const deviceId = generateDeviceId();

  // 1. Authenticate and setup user session once
  const user = authenticateUser(email, deviceId);
  if (!user) {
    sleep(1);
    return;
  }

  const headers = getHeaders(user.deviceId, user.token);

  // 2. Perform Weighted User Activity Loop
  for (let cycle = 0; cycle < 5; cycle++) {
    const roll = Math.random() * 100;

    if (roll < 10) {
      // Health check
      http.get(`${BASE_URL}/health/`, { tags: { name: 'health' } });
    } else if (roll < 25) {
      // Discovery feed (FastAPI v2)
      let feedRes = http.get(`${BASE_URL}/api/v2/feed/?count=10`, { headers: headers, tags: { name: 'feed:list' } });
      if (feedRes.status === 200 && feedRes.json('results')) {
        const items = feedRes.json('results');
        items.forEach((item) => {
          const cid = item.id || item.user_id;
          if (cid) user.seenCandidates.push(cid.toString());
        });
      }
    } else if (roll < 40) {
      // User / Profile checks
      http.get(`${BASE_URL}/api/v1/users/me/`, { headers: headers, tags: { name: 'users:me' } });
      http.get(`${BASE_URL}/api/v1/profile/me/`, { headers: headers, tags: { name: 'profile:me' } });
    } else if (roll < 55) {
      // Like or Pass candidate if feed candidates seen
      if (user.seenCandidates.length > 0) {
        const targetId = user.seenCandidates.shift();
        const action = Math.random() > 0.3 ? 'send' : 'pass';
        http.post(
          `${BASE_URL}/api/v1/interaction/${action}/`,
          JSON.stringify({ target_user_id: targetId }),
          { headers: headers, tags: { name: `interaction:${action}` } }
        );
      }
    } else if (roll < 70) {
      // Update Presence / Last Active
      http.post(
        `${BASE_URL}/api/v1/users/last-active/`,
        JSON.stringify({ lat: 12.9716, lon: 77.5946 }),
        { headers: headers, tags: { name: 'users:last_active' } }
      );
    } else if (roll < 85) {
      // Session / Catalogs / Verification
      http.get(`${BASE_URL}/api/v1/auth/session/`, { headers: headers, tags: { name: 'auth:session' } });
      http.get(`${BASE_URL}/api/v1/social/`, { headers: headers, tags: { name: 'social:list' } });
      http.get(`${BASE_URL}/api/v1/subscriptions/status/`, { headers: headers, tags: { name: 'subscriptions:status' } });
    } else {
      // WS ticket
      http.post(
        `${BASE_URL}/api/v1/auth/ws-ticket/`,
        JSON.stringify({}),
        { headers: headers, tags: { name: 'auth:ws_ticket' } }
      );
    }

    sleep(Math.random() * 1.5 + 0.5); // Random wait between 0.5s - 2.0s
  }
}
