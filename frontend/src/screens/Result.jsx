import { useState } from 'react';
import NaverMap from '../components/NaverMap.jsx';

const won = (v) => {
  const man = Math.round(v / 10000); // 만원 단위로 반올림
  if (man >= 10000) {
    const uk = Math.floor(man / 10000); // '억' 단위 추출
    const remain = man % 10000;         // 남은 '만' 단위 추출
    return remain > 0 ? `${uk}억 ${remain.toLocaleString()}만원` : `${uk}억원`;
  }
  return `${man.toLocaleString()}만원`;
};
const CAT_CLASS = { 정책자금: 'tag', 자체대출: 'tag', 보증서: 'tag' };

const COST_LABELS = {
  '보증금': '상권 임대 시세로 추정',
  '권리금': '업종별 평균 권리금',
  '인테리어': '평수 × 업종별 평당 단가',
  '설비비': '업종·창업형태별 기본 설비',
  '가맹비': '프랜차이즈 가입·교육·보증 비용',
  '운영자금': '예상 월세 × 초기 운영 개월',
};

function CostBreakdown({ cost }) {
  const entries = Object.entries(cost.breakdown || {});
  if (!entries.length) return null;

  const basis = cost.basis || {};
  const location = [basis.sigungu, basis.dong].filter(Boolean).join(' ');

  return (
    <details className="cost-details" open>
      <summary>창업비용 계산 결과 자세히 보기</summary>
      <div className="cost-basis">
        {[basis.induty, basis.business_type, basis.pyeong && `${basis.pyeong}평`, location]
          .filter(Boolean)
          .map((item) => <span key={item}>{item}</span>)}
      </div>
      <div className="cost-formula">예상 창업비용 = 시설·초기투자비 + 초기 운영자금</div>
      <div className="cost-breakdown-list">
        {entries.map(([name, amount]) => (
          <div className="cost-breakdown-row" key={name}>
            <div>
              <strong>{name}</strong>
              <small>{COST_LABELS[name]}</small>
            </div>
            <b>{won(amount)}</b>
          </div>
        ))}
      </div>
      <div className="cost-total-row">
        <span>합계</span><strong>{won(cost.required)}</strong>
      </div>
      {basis.monthly_rent != null && (
        <p className="cost-note">
          월세는 상권 임대 시세를 바탕으로 약 {won(basis.monthly_rent)}으로 추정했고,
          운영자금은 초기 {basis.opex_months || 3}개월분으로 계산했습니다.
        </p>
      )}
      <p className="cost-disclaimer">※ 공개 통계와 임대 시세를 활용한 추정치로, 실제 계약·시공·브랜드 견적에 따라 달라질 수 있습니다.</p>
    </details>
  );
}

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

// 💡 [추가] 세부 점수를 시각화하는 미니 프로그레스 바 컴포넌트
function DetailBar({ label, score, max }) {
  if (score === undefined || score === null) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', fontSize: '12px', color: '#999', margin: '4px 0' }}>
        <span style={{ width: '70px' }}>{label}</span>
        <span>데이터 없음 (제외)</span>
      </div>
    );
  }

  const percentage = (score / max) * 100;

  return (
    <div style={{ display: 'flex', alignItems: 'center', fontSize: '12px', margin: '4px 0' }}>
      <span style={{ width: '70px', fontWeight: '600', color: '#5c554b' }}>{label}</span>
      <div style={{ flex: 1, background: '#e6ded1', height: '6px', borderRadius: '3px', margin: '0 8px', overflow: 'hidden' }}>
        <div style={{ width: `${percentage}%`, background: '#d9822b', height: '100%', borderRadius: '3px', transition: 'width 0.5s ease-in-out' }}></div>
      </div>
      <span style={{ width: '35px', textAlign: 'right', color: '#8a8378' }}>{score}/{max}</span>
    </div>
  );
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
          {data.isFallback && (
            <div className="location-fallback-notice">
              💡 해당 업종의 세부 분석 데이터가 부족하여, 상권 종합 지표가 가장 우수한 범용적인 입지를 추천해 드립니다.
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
            <CostBreakdown cost={cost} />
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
            <button className="btn-finance-next" onClick={onNext}>
              금융상품 추천받기 →
            </button>

            <button className="btn-return-home" onClick={onRestart}>
              처음으로 돌아가기
            </button>
          </>
        ) : (
          <>
            {/* 💡 [수정] 금융상품 추천 렌더링 (프로그레스 바 + AI 코멘트 강조) */}
            <div className="section-title">💳 맞춤 금융상품 Top {recommendations?.length || 0}</div>

            {recommendations && recommendations.length > 0 ? (
              recommendations.map((p) => (
                <div key={p.rank} className="prod-card" style={{ padding: '20px', marginBottom: '15px', borderRadius: '12px', background: '#fff', border: '1px solid #e6ded1' }}>

                  {/* 상단: 순위, 이름, 총점 */}
                  <div className="prod-head" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                    <div>
                      <span className="prod-rank" style={{ color: '#d9822b', fontWeight: 'bold', fontSize: '13px' }}>{p.rank}순위</span>
                      <div className="prod-name" style={{ fontSize: '18px', fontWeight: 'bold', margin: '4px 0' }}>{p.product_name}</div>
                      <div className="prod-meta" style={{ fontSize: '13px', color: '#8a8378' }}>{p.provider}</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontWeight: 800, fontSize: '24px', color: '#d9822b' }}>
                        {p.match_score}<span style={{fontSize: '14px', color: '#8a8378', fontWeight: 500}}>점</span>
                      </div>
                    </div>
                  </div>

                  {/* 태그 영역 */}
                  <div className="prod-tags" style={{ marginBottom: '15px' }}>
                    <span className={CAT_CLASS[p.category] || 'tag'}>{p.category}</span>
                    <span className="tag rate">금리 {p.base_rate !== null ? `${p.base_rate}%~` : '미정'}</span>
                  </div>

                  {/* AI 코멘트 강조 박스 */}
                  <div style={{ background: '#fdf3e7', padding: '12px', borderRadius: '8px', marginBottom: '15px', fontSize: '14px', color: '#5c554b', lineHeight: 1.5 }}>
                    <strong style={{ color: '#d9822b', display: 'block', marginBottom: '4px' }}>💡 AI 분석 코멘트</strong>
                    {p.ai_comment}
                  </div>

                  {/* 세부 점수 2단 그리드 (score_detail이 있을 때만 렌더링) */}
                  {p.score_detail && (
                    <div style={{ borderTop: '1px dashed #e6ded1', paddingTop: '12px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 15px' }}>
                      <DetailBar label="창업조건" score={p.score_detail.startup} max={25} />
                      <DetailBar label="신용/담보" score={p.score_detail.credit_collateral} max={20} />
                      <DetailBar label="자금용도" score={p.score_detail.purpose} max={20} />
                      <DetailBar label="한도충족" score={p.score_detail.coverage} max={15} />
                      <DetailBar label="금리경쟁" score={p.score_detail.rate} max={15} />
                      <DetailBar label="우대조건" score={p.score_detail.benefit} max={5} />
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div style={{ textAlign: 'center', padding: '30px', color: '#8a8378' }}>조건에 맞는 상품이 없습니다.</div>
            )}

            <p style={{ textAlign: 'center', color: '#b0a99c', fontSize: 12, marginTop: '20px' }}>
              ※ 금융상품은 예시(mock)이며 실제 자격·한도는 각 기관 심사로 확정됩니다.
            </p>
            <button className="restart" onClick={onRestart}>처음으로</button>
          </>
        )}
      </div>
    </div>
  );
}
