import http from 'k6/http';
import { check, sleep } from 'k6';

/**
 * k6 Load Test Script for SPYCE Backend (Comprehensive API test suite matching Locust)
 * 
 * Target Server Requirements:
 *   - DISABLE_RATE_LIMITING=True
 *   - USE_TEST_OTP=True, MAGIC_OTP=123456
 *   - REQUIRE_CAPTCHA=False
 *   - FACE_VERIFICATION=False
 * 
 * Execution:
 *   k6 run --environment BASE_URL=https://api01.spycenow.com testing/k6/locust_equivalent.js
 */

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const MAGIC_OTP = __ENV.MAGIC_OTP || '123456';

export const options = {
  stages: [
    { duration: '30s', target: 500 },   // Warm-up ramp
    { duration: '1m',  target: 2000 },  // Steady load 2,000 users
    { duration: '2m',  target: 5000 },  // Peak load 5,000 users
    { duration: '30s', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],     // < 5% errors
    http_req_duration: ['p(95)<1000'],  // 95% of requests below 1s under heavy load
  },
};

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

function authenticateUser(email, deviceId) {
  let headers = getHeaders(deviceId);

  let regRes = http.post(
    `${BASE_URL}/api/v1/auth/register/`,
    JSON.stringify({ email: email, device_id: deviceId, intent: 'signup' }),
    { headers: headers, tags: { name: 'auth:register' } }
  );

  if (regRes.status !== 200) return null;

  let verRes = http.post(
    `${BASE_URL}/api/v1/auth/otp/verify/`,
    JSON.stringify({ email: email, otp: MAGIC_OTP, device_id: deviceId }),
    { headers: headers, tags: { name: 'auth:otp_verify' } }
  );

  if (verRes.status !== 200) return null;

  const verData = verRes.json();
  const token = verData.access;
  const userId = verData.user_id;

  headers = getHeaders(deviceId, token);

  http.post(
    `${BASE_URL}/api/v1/verification/mock-complete/`,
    JSON.stringify({}),
    { headers: headers, tags: { name: 'verification:mock_complete' } }
  );

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

  const username = `usr_${randomHex(10)}`;
  const onboardingPayload = {
    username: username,
    name: `User ${username.substring(0, 6)}`,
    date_of_birth: '1998-05-15',
    gender: genderId,
    sexuality: sexualityId,
    preferred_genders: [genderId],
    bio: 'k6 load test user profile for discovery feed and social.',
    latitude: 12.9716,
    longitude: 77.5946,
  };

  http.patch(
    `${BASE_URL}/api/v1/profile/me/`,
    JSON.stringify(onboardingPayload),
    { headers: headers, tags: { name: 'profile:onboarding_patch' } }
  );

  http.post(
    `${BASE_URL}/api/v1/users/last-active/`,
    JSON.stringify({ lat: 12.9716, lon: 77.5946 }),
    { headers: headers, tags: { name: 'users:last_active_init' } }
  );

  return { token: token, userId: userId, deviceId: deviceId, seenCandidates: [], confessionIds: [] };
}

export default function () {
  const email = generateEmail();
  const deviceId = generateDeviceId();

  const user = authenticateUser(email, deviceId);
  if (!user) {
    sleep(1);
    return;
  }

  const headers = getHeaders(user.deviceId, user.token);

  for (let cycle = 0; cycle < 5; cycle++) {
    const roll = Math.random() * 100;

    if (roll < 8) {
      // Health check
      http.get(`${BASE_URL}/health/`, { tags: { name: 'health' } });
      http.get(`${BASE_URL}/health/live/`, { tags: { name: 'health:live' } });
      http.get(`${BASE_URL}/health/ready/`, { tags: { name: 'health:ready' } });
    } else if (roll < 20) {
      // Feed & Feed AI
      let feedRes = http.get(`${BASE_URL}/api/v2/feed/?count=10`, { headers: headers, tags: { name: 'feed:v2' } });
      if (feedRes.status === 200 && feedRes.json('results')) {
        const items = feedRes.json('results');
        items.forEach((item) => {
          const cid = item.id || item.user_id;
          if (cid) user.seenCandidates.push(cid.toString());
        });
      }
      // Feed AI recalculation path
      http.get(`${BASE_URL}/api/v1/feed/?count=10&refresh=true&currently_online=true`, { headers: headers, tags: { name: 'feed:v1_ai_refresh' } });
    } else if (roll < 35) {
      // Profile & User info
      http.get(`${BASE_URL}/api/v1/users/me/`, { headers: headers, tags: { name: 'users:me' } });
      http.get(`${BASE_URL}/api/v1/profile/me/`, { headers: headers, tags: { name: 'profile:me' } });
      http.get(`${BASE_URL}/api/v1/mood/`, { headers: headers, tags: { name: 'mood:get' } });
      http.get(`${BASE_URL}/api/v1/avatars/`, { headers: headers, tags: { name: 'avatars:list' } });
    } else if (roll < 55) {
      // Like / Pass / Interested / Connection Request
      if (user.seenCandidates.length > 0) {
        const targetId = user.seenCandidates.shift();
        const rand = Math.random();
        if (rand < 0.4) {
          http.post(
            `${BASE_URL}/api/v1/interaction/send/`,
            JSON.stringify({ target_user_id: targetId }),
            { headers: headers, tags: { name: 'interaction:like' } }
          );
        } else if (rand < 0.7) {
          http.post(
            `${BASE_URL}/api/v1/interested/`,
            JSON.stringify({ target_user_id: targetId }),
            { headers: headers, tags: { name: 'interaction:interested' } }
          );
        } else {
          http.post(
            `${BASE_URL}/api/v1/interaction/start_conversation/`,
            JSON.stringify({ target_user_id: targetId, message: 'Hey! Want to chat?' }),
            { headers: headers, tags: { name: 'interaction:start_conversation' } }
          );
        }
      }
      http.get(`${BASE_URL}/api/v1/interaction/received/`, { headers: headers, tags: { name: 'interaction:received' } });
    } else if (roll < 75) {
      // Confession Social (List, Feed, Create, Relate/Like, Repost, Comment, Request)
      let confRes = http.get(`${BASE_URL}/api/v1/social/feed/?limit=15`, { headers: headers, tags: { name: 'confession:feed' } });
      if (confRes.status === 200 && confRes.json('results')) {
        const items = confRes.json('results');
        items.forEach((item) => {
          if (item.id) user.confessionIds.push(item.id.toString());
        });
      }

      if (Math.random() < 0.3) {
        let postRes = http.post(
          `${BASE_URL}/api/v1/social/`,
          JSON.stringify({
            text: `Load test confession ${randomHex(8)} about city thoughts and late night vibe.`,
            mood_tag: 'LONELY',
            language: 'en',
            latitude: 12.9716,
            longitude: 77.5946,
          }),
          { headers: headers, tags: { name: 'confession:create' } }
        );
        if (postRes.status === 201 && postRes.json('id')) {
          user.confessionIds.push(postRes.json('id').toString());
        }
      }

      if (user.confessionIds.length > 0) {
        const cid = user.confessionIds[Math.floor(Math.random() * user.confessionIds.length)];
        http.get(`${BASE_URL}/api/v1/social/${cid}/`, { headers: headers, tags: { name: 'confession:detail' } });
        http.post(`${BASE_URL}/api/v1/social/${cid}/relate/`, JSON.stringify({}), { headers: headers, tags: { name: 'confession:relate' } });
        http.post(`${BASE_URL}/api/v1/social/${cid}/repost/`, JSON.stringify({}), { headers: headers, tags: { name: 'confession:repost' } });
        http.post(
          `${BASE_URL}/api/v1/social/${cid}/comments/`,
          JSON.stringify({ text: 'Load test comment.', is_anonymous: true }),
          { headers: headers, tags: { name: 'confession:comment_create' } }
        );
        http.post(
          `${BASE_URL}/api/v1/social/${cid}/chat-request/`,
          JSON.stringify({ message: 'Hey, your confession hit home. Want to chat?' }),
          { headers: headers, tags: { name: 'confession:chat_request' } }
        );
      }

      http.get(`${BASE_URL}/api/v1/confession-requests/`, { headers: headers, tags: { name: 'confession:requests' } });
      http.get(`${BASE_URL}/api/v1/confession-requests/count/`, { headers: headers, tags: { name: 'confession:request_count' } });
    } else if (roll < 88) {
      // Subscriptions, Wallet, Call, Geo
      http.get(`${BASE_URL}/api/v1/subscriptions/status/`, { headers: headers, tags: { name: 'subscriptions:status' } });
      http.get(`${BASE_URL}/api/v1/call-time/wallet/`, { headers: headers, tags: { name: 'call:wallet' } });
      http.get(`${BASE_URL}/api/v1/geo/cities/?q=Ban`, { headers: headers, tags: { name: 'geo:cities' } });
    } else {
      // Presence & WS Ticket
      http.post(
        `${BASE_URL}/api/v1/users/last-active/`,
        JSON.stringify({ lat: 12.9716, lon: 77.5946 }),
        { headers: headers, tags: { name: 'users:last_active' } }
      );
      http.post(
        `${BASE_URL}/api/v1/auth/ws-ticket/`,
        JSON.stringify({}),
        { headers: headers, tags: { name: 'auth:ws_ticket' } }
      );
    }

    sleep(Math.random() * 1.5 + 0.5);
  }
}
