import NaverMap from '../components/NaverMap.jsx';

const won = (v) => `${(v / 1e4).toLocaleString()}만원`;
const CAT_CLASS = { 정책자금: 'tag', 자체대출: 'tag', 보증서: 'tag' };

export default function Result({ data, onRestart }) {
  const { location, cost, recommendations } = data;
  const naverUrl = location
    ? `https://map.naver.com/p/search/${encodeURIComponent(location.naverQuery || location.name)}`
    : null;

  return (
    <div className="screen">
      <div className="topbar"><span className="logo-badge">KB</span>
        <h2>{location ? '맞춤 추천 결과' : '자금·금융상품 추천 결과'}</h2></div>
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
        {/* 추천 입지 */}
        <div className="result-hero">
          <div className="rank1">AI 추천 입지 1순위</div>
          <h1>📍 {location.name}</h1>
          <div className="score">
            {location.score != null && `종합점수 ${location.score}점`}
            {location.reasons?.length > 0 &&
              ` · ${location.reasons.map((r) => `${r.label} ${r.pct}%`).join(' · ')}`}
          </div>
          {data._fallback && (
            <div style={{ color: '#c0392b', fontSize: 12, marginTop: 6 }}>
              ⚠️ {data._fallback}
            </div>
          )}
        </div>

        <NaverMap lat={location.lat} lng={location.lng} name={location.name} />
        <a className="map-open" href={naverUrl} target="_blank" rel="noreferrer">
          네이버 지도에서 자세히 보기 →
        </a>

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
      </div>
    </div>
  );
}
