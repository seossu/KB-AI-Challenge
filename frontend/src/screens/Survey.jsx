import { useState } from 'react';

/* 2025 기준 중위소득(월, 원) — median_income_ratio 자동계산용 */
const MEDIAN = { 1: 2392013, 2: 3932658, 3: 5025353, 4: 6097773 };
const INCOME_MID = { '<3000': 20000000, '3000-5000': 40000000, '5000-8000': 65000000, '8000+': 90000000 };

/* 자금측정(입지추천 없는) 모드에서만 앞에 붙는 자기자본 질문 */
const CAPITAL_Q = {
  key: 'capital', title: '창업에 쓸 수 있는 자기자본은 어느 정도인가요?', type: 'single',
  options: [['30000000', '3천만원 미만'], ['65000000', '3천만~1억'], ['200000000', '1억~3억'], ['400000000', '3억 이상']],
};

/* 금융 설문 (Gemini 수정 반영) */
const FINANCE_QS = [
  { key: 'startup_experience', title: '창업 경험이 어떻게 되시나요?', type: 'single',
    options: [['first', '생애 최초 창업이에요'], ['restart', '과거 창업 후 폐업 경험이 있어요'], ['existing', '현재 다른 사업장을 운영 중이에요']] },
  { key: 'business_stage_years', title: '현재 창업 단계(업력)는?', sub: '창업 경험에 따라 선택지가 조정됩니다', type: 'single',
    options: [['0', '아직 사업자등록 전 (예비창업)'], ['3', '사업자등록 후 3년 미만'], ['7', '3년 이상 ~ 7년 미만'], ['8', '7년 이상']],
    // 동적 제어: first → 예비/3년미만 / existing → 3년미만 이상
    enabledBy: (a) => ({
      first: ['0', '3'], restart: ['0', '3', '7', '8'], existing: ['3', '7', '8'],
    }[a.startup_experience] || ['0', '3', '7', '8']) },
  { key: 'age_group', title: '대표님의 연령대는?', type: 'single',
    options: [['youth', '만 19세 ~ 39세 이하'], ['normal', '만 40세 이상']] },
  { key: 'credit_status', title: '대략적인 신용 수준을 선택해 주세요', sub: '정확한 점수를 몰라도 괜찮습니다', type: 'single',
    options: [['high', '우수 (900점 이상)'], ['medium', '보통 (700~890점)'], ['low', '낮음 또는 잘 모르겠음']] },
  { key: 'existing_loan_amount', title: '다른 금융기관 대출(부채) 잔액이 있으신가요?', type: 'single',
    options: [['0', '없음'], ['30000000', '3천만원 미만'], ['65000000', '3천만~1억'], ['100000000', '1억 이상']] },
  { key: 'loan_purpose', title: '대출 자금은 어디에 쓰실 예정인가요?', sub: '복수 선택 가능', type: 'multi',
    options: [['deposit', '보증금'], ['facility', '인테리어 / 시설·장비'], ['operation', '운영자금 / 재료 구입']] },
  { key: 'house_type', title: '거주 중인 주택의 소유 형태는?', sub: '담보 여력 판단', type: 'single',
    options: [['own', '본인/공동명의 자가'], ['rent', '전세 / 월세 / 기타']] },
  { key: 'special_interest_rate', title: '가구 구성 상태를 선택해 주세요', sub: '복수 선택 가능 · 금리우대', type: 'multi',
    options: [['신혼부부', '신혼부부(혼인 7년 이내)'], ['자녀1', '자녀 1명'], ['다자녀', '자녀 2명 이상'], ['한부모가정', '한부모 가정'], ['none', '해당 없음']] },
  { key: 'household_size', title: '가구원 수는?', sub: '중위소득 계산', type: 'single',
    options: [['1', '1인'], ['2', '2인'], ['3', '3인'], ['4', '4인 이상']] },
  { key: 'income_bracket', title: '연소득 수준은?', sub: '중위소득 대비 비율 자동 계산', type: 'single',
    options: [['<3000', '3천만원 미만'], ['3000-5000', '3천~5천만'], ['5000-8000', '5천~8천만'], ['8000+', '8천만 이상']] },
  { key: 'special_targets', title: '우대 대상에 해당하는 항목이 있으신가요?', sub: '복수 선택 가능', type: 'multi',
    options: [['women', '여성 창업자'], ['disabled', '장애인'], ['veteran', '국가유공자'], ['multicultural', '다문화가정'], ['none', '해당 없음']] },
];

export default function Survey({ financeOnly, phase1, onSubmit }) {
  // financeOnly(자금측정): 자본 질문 + 금융설문 / 대화형 경유: 금융설문만(자본 자동연동)
  const questions = financeOnly ? [CAPITAL_Q, ...FINANCE_QS] : FINANCE_QS;
  const [step, setStep] = useState(0);
  const [ans, setAns] = useState({});
  const q = questions[step];

  const enabled = q.enabledBy ? q.enabledBy(ans) : null;
  const val = ans[q.key];
  const answered = q.type === 'multi' ? Array.isArray(val) && val.length > 0
    : q.type === 'text' ? !!(val && val.trim()) : val != null;

  function choose(optVal) {
    if (q.type === 'multi') {
      let arr = Array.isArray(val) ? [...val] : [];
      if (optVal === 'none') arr = ['none'];
      else { arr = arr.filter((x) => x !== 'none'); arr.includes(optVal) ? (arr = arr.filter((x) => x !== optVal)) : arr.push(optVal); }
      setAns({ ...ans, [q.key]: arr });
    } else {
      setAns({ ...ans, [q.key]: optVal });
    }
  }

  function next() {
    if (step < questions.length - 1) setStep(step + 1);
    else onSubmit(buildProfile(ans, phase1, financeOnly));
  }

  return (
    <div className="screen">
      <div className="topbar"><span className="logo-badge">KB</span><h2>{financeOnly ? '설문형 자금 측정' : '금융 맞춤 설문'}</h2></div>
      <div className="container">
        <div className="progress"><div style={{ width: `${((step + 1) / questions.length) * 100}%` }} /></div>

        {/* Phase1 자본 자동연동 안내 (대화형 경유 시) */}
        {!financeOnly && step === 0 && phase1?.capital && (
          <div className="autofill">✓ 앞서 입력하신 자기자본 <b>{(phase1.capital / 1e8).toFixed(1)}억원</b>이 자동 반영되었습니다. (다시 묻지 않아요)</div>
        )}

        <div className="q-card">
          <p className="q-title">Q{step + 1}. {q.title}</p>
          {q.sub && <p className="q-sub">{q.sub}</p>}

          {q.type === 'text' ? (
            <input className="opt" style={{ display: 'block' }} placeholder={q.placeholder}
              value={val || ''} onChange={(e) => setAns({ ...ans, [q.key]: e.target.value })} />
          ) : (
            <div className={q.options.length > 3 ? 'grid2' : ''}>
              {q.options.map(([ov, label]) => {
                const dis = enabled && !enabled.includes(ov);
                const sel = q.type === 'multi' ? (val || []).includes(ov) : val === ov;
                return (
                  <button key={ov} className={`opt ${q.type === 'multi' ? 'multi' : ''} ${sel ? 'selected' : ''} ${dis ? 'disabled' : ''}`}
                    onClick={() => choose(ov)}>
                    <span className="dot" />{label}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="survey-actions">
          <button className="btn-back" onClick={() => step ? setStep(step - 1) : null} style={{ visibility: step ? 'visible' : 'hidden' }}>← 이전</button>
          <button className="btn-next" disabled={!answered} onClick={next}>
            {step < questions.length - 1 ? '다음 →' : '결과 보기 🔍'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* 설문 응답 → financial_profile (백엔드 스코어링 입력 형태) */
function buildProfile(a, phase1, financeOnly) {
  // 자금측정: 설문에서 받은 자본 / 대화형: phase1 자본 자동연동
  const capital = financeOnly ? Number(a.capital) : (phase1?.capital ?? Number(a.capital) ?? 0);
  const size = Number(MEDIAN[a.household_size] || MEDIAN[1]);
  const income = INCOME_MID[a.income_bracket] || 40000000;
  const median_income_ratio = Math.round((income / 12) / size * 100);
  const special = (a.special_interest_rate || []).filter((x) => x !== 'none');
  const targets = (a.special_targets || []).filter((x) => x !== 'none');

  const profile = {
    financial_profile: {
      business_stage_years: Number(a.business_stage_years ?? 0),
      startup_experience: a.startup_experience || 'first',
      is_youth: a.age_group === 'youth',
      credit_status: a.credit_status || 'medium',
      has_collateral: a.house_type === 'own',
      loan_purpose: a.loan_purpose || [],
      capital_amount: capital,
      existing_loan_amount: Number(a.existing_loan_amount || 0),
      household_size: Number(a.household_size || 1),
      median_income_ratio,
      special_interest_rate: special,
      special_targets: targets,
    },
  };
  // 대화형 경유 시에만 입지조건 전달. 자금측정 모드는 입지 없음(financeOnly 플래그).
  return { location: financeOnly ? null : phase1, financeOnly, ...profile.financial_profile, _raw: profile };
}
