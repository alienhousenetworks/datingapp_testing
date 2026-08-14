import http from 'k6/http';
import { check, sleep } from 'k6';

/**
 * 20k Concurrent Virtual Users Load Test for 3-VPS SPYCE Backend
 * 
 * Purpose:
 *   Performs realistic, non-stop application load (Feed, Confessions, Likes/Passes,
 *   Profile, Presence, Matches, Conversations) across 20,000 concurrent Virtual Users.
 * 
 * Execution on 4th VPS:
 *   ulimit -n 100000
 *   k6 run --environment BASE_URL=https://api01.spycenow.com testing/k6/high_concurrency_20k.js
 */

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const MAGIC_OTP = __ENV.MAGIC_OTP || '123456';

export const options = {
  stages: [
    { duration: '30s', target: 2000 },   // Ramp to 2,000 VUs
    { duration: '1m',  target: 10000 },  // Ramp to 10,000 VUs
    { duration: '3m',  target: 20000 },  // Sustain 20,000 VUs peak load
    { duration: '1m',  target: 5000 },   // Step down
    { duration: '30s', target: 0 },      // Ramp down
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],      // < 5% error rate allowed
    http_req_duration: ['p(95)<1000'],   // 95% of requests under 1s
  },
  discardResponseBodies: false,
  noConnectionReuse: false,
};

function randomHex(length) {
  const chars = 'abcdef0123456789';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

export function setup() {
  // Pre-register and set up a pool of authenticated users / master user
  const email = `load_master_${randomHex(8)}@example.com`;
  const deviceId = `load-master-device-${randomHex(8)}`;
  const headers = { 'Content-Type': 'application/json', 'X-Device-ID': deviceId };

  http.post(`${BASE_URL}/api/v1/auth/register/`, JSON.stringify({ email: email, device_id: deviceId, intent: 'signup' }), { headers: headers });
  
  let verRes = http.post(`${BASE_URL}/api/v1/auth/otp/verify/`, JSON.stringify({ email: email, otp: MAGIC_OTP, device_id: deviceId }), { headers: headers });

  let token = null;
  if (verRes.status === 200 && verRes.json('access')) {
    token = verRes.json('access');
  }

  // Populate onboarding details so feed & interactions work smoothly
  if (token) {
    const authHeaders = { ...headers, Authorization: `Bearer ${token}` };
    http.patch(
      `${BASE_URL}/api/v1/profile/me/`,
      JSON.stringify({
        username: `master_${randomHex(6)}`,
        name: 'Load Master',
        gender: 1,
        sexuality: 1,
        latitude: 12.9716,
        longitude: 77.5946,
      }),
      { headers: authHeaders }
    );
  }

  return { token: token, deviceId: deviceId };
}

export default function (data) {
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'X-Device-ID': data.deviceId || 'k6-20k-device',
  };

  if (data.token) {
    headers['Authorization'] = `Bearer ${data.token}`;
  }

  // Realistic Application Activity Distribution
  const choice = Math.random();

  if (choice < 0.25) {
    // 1. DISCOVERY FEED REQUESTS (25%) - FastAPI v2 Async Feed (Redis pool + card mget)
    let feedRes = http.get(`${BASE_URL}/api/v2/feed/?count=10`, { headers: headers, tags: { name: 'feed:list' } });
    check(feedRes, { 'feed status 200/304': (r) => r.status === 200 || r.status === 304 });

  } else if (choice < 0.45) {
    // 2. CONFESSIONS & SOCIAL FEED REQUESTS (20%)
    if (Math.random() < 0.8) {
      // List confessions
      let confRes = http.get(`${BASE_URL}/api/v1/social/`, { headers: headers, tags: { name: 'confession:list' } });
      check(confRes, { 'confession list 200/304': (r) => r.status === 200 || r.status === 304 });
    } else {
      // Post new anonymous confession
      let postRes = http.post(
        `${BASE_URL}/api/v1/social/`,
        JSON.stringify({
          content: `k6 load test confession post ${randomHex(6)}`,
          mood_tag: 'funny',
        }),
        { headers: headers, tags: { name: 'confession:create' } }
      );
      check(postRes, { 'confession create 200/201': (r) => r.status === 200 || r.status === 201 });
    }

  } else if (choice < 0.65) {
    // 3. INTERACTIONS: LIKE & PASS REQUESTS (20%)
    const targetUserId = Math.floor(Math.random() * 1000) + 1;
    const action = Math.random() > 0.3 ? 'send' : 'pass';
    
    let intRes = http.post(
      `${BASE_URL}/api/v1/interaction/${action}/`,
      JSON.stringify({ target_user_id: targetUserId }),
      { headers: headers, tags: { name: `interaction:${action}` } }
    );
    check(intRes, { 'interaction status < 500': (r) => r.status < 500 });

  } else if (choice < 0.80) {
    // 4. USER PROFILE & AUTH SESSION REQUESTS (15%) - Redis Fast-Path
    let meRes = http.get(`${BASE_URL}/api/v1/users/me/`, { headers: headers, tags: { name: 'users:me' } });
    check(meRes, { 'users_me status 200': (r) => r.status === 200 });

    let profRes = http.get(`${BASE_URL}/api/v1/profile/me/`, { headers: headers, tags: { name: 'profile:me' } });
    check(profRes, { 'profile status 200': (r) => r.status === 200 });

  } else if (choice < 0.90) {
    // 5. MATCHES & CONVERSATIONS REQUESTS (10%)
    let matchRes = http.get(`${BASE_URL}/api/v1/matches/`, { headers: headers, tags: { name: 'matches:list' } });
    check(matchRes, { 'matches status 200': (r) => r.status === 200 });

    let convRes = http.get(`${BASE_URL}/api/v1/conversations/`, { headers: headers, tags: { name: 'conversations:list' } });
    check(convRes, { 'conversations status 200': (r) => r.status === 200 });

  } else {
    // 6. PRESENCE / LAST ACTIVE UPDATES (10%) - Redis Geo/Zset
    let activeRes = http.post(
      `${BASE_URL}/api/v1/users/last-active/`,
      JSON.stringify({ lat: 12.9716 + (Math.random() - 0.5) * 0.1, lon: 77.5946 + (Math.random() - 0.5) * 0.1 }),
      { headers: headers, tags: { name: 'users:last_active' } }
    );
    check(activeRes, { 'last_active status 200': (r) => r.status === 200 });
  }

  sleep(Math.random() * 0.5 + 0.5); // 0.5s - 1.0s pace between requests
}
