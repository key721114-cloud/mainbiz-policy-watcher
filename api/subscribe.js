// 새 공고 메일 알림 구독 API (Vercel 함수).
//
// 구독자 정보는 Upstash Redis(Vercel Marketplace 연동)의 해시 "subscribers"에
// field=이메일, value=JSON({email, keywords, updated_at}) 형태로 저장한다.
// keywords가 빈 배열이면 "전체 키워드" 구독이다.
// 실제 메일 발송은 여기서 하지 않고, GitHub Actions의 scripts/notify.py가 수집 직후
// 같은 해시를 읽어서 보낸다.
//
// 팀 내부용이라 인증 없이 이메일만으로 조회/등록/해지한다(의도된 결정).
//   GET    /api/subscribe?email=...        현재 구독 조회
//   POST   /api/subscribe {email, keywords} 등록 또는 키워드 변경
//   DELETE /api/subscribe?email=...        구독 해지
//
// 외부 npm 패키지 없이 Upstash REST API를 fetch로 직접 호출한다
// (vercel.json이 installCommand: null이라 의존성 설치 단계가 없음).

const HASH_KEY = "subscribers";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function redisConfig() {
  // Upstash 연동 방식에 따라 변수명이 둘 중 하나로 들어온다.
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  return url && token ? { url, token } : null;
}

async function redis(cfg, command) {
  const r = await fetch(cfg.url, {
    method: "POST",
    headers: { Authorization: "Bearer " + cfg.token, "Content-Type": "application/json" },
    body: JSON.stringify(command),
  });
  const data = await r.json();
  if (!r.ok || data.error) throw new Error(data.error || "redis HTTP " + r.status);
  return data.result;
}

function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  try { return JSON.parse(req.body || "{}"); } catch (e) { return {}; }
}

module.exports = async function handler(req, res) {
  const cfg = redisConfig();
  if (!cfg) {
    res.status(503).json({ error: "구독 저장소가 아직 연결되지 않았습니다." });
    return;
  }

  const body = req.method === "POST" ? readBody(req) : {};
  const email = String(req.query.email || body.email || "").trim().toLowerCase();
  if (!EMAIL_RE.test(email)) {
    res.status(400).json({ error: "이메일 주소 형식이 올바르지 않습니다." });
    return;
  }

  try {
    if (req.method === "GET") {
      const raw = await redis(cfg, ["HGET", HASH_KEY, email]);
      res.status(200).json({ subscribed: !!raw, subscription: raw ? JSON.parse(raw) : null });
      return;
    }

    if (req.method === "POST") {
      const keywords = Array.isArray(body.keywords)
        ? Array.from(new Set(body.keywords.map(function (k) { return String(k).trim(); }).filter(Boolean))).slice(0, 50)
        : [];
      const sub = { email: email, keywords: keywords, updated_at: new Date().toISOString() };
      await redis(cfg, ["HSET", HASH_KEY, email, JSON.stringify(sub)]);
      res.status(200).json({ subscribed: true, subscription: sub });
      return;
    }

    if (req.method === "DELETE") {
      const removed = await redis(cfg, ["HDEL", HASH_KEY, email]);
      res.status(200).json({ subscribed: false, removed: removed === 1 });
      return;
    }

    res.setHeader("Allow", "GET, POST, DELETE");
    res.status(405).json({ error: "지원하지 않는 요청입니다." });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "구독 처리 중 오류가 발생했습니다." });
  }
};
