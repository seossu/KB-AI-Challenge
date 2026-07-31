const express = require('express');
const router = express.Router();
const { OpenAI } = require('openai');

let openai = null;
if (process.env.OPENAI_API_KEY) {
  openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
}

// 1팀 main.py 의 시스템 프롬프트를 그대로 사용 (대화 → 9개 필드 추출)
const SYSTEM_PROMPT = `
당신은 창업 입지 컨설팅 에이전트입니다.
사용자의 입력에서 상권 분석에 필요한 정보를 추출하세요.

[행동 지침]
1. 정보 누적: 이전 대화에서 추출한 정보는 유지·업데이트하고, 없는 정보는 null.
2. 질문 규칙:
   - 필수 5가지(purpose, business_type, capital, preferred_region, store_size_pyeong) 중 null이 있으면 그것부터 물어보세요.
   - 필수가 다 차면 "이대로 진행할까요? 아니면 더 입력하시겠어요? (ex. 타겟층, 우선순위, 주차, 대중교통)"처럼 진행 여부를 물으세요.
3. 종료(ready_to_proceed=true) — 매우 중요:
   - 사용자의 마지막 메시지에 "이대로", "진행", "추천해줘", "바로", "없어", "괜찮아", "그렇게 해" 같은 진행 의사가 있으면
     (필수 5가지가 채워져 있는 한) 반드시 ready_to_proceed=true, next_question=null 로 설정하세요.
   - 이 경우 target_customer·주차 같은 선택정보를 절대 다시 묻지 마세요.
   - 진행 의사가 없고 정보도 다 안 찼으면 false.

[중요] business_type 은 어떤 표현이든 업종으로 인식하세요. 예: "마트","무인아이스크림","밀키트가게","코인노래방" 모두 업종입니다. 절대 "업종을 알려주세요"를 반복하지 마세요(이미 말했다면).

[추출 키 · 타입 규칙 - 엄수]
  purpose(문자열) / business_type(문자열) / capital(순수 정수, 예 50000000) /
  preferred_region(문자열, 예 "중구") / store_size_pyeong(숫자, 예 20.0) /
  target_customer(문자열|null) /
  priority(배열|null, [foot_traffic, low_rent, low_competition, transit, residential_base] 중) /
  parking(boolean|null) / public_transport(boolean|null)

[출력 JSON - 이 구조 엄수]
{
  "extracted_data": {
    "purpose": null, "business_type": null, "capital": null,
    "preferred_region": null, "store_size_pyeong": null,
    "target_customer": null, "priority": null, "parking": null, "public_transport": null
  },
  "next_question": "질문 또는 null",
  "ready_to_proceed": false
}
`;

/*
 * POST /api/chat
 * body: { messages: [{role, content}, ...] }  (사용자·AI 누적 대화)
 * → { extracted, next_question, ready }
 */
router.post('/', async (req, res) => {
  const messages = req.body.messages || [];
  if (!openai) {
    return res.status(503).json({ ok: false, reason: 'OPENAI_API_KEY 미설정' });
  }
  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      messages: [{ role: 'system', content: SYSTEM_PROMPT }, ...messages],
      response_format: { type: 'json_object' },
      temperature: 0.2,
    });
    const parsed = JSON.parse(completion.choices[0].message.content);
    const d = parsed.extracted_data || {};

    // ── 종료 판정은 코드가 확정 (LLM 판단에만 의존하지 않음) ──
    const required = ['business_type', 'preferred_region', 'capital', 'store_size_pyeong'];
    const allPresent = required.every((k) => d[k] != null && d[k] !== '');
    const lastUser = [...messages].reverse().find((m) => m.role === 'user')?.content || '';
    const proceedIntent = /이대로|진행|추천\s*(해|해줘|시작)|바로|없어|없습니다|괜찮|그렇게|시작/.test(lastUser);
    const ready = allPresent && (!!parsed.ready_to_proceed || proceedIntent);

    return res.status(200).json({
      ok: true,
      extracted: {
        purpose: d.purpose ?? '창업',
        business_type: d.business_type ?? null,
        capital: d.capital ?? null,
        preferred_region: d.preferred_region ?? null,
        store_size_pyeong: d.store_size_pyeong ?? null,
        target_customer: d.target_customer ?? null,
        priority: d.priority ?? null,
        parking: d.parking ?? null,
        public_transport: d.public_transport ?? null,
      },
      next_question: ready ? null : (parsed.next_question ?? null),
      ready,
    });
  } catch (e) {
    return res.status(500).json({ ok: false, reason: `GPT 호출 실패: ${e.message}` });
  }
});

module.exports = router;
