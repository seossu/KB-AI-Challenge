import { useState } from 'react';
import Landing from './screens/Landing.jsx';
import Chat from './screens/Chat.jsx';
import Survey from './screens/Survey.jsx';
import Result from './screens/Result.jsx';
import { recommendLocation, recommendFinance, recommendFinanceOnly } from './api.js';

/*
 * 화면 흐름 (상태 기계):
 *   landing ─[대화형 입지추천]─▶ chat ─(종료)─▶ locresult(지도) ─(다음)─▶ survey(금융) ─▶ result(금융상품)
 *           └[설문형 자금측정]──────────────────────────────────▶ survey(자본+금융) ─▶ result(금융만)
 */
export default function App() {
  const [screen, setScreen] = useState('landing');
  const [entry, setEntry] = useState(null);      // 'chat' | 'finance'
  const [phase1, setPhase1] = useState(null);    // 입지 조건(대화형 결과)
  const [locResult, setLocResult] = useState(null); // 1단계 입지 추천 결과(지도/비용)
  const [result, setResult] = useState(null);    // 최종 결과(금융상품 포함)
  const [loading, setLoading] = useState(false); // false | 'location' | 'finance'

  function selectEntry(mode) {
    setEntry(mode);
    setScreen(mode === 'chat' ? 'chat' : 'survey');
  }

  // 대화형 종료 → 먼저 '입지 추천'만 계산해서 지도 결과부터 보여준다
  async function onChatFinish(extracted) {
    setPhase1(extracted);
    setLoading('location');
    const loc = await recommendLocation(extracted);
    setLocResult(loc);
    setLoading(false);
    setScreen('locresult');
  }

  // 입지결과 화면에서 '다음' → 금융 설문으로
  function goSurvey() {
    setScreen('survey');
  }

  // 설문 완료 → (대화형)입지결과에 금융상품 이어붙이기 / (자금측정)금융만
  async function onSurveySubmit(payload) {
    setLoading('finance');
    if (payload.financeOnly) {
      // 자금측정 모드: 입지추천 없이 금융상품만
      setResult(await recommendFinanceOnly(payload));
    } else {
      // 대화형 모드: 이미 계산한 입지결과 + 새로 뽑은 금융상품
      const { recommendations } = await recommendFinance(payload);
      setResult({ ...(locResult || {}), recommendations });
    }
    setLoading(false);
    setScreen('result');
  }

  function reset() {
    setScreen('landing'); setEntry(null);
    setPhase1(null); setLocResult(null); setResult(null);
  }

  if (loading) {
    return (
      <div className="screen landing">
        <div style={{ fontSize: 40 }}>{loading === 'location' ? '📍' : '💳'}</div>
        <div className="tagline">
          {loading === 'location'
            ? 'AI가 최적 입지를 분석하고 있어요…'
            : '자격에 맞는 금융상품을 찾고 있어요…'}
        </div>
      </div>
    );
  }

  return (
    <>
      {screen === 'landing' && <Landing onSelect={selectEntry} />}
      {screen === 'chat' && <Chat onFinish={onChatFinish} />}
      {screen === 'locresult' && (
        <Result data={locResult} step="location" onNext={goSurvey} onRestart={reset} />
      )}
      {screen === 'survey' && (
        <Survey
          financeOnly={entry === 'finance'}
          phase1={phase1}
          onSubmit={onSurveySubmit}
        />
      )}
      {screen === 'result' && <Result data={result} onRestart={reset} />}
    </>
  );
}
