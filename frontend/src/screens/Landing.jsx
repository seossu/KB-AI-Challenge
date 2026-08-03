export default function Landing({ onSelect }) {
  return (
    <div className="screen landing">
      <div className="logo">
        <span className="kb">KB</span> 창업 컨설팅
      </div>
      <div className="tagline">입지부터 금융까지, AI가 한 번에 설계합니다</div>

      <div className="buttons">
        <button className="btn-primary" onClick={() => onSelect('chat')}>
          대화형 입지 추천
          <small>AI와 대화 → 입지 + 금융 추천</small>
        </button>
        <button className="btn-outline" onClick={() => onSelect('finance')}>
          설문형 자금 측정
          <small>설문만 → 금융상품 추천</small>
        </button>
      </div>
    </div>
  );
}
