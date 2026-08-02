import { useState } from 'react';
import NaverMap from '../components/NaverMap.jsx';

const won = (v) => `${(v / 1e4).toLocaleString()}만원`;
const CAT_CLASS = { 정책자금: 'tag', 자체대출: 'tag', 보증서: 'tag' };

// 지표 라벨 → 문장에 쓸 '측면' 명사 (조사 이/가 자동 처리)
const FACTOR_ASPECT = {
  '유동인구': '유동인구', '상권활력': '상권 활력', '동종경쟁': '경쟁 여건',
  '교통': '교통 접근성', '배후인구': '배후 수요', '성장성': '상권 성장성',
  '임대료': '임대료 여건', '주차': '주차 여건', '건물규모': '매장 공간',
  '대형마트': '집객시설 접근성', '학교근접': '학교 접근성', '업종다양성': '업종 다양성',
};

// 지표 라벨 → 사용자가 '중시하는 조건' 표현(1순위 추천 대상 문구용)
const FACTOR_NEED = {
  '유동인구': '많은 유동인구', '상권활력': '활발한 상권 분위기', '동종경쟁': '경쟁이 적은 입지',
  '교통': '편리한 대중교통', '배후인구': '안정적인 배후 수요', '성장성': '상권의 성장 가능성',
  '임대료': '합리적인 임대료', '주차': '주차 편의', '건물규모': '넉넉한 매장 공간',
  '대형마트': '집객시설 인접', '학교근접': '학교 근접 수요', '업종다양성': '다양한 업종이 모인 상권',
};

// 한국어 조사 자동 선택 (받침 유무)
const hasBatchim = (w) => {
  const c = (w || '').charCodeAt((w || '').length - 1);
  return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 !== 0;
};
const josaEun = (w) => (hasBatchim(w) ? '은' : '는');
const josaEul = (w) => (hasBatchim(w) ? '을' : '를');
const josaIga = (w) => (hasBatchim(w) ? '이' : '가');

// 지표값(0~100)을 강도 표현 어간으로 (뒤에 '고'/'다는' 이 자연스럽게 붙음)
const levelStem = (pct) =>
  pct >= 85 ? '매우 우수하' : pct >= 65 ? '우수하' : pct >= 45 ? '무난하' : '다소 아쉽';

// 한 지표를 "측면이 (강도)" 어간 절로 (예: "교통 접근성이 매우 우수하")
function factorClause(r) {
  const a = FACTOR_ASPECT[r.label] || r.label;
  return `${a}${josaIga(a)} ${levelStem(r.pct)}`;
}

// 상위 지표를 줄글로 + 순위(sel)에 따라 1순위 대비 차이를 덧붙임
function describeLocation(loc, ranks, sel) {
  const rs = (loc.reasons || []).filter((r) => FACTOR_ASPECT[r.label]);
  const nm = loc.name;
  if (!rs.length) return `${nm}${josaEun(nm)} 여러 지표가 고르게 균형 잡힌 상권이에요.`;

  // 1) 강점(45% 이상)만 "돋보이는" 목록에 (약점은 아래 비교 문장에서 다룸)
  const strong = rs.filter((r) => r.pct >= 45);
  const clauses = (strong.length ? strong : rs).map(factorClause);
  const joined = clauses
    .map((c, i) => (i === clauses.length - 1 ? `${c}다는 점` : `${c}고`))
    .join(', ');
  let out = `${nm}${josaEun(nm)} ${joined}이 돋보이는 상권이에요.`;

  // 2) 순위별 차별화
  if (sel > 0 && ranks[0]) {
    // 1순위와 공통 지표 중, 이 후보가 가장 크게 뒤지는 지표를 찾아 이유로 제시
    const top = ranks[0];
    const topPct = Object.fromEntries((top.reasons || []).map((r) => [r.label, r.pct]));
    let weak = null, gap = 0;
    rs.forEach((r) => {
      if (topPct[r.label] != null) {
        const g = topPct[r.label] - r.pct;
        if (g > gap) { gap = g; weak = r.label; }
      }
    });
    if (weak && gap >= 5) {
      const a = FACTOR_ASPECT[weak];
      out += ` 다만 1순위 ${top.name}에 비해 ${a}${josaEun(a)} 다소 낮아 ${sel + 1}순위로 추천드려요.`;
    } else {
      out += ` 1순위 ${top.name}과(와) 강점 구성이 비슷해, 유력한 대안이 되는 ${sel + 1}순위 입지예요.`;
    }
  } else {
    const need = FACTOR_NEED[rs[0].label] || rs[0].label;
    out += ` 특히 ${need}${josaEul(need)} 중시하는 창업자에게 잘 맞습니다.`;
  }
  return out;
}

export default function Result({ data, onRestart, step, onNext }) {
  const { location, cost, recommendations } = data;
  const isLocationStep = step === 'location'; // 1단계: 입지만 보여주고 금융 설문으로 넘어가기

  // 후보 순위 목록(좌표·이유 포함). 없으면 1순위(location) 하나만.
  const ranks = (data.candidates && data.candidates.length)
    ? data.candidates
    : (location ? [location] : []);
  const [sel, setSel] = useState(0);           // 현재 선택된 순위(0=1순위)
  const active = ranks[sel] || location;       // 화면에 표시할 입지

  const naverUrl = active
    ? `https://map.naver.com/p/search/${encodeURIComponent(active.naverQuery || active.name)}`
    : null;

  const title = isLocationStep ? 'AI 추천 입지 결과'
    : location ? '맞춤 추천 결과' : '자금·금융상품 추천 결과';

  return (
    <div className="screen">
      <div className="topbar"><span className="logo-badge">KB</span>
        <h2>{title}</h2></div>
      <div className="container">

        {/* 자금측정 모드: 입지·지도 섹션 전체 생략 */}
        {!location ? (
          <div className="result-hero">
            <div className="rank1">설문형 자금 측정</div>
            <h1>💳 맞춤 금융상품</h1>
            <div className="score">
              {data.capital ? `보유 자금 ${(data.capital / 1e4).toLocaleString()}만원 기준` : ''} · 자격에 맞는 상품을 추천했어요
            </div>
          </div>
        ) : (
        <>
        {/* 추천 입지 (선택된 순위) */}
        <div className="result-hero">
          <div className="rank1">AI 추천 입지 {sel + 1}순위</div>
          <h1>📍 {active.name}</h1>
          {active.score != null && (
            <div className="score">종합점수 {active.score}점</div>
          )}
          {/* 지표를 줄글로 풀어 설명 (순위별로 강도·비교가 달라짐) */}
          <p style={{ marginTop: 10, lineHeight: 1.65, color: '#5c554b', fontSize: 15 }}>
            {describeLocation(active, ranks, sel)}
          </p>
          {data._fallback && (
            <div style={{ color: '#c0392b', fontSize: 12, marginTop: 6 }}>
              ⚠️ {data._fallback}
            </div>
          )}
        </div>

        <NaverMap lat={active.lat} lng={active.lng} name={active.name} />
        <a className="map-open" href={naverUrl} target="_blank" rel="noreferrer">
          네이버 지도에서 자세히 보기 →
        </a>

        {/* 순위 전환 버튼 (2·3순위) — 누르면 위 제목·지도가 해당 입지로 바뀜 */}
        {ranks.length > 1 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
            {ranks.map((r, i) => (
              <button
                key={i}
                onClick={() => setSel(i)}
                style={{
                  flex: '1 1 30%', padding: '10px 8px', borderRadius: 10, cursor: 'pointer',
                  textAlign: 'center', transition: 'all .15s',
                  border: i === sel ? '2px solid #d9822b' : '1px solid #e6ded1',
                  background: i === sel ? '#fdf3e7' : '#faf8f4',
                }}
              >
                <div style={{ fontSize: 12, color: i === sel ? '#d9822b' : '#b0a99c', fontWeight: 700 }}>
                  {i + 1}순위
                </div>
                <div style={{ fontSize: 14, fontWeight: i === sel ? 700 : 500, marginTop: 2 }}>
                  {r.name}
                </div>
              </button>
            ))}
          </div>
        )}

        {/* 자금 요약 */}
        {cost && (
          <div className="q-card" style={{ marginTop: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>예상 창업비용</span><b>{won(cost.required)}</b>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#8a8378', marginTop: 6 }}>
              <span>보유 자금</span><span>{won(cost.capital)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#d9822b', fontWeight: 700, marginTop: 6 }}>
              <span>부족 자금</span><span>{won(cost.gap)}</span>
            </div>
          </div>
        )}
        </>
        )}

        {/* 1단계(입지만): 금융 섹션 대신 '설문으로' 안내 + 버튼 */}
        {isLocationStep ? (
          <>
            <div className="q-card" style={{ marginTop: 20, textAlign: 'center', lineHeight: 1.6 }}>
              추천 입지를 확인하셨나요?<br />
              이제 <b>간단한 설문</b>으로 창업자금에 맞는 <b>금융상품</b>을 찾아드릴게요.
            </div>
            <button className="restart" onClick={onNext}>금융상품 추천받기 →</button>
            <button
              className="restart"
              onClick={onRestart}
              style={{ background: 'transparent', color: '#8a8378' }}
            >
              처음으로
            </button>
          </>
        ) : (
          <>
            {/* 금융상품 추천 */}
            <div className="section-title">💳 맞춤 금융상품 Top {recommendations.length}</div>
            {recommendations.map((p) => (
              <div key={p.rank} className="prod-card">
                <div className="prod-head">
                  <div>
                    <span className="prod-rank">{p.rank}순위</span>
                    <div className="prod-name">{p.product_name}</div>
                    <div className="prod-meta">{p.provider}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontWeight: 800, fontSize: 18 }}>{p.match_score}점</div>
                  </div>
                </div>
                <div className="prod-tags">
                  <span className={CAT_CLASS[p.category] || 'tag'}>{p.category}</span>
                  <span className="tag rate">금리 {p.base_rate}%~</span>
                </div>
                <div className="prod-comment">💬 {p.ai_comment}</div>
              </div>
            ))}

            <p style={{ textAlign: 'center', color: '#b0a99c', fontSize: 12 }}>
              ※ 금융상품은 예시(mock)이며 실제 자격·한도는 각 기관 심사로 확정됩니다.
            </p>
            <button className="restart" onClick={onRestart}>처음으로</button>
          </>
        )}
      </div>
    </div>
  );
}
