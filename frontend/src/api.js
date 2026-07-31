/*
 * API 레이어 — 지금은 mock. 실제 백엔드 연결 시 아래 fetch 주석을 사용하세요.
 *
 *  · chatParse : 대화형 입력 파싱  → 실제로는 1팀 main.py / OpenAI (백엔드 /api/chat)
 *  · recommend : 입지+금융 추천     → 실제로는 python run_request + backend /api/recommend
 */

// 데모용 좌표 (실제로는 백엔드가 상권 좌표를 WGS84로 반환).
const GEO = {
  '성수': { name: '성수역', lat: 37.5446, lng: 127.0559 },
  '서강대': { name: '서강대역', lat: 37.5515, lng: 126.9365 },
  '홍대': { name: '홍대입구역', lat: 37.5572, lng: 126.9245 },
  '강남': { name: '강남역', lat: 37.4979, lng: 127.0276 },
  '대치': { name: '대치동 학원가', lat: 37.4996, lng: 127.0567 },
  '역삼': { name: '역삼역', lat: 37.5006, lng: 127.0364 },
  '잠실': { name: '잠실역', lat: 37.5133, lng: 127.1000 },
  '건대': { name: '건대입구역', lat: 37.5405, lng: 127.0703 },
  '신촌': { name: '신촌역', lat: 37.5551, lng: 126.9368 },
  '노원': { name: '노원역', lat: 37.6542, lng: 127.0568 },
  '목동': { name: '목동', lat: 37.5265, lng: 126.8659 },
};

// 매칭 실패 시: 시청으로 떨어지지 않고 '입력 지역 그대로'를 검색 대상으로 사용.
// (좌표는 서울 중심 근사값, 지도 검색·네이버 연결은 입력 지역명으로 정확히 동작)
function pickGeo(region = '') {
  const r = String(region).trim();
  const key = Object.keys(GEO).find((k) => r.includes(k));
  if (key) return GEO[key];
  return { name: r || '서울', lat: 37.5663, lng: 126.9779, approx: true };
}

// 업종 키워드 → 데이터 업종명(파이썬이 인식하는 100개 업종에 매핑되는 대표어)
const BIZ_KEYWORDS = [
  '카페', '커피', '분식', '떡볶이', '편의점', '마트', '슈퍼', '슈퍼마켓', '치킨', '통닭',
  '베이커리', '빵집', '제과', '한식', '중식', '일식', '양식', '음식점', '식당', '레스토랑',
  '고깃집', '고기', '횟집', '술집', '호프', '주점', '포차', '네일', '미용실', '헤어',
  '학원', '교습', '공부방', '피부', '에스테틱', '동물병원', '펫샵', 'pc방', '피시방',
  '노래방', '코인노래방', '스터디카페', '독서실', '문구', '꽃집', '화원', '세탁소', '빨래방',
  '약국', '안경', '헬스', '필라테스', '요가', '태권도', '옷가게', '의류', '편집샵',
];

function detectBusiness(text) {
  const hit = BIZ_KEYWORDS.find((k) => text.toLowerCase().includes(k.toLowerCase()));
  return hit || null;
}

// 서울 25개 자치구 (정확 매칭 우선)
const SEOUL_GU = ['종로구', '중구', '용산구', '성동구', '광진구', '동대문구', '중랑구', '성북구',
  '강북구', '도봉구', '노원구', '은평구', '서대문구', '마포구', '양천구', '강서구', '구로구',
  '금천구', '영등포구', '동작구', '관악구', '서초구', '강남구', '송파구', '강동구'];

// 지역: 자치구 정확매칭 → 동/역/가 순.
function detectRegion(text) {
  const gu = SEOUL_GU.find((g) => text.includes(g));
  if (gu) return gu;
  // 동/역/가/읍/면/리 (뒤에 조사 '에/에서/이/은/는' 등이 와도 지역명만 추출)
  const other = text.match(/([가-힣]{2,4}(?:동|역|가|읍|면|리))/);
  return other ? other[1] : null;
}

/* ── 대화형 파싱 (실제 OpenAI, 백엔드 /api/chat) ──
   history: [{role, content}]  →  {extracted, next_question, ready}
   백엔드 실패 시 로컬 키워드 파서로 폴백. */
export async function chatParse(history) {
  try {
    const r = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: history }),
    });
    const data = await r.json();
    if (data.ok) {
      return {
        extracted: clean(data.extracted),
        next_question: data.next_question,
        ready: data.ready,
      };
    }
  } catch (e) { /* 폴백 */ }
  return localParse(history); // 백엔드 미기동 시
}

// 백엔드 없을 때 쓰는 로컬 키워드 파서(폴백)
function localParse(history) {
  const text = history.filter((m) => m.role === 'user').map((m) => m.content).join(' ');
  const biz = detectBusiness(text);
  const region = detectRegion(text);
  const capMatch = text.match(/(\d+(?:\.\d+)?)\s*억/);
  const capital = capMatch ? Math.round(parseFloat(capMatch[1]) * 1e8) : null;
  const extracted = { business_type: biz, preferred_region: region, capital };
  const missing = [];
  if (!biz) missing.push('업종');
  if (!region) missing.push('지역');
  if (!capital) missing.push('창업 자금');
  const lastUser = [...history].reverse().find((m) => m.role === 'user')?.content || '';
  const wantsProceed = /진행|이대로|바로|없어|괜찮/.test(lastUser);
  const ready = missing.length === 0 && wantsProceed;
  let next_question;
  if (missing.length) next_question = `${missing.join(', ')} 정보를 알려주세요.`;
  else if (!ready) next_question = '필수 정보는 다 받았어요! 이대로 진행할까요?';
  return { extracted, next_question, ready };
}

function clean(obj) {
  const out = {};
  for (const [k, v] of Object.entries(obj || {})) if (v != null) out[k] = v;
  return out;
}

// 백엔드 주소 (개발: localhost:8080). 배포 시 환경변수로 교체.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8080';

/* ── 입지 + 금융 추천 ──
   phase1(입지조건) + profile(금융설문) → 결과
   1) /api/location : 파이썬 실제 입지 추천 (진짜 데이터)
   2) /api/recommend: 금융상품 스코어링 (DB 연결 전이면 mock 폴백) */
export async function recommend(phase1, profile) {
  // 입력 병합: 입지조건 + 금융설문 필드
  const payload = { ...phase1, ...flattenProfile(profile) };

  // 1) 실제 입지 추천 (파이썬)
  let loc;
  try {
    const r = await fetch(`${API_BASE}/api/location`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();
    if (data.ok) {
      const g = data.location;
      loc = {
        result: {
          location: {
            name: g.name, score: g.score,
            lat: g.lat, lng: g.lng, naverQuery: g.naverQuery || g.name,
            reasons: g.reasons || [],
          },
          candidates: data.candidates || [],
          cost: data.cost
            ? { required: data.cost.required, capital: data.cost.capital, gap: data.cost.gap }
            : null,
        },
      };
    } else {
      loc = { error: data.reason || '추천 실패' };
    }
  } catch (e) {
    // 백엔드 미기동 시 mock 폴백 (개발 편의)
    loc = { error: `백엔드 연결 실패 (${e.message}) — mock으로 표시` };
  }

  // 2) 금융상품 추천 (DB 연결 전 → mock)
  const recommendations = await recommendProducts(profile);

  if (loc.error) {
    // 폴백: 입지 mock
    const geo = pickGeo(phase1.preferred_region || '');
    return {
      _fallback: loc.error,
      location: { name: geo.name, score: null, lat: geo.lat, lng: geo.lng,
        naverQuery: geo.name, reasons: [] },
      cost: null,
      recommendations,
    };
  }
  return { ...loc.result, recommendations };
}

/* ── 설문형 자금 측정 ── 입지 없이 자본·설문 → 금융상품만 */
export async function recommendFinanceOnly(profile) {
  const recommendations = await recommendProducts(profile);
  const cap = Number(profile.capital_amount || profile.capital || 0);
  return {
    financeOnly: true,
    location: null,                 // 지도 없음
    capital: cap,
    recommendations,
  };
}

/* 금융상품 — 백엔드 /api/recommend 시도, 실패(=DB 미연결)면 mock */
async function recommendProducts(profile) {
  try {
    const r = await fetch(`${API_BASE}/api/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ financial_profile: flattenProfile(profile) }),
    });
    const data = await r.json();
    if (data?.financial_profile?.recommended_actions?.length) {
      return data.financial_profile.recommended_actions;
    }
  } catch (e) { /* DB 미연결 → mock */ }
  return mockProducts(profile);
}

// Survey 가 만든 profile(중첩 가능) → 평탄화
function flattenProfile(p = {}) {
  return p.financial_profile ? { ...p, ...p.financial_profile } : p;
}

function mockProducts(p = {}) {
  const youth = p.is_youth;
  const list = [
    {
      rank: 1,
      product_name: youth ? '중진공 청년전용창업자금' : '소상공인 일반경영안정자금',
      provider: youth ? '중소벤처기업진흥공단' : '소상공인시장진흥공단',
      category: '정책자금',
      base_rate: youth ? 2.5 : 3.0,
      match_score: 100 + (p.special_interest_rate?.length ? 30 : 0),
      ai_comment: youth
        ? '청년 요건에 해당하여 최저금리 정책자금 1순위로 추천됩니다.'
        : '자격 요건에 가장 부합하는 저금리 정책자금입니다.',
    },
    {
      rank: 2,
      product_name: 'KB 소호(SOHO) 창업대출',
      provider: 'KB국민은행',
      category: '자체대출',
      base_rate: 4.5,
      match_score: 100,
      ai_comment: '부족 자금을 빠른 심사로 보완할 수 있는 KB 대표 창업대출입니다.',
    },
    {
      rank: 3,
      product_name: '지역신용보증재단 보증서 연계 대출',
      provider: '지역신용보증재단',
      category: '보증서',
      base_rate: 3.8,
      match_score: 70 + (!p.has_collateral ? 20 : 0),
      ai_comment: '담보가 부족해도 보증서를 통해 대출이 가능하도록 연계합니다.',
    },
  ];
  return list.sort((a, b) => b.match_score - a.match_score || a.base_rate - b.base_rate);
}
