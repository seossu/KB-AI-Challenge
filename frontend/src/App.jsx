import { useState } from 'react';
import Landing from './screens/Landing.jsx';
import Chat from './screens/Chat.jsx';
import Survey from './screens/Survey.jsx';
import Result from './screens/Result.jsx';
import { recommend, recommendFinanceOnly } from './api.js';

/*
 * 화면 흐름 (상태 기계):
 *   landing ──[대화형 입지추천]──▶ chat ──(종료)──▶ survey(금융) ──▶ result(지도+금융)
 *           └─[설문형 자금측정]──────────────────▶ survey(자본+금융) ──▶ result(금융만)
 */
export default function App() {
  const [screen, setScreen] = useState('landing');
  const [entry, setEntry] = useState(null);      // 'chat' | 'finance'
  const [phase1, setPhase1] = useState(null);    // 입지 조건(대화형 결과)
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  function selectEntry(mode) {
    setEntry(mode);
    setScreen(mode === 'chat' ? 'chat' : 'survey');
  }

  // 대화형 종료 → 무조건 설문 페이지로
  function onChatFinish(extracted) {
    setPhase1(extracted);
    setScreen('survey');
  }

  // 설문 완료 → 추천 계산 → 결과
  async function onSurveySubmit(payload) {
    setLoading(true);
    if (payload.financeOnly) {
      // 자금측정 모드: 입지추천 없이 금융상품만
      const data = await recommendFinanceOnly(payload);
      setResult(data);
    } else {
      const loc = payload.location || phase1 || {};
      const data = await recommend(loc, payload);
      setResult(data);
    }
    setLoading(false);
    setScreen('result');
  }

  function reset() {
    setScreen('landing'); setEntry(null); setPhase1(null); setResult(null);
  }

  if (loading) {
    return (
      <div className="screen landing">
        <div style={{ fontSize: 40 }}>⚙️</div>
        <div className="tagline">AI가 입지와 금융상품을 분석하고 있어요…</div>
      </div>
    );
  }

  return (
    <>
      {screen === 'landing' && <Landing onSelect={selectEntry} />}
      {screen === 'chat' && <Chat onFinish={onChatFinish} />}
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
