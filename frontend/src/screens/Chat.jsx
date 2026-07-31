import { useState, useRef, useEffect } from 'react';
import { chatParse } from '../api.js';

const GREETING = {
  role: 'assistant',
  content: '안녕하세요! 창업 입지 컨설팅 AI입니다. 🏙️\n어떤 업종을, 어느 지역에, 얼마의 자금으로 창업하실 계획인가요?\n예) "성수동에 2억으로 카페 차리려고요"',
};

export default function Chat({ onFinish }) {
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState('');
  const [extracted, setExtracted] = useState({});
  const [canProceed, setCanProceed] = useState(false);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  async function send(forceProceed = false) {
    const text = forceProceed ? '이대로 진행할게요' : input.trim();
    if (!text || busy) return;
    const history = [...messages, { role: 'user', content: text }];
    setMessages(history);
    setInput('');
    setBusy(true);

    const { extracted: ex, next_question, ready } = await chatParse(history);
    const merged = { ...extracted, ...clean(ex) };
    setExtracted(merged);

    // "이대로 진행" 버튼을 눌렀고 필수정보가 있으면 즉시 종료
    const proceedNow = forceProceed && merged.business_type && merged.preferred_region && merged.capital;

    if (ready || proceedNow) {
      setMessages((m) => [...m, { role: 'assistant', content: '네, 취합된 정보로 맞춤형 입지 추천을 시작합니다. ⚙️' }]);
      setBusy(false);
      setTimeout(() => onFinish(merged), 900); // → 설문 페이지로 자동 이동
      return;
    }
    setMessages((m) => [...m, { role: 'assistant', content: next_question || '조금 더 알려주세요.' }]);
    setCanProceed(!!(merged.business_type && merged.preferred_region && merged.capital));
    setBusy(false);
  }

  return (
    <div className="screen chat-wrap">
      <div className="topbar">
        <span className="logo-badge">KB</span>
        <h2>대화형 입지 추천</h2>
      </div>

      <div className="chat-scroll" ref={scrollRef}>
        <div className="chat-inner">
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <div className="avatar">{m.role === 'assistant' ? 'AI' : '나'}</div>
              <div className="bubble">{m.content}</div>
            </div>
          ))}
          {busy && (
            <div className="msg assistant">
              <div className="avatar">AI</div>
              <div className="bubble">…</div>
            </div>
          )}
        </div>
      </div>

      <div className="chat-input-bar">
        <div className="chat-input">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              // 한글(IME) 조합 중 엔터는 무시 → 마지막 글자 중복 방지
              if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="메시지를 입력하세요…"
          />
          <button onClick={() => send()} disabled={!input.trim() || busy}>↑</button>
        </div>
        {canProceed && (
          <button className="chat-proceed" onClick={() => send(true)}>
            이대로 추천 진행하기 →
          </button>
        )}
      </div>
    </div>
  );
}

function clean(obj) {
  const out = {};
  for (const [k, v] of Object.entries(obj)) if (v != null) out[k] = v;
  return out;
}
