const express = require('express');
const router = express.Router();
const { createClient } = require('@supabase/supabase-js');
const { OpenAI } = require('openai');

// 지연 초기화: 키가 없어도 서버가 죽지 않게
let supabase = null;
let openai = null;
if (process.env.SUPABASE_URL && process.env.SUPABASE_ANON_KEY) {
  supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY);
}
if (process.env.OPENAI_API_KEY) {
  openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
}

// 신용등급 매핑 헬퍼 (낮은 숫자가 고신용)
const CREDIT_LEVEL = { high: 3, medium: 2, low: 1 };

router.post('/', async (req, res) => {
  try {
    if (!supabase) {
      return res.status(503).json({
        ok: false,
        reason: '금융상품 DB(Supabase)가 아직 연결되지 않았습니다. (.env 설정 필요)',
      });
    }
    const profile = req.body.financial_profile;

    // ==========================================
    // [1단계] 필수 자격 필터링 (Hard Filter)
    // ==========================================
    let query = supabase.from('financial_products').select('*');

    // 1. 연령 및 업력
    const userAge = profile.is_youth ? 35 : 45; // 예시용 연령 산출
    query = query.gte('req_age_max', userAge);
    query = query.gte('req_max_biz_years', profile.business_stage_years);

    // 2. 자금 용도 (시설자금, 운전자금 등)
    const validPurposes = [...(profile.loan_purpose || []), 'all'];
    query = query.in('req_loan_purpose', validPurposes);

    // 3. 담보 여력 (자가/전월세)
    if (!profile.has_collateral) {
      query = query.eq('needs_collateral', false); // 담보 없으면 무담보(false)만
    }

    // 4. 특화 대상 철벽 방어 (Hard Filter)
    const allSpecialTargets = ['women', 'disabled', 'veteran', 'multicultural'];
    const userTargets = profile.special_targets || [];

    allSpecialTargets.forEach(target => {
      if (!userTargets.includes(target)) {
        query = query.neq('target_special', target);
      }
    });

    const { data: filteredProducts, error } = await query;
    if (error) throw error;

    if (!filteredProducts || filteredProducts.length === 0) {
      return res.status(200).json({
        financial_profile: { recommended_actions: [] },
        message: '조건에 맞는 상품이 없습니다.'
      });
    }

    // ==========================================
    // [2단계] 상태값 추출 (금리 정규화를 위한 Min/Max 계산)
    // ==========================================
    let minRate = Infinity;
    let maxRate = -Infinity;

    filteredProducts.forEach(p => {
      if (p.base_rate !== null) {
        minRate = Math.min(minRate, p.base_rate);
        maxRate = Math.max(maxRate, p.base_rate);
      }
    });
    if (minRate === Infinity) { minRate = null; maxRate = null; }

    // ==========================================
    // [3단계] 가중치 기반 적합도 스코어링 (XAI)
    // ==========================================
    const scoredProducts = filteredProducts.map(product => {
      const criteria = [];

      // 1. 창업자 조건 적합도 (25점)
      let startupScore = 0.6; // 기본 신청 가능하면 0.6
      if (product.req_startup_exp === profile.startup_experience) startupScore = 1.0;
      else if (product.target_special === 'youth' && profile.is_youth) startupScore = 1.0;
      criteria.push({ name: 'startup', value: startupScore, weight: 25 });

      // 2. 신용·담보 적합도 (20점)
      let creditScore = 0.8;
      const uCredit = CREDIT_LEVEL[profile.credit_status] || 2;
      const pCredit = CREDIT_LEVEL[product.req_credit_min] || 1;
      if (uCredit > pCredit) creditScore = 1.0;      // 여유 있게 충족
      else if (uCredit === pCredit) creditScore = 0.8; // 딱 맞게 충족
      criteria.push({ name: 'credit_collateral', value: creditScore, weight: 20 });

      // 3. 자금 용도 적합도 (20점)
      let purposeScore = 1.0;
      // (Hard Filter를 뚫고 왔으므로 기본 1.0으로 부여하되, 다중 용도 일치율에 따라 고도화 가능)
      criteria.push({ name: 'purpose', value: purposeScore, weight: 20 });

      // 4. 필요금액 충족도 (15점)
      let coverageVal = null;
      // 프론트나 이전 로직에서 funding_gap(부족 자금)을 계산해서 넘겼다고 가정
      const fundingGap = profile.funding_gap || profile.capital_amount;
      if (fundingGap && product.max_loan_amount) {
        coverageVal = Math.min(product.max_loan_amount / fundingGap, 1.0);
      }
      criteria.push({ name: 'coverage', value: coverageVal, weight: 15 });

      // 5. 금리 경쟁력 (15점)
      let rateVal = null;
      if (product.base_rate !== null && maxRate !== null && minRate !== null) {
        if (maxRate === minRate) {
          rateVal = null; // 단일 상품이거나 모두 금리가 같으면 계산 제외 (재정규화)
        } else {
          rateVal = (maxRate - product.base_rate) / (maxRate - minRate); // 낮을수록 1에 가까움
        }
      }
      criteria.push({ name: 'rate', value: rateVal, weight: 15 });

      // 6. 우대조건 적합도 (5점)
      let benefitScore = 0.2; // 기본
      if (userTargets.includes(product.target_special)) benefitScore = 1.0; // 특화대상 완벽 일치
      else if (profile.median_income_ratio <= 80 && product.category === '보증서') benefitScore = 0.8;
      else if (profile.special_interest_rate?.length > 0) benefitScore = 0.6;
      criteria.push({ name: 'benefit', value: benefitScore, weight: 5 });

      // --- 최종 점수 계산 (결측치 재정규화) ---
      let weightedSum = 0;
      let usedWeight = 0;
      const scoreDetail = {};

      criteria.forEach(c => {
        if (c.value !== null) {
          const itemScore = c.value * c.weight;
          weightedSum += itemScore;
          usedWeight += c.weight;
          scoreDetail[c.name] = Math.round(itemScore); // 프론트 차트용
        }
      });

      const finalMatchScore = usedWeight === 0 ? 0 : Math.round((weightedSum / usedWeight) * 100);

      return {
        ...product,
        match_score: finalMatchScore,
        score_detail: scoreDetail
      };
    });

    // ==========================================
    // [4단계] 정렬 및 Top 3 추출
    // ==========================================
    const top3Products = scoredProducts
      .sort((a, b) => {
        if (b.match_score !== a.match_score) return b.match_score - a.match_score; // 1순위: 적합도 점수
        const rateA = a.base_rate !== null ? a.base_rate : 99;
        const rateB = b.base_rate !== null ? b.base_rate : 99;
        return rateA - rateB; // 2순위: 동점이면 낮은 금리
      })
      .slice(0, 3);

    // ==========================================
    // [5단계] OpenAI AI 코멘트 생성 (점수 디테일 반영)
    // ==========================================
    // 💡 AI에게 세부 점수(score_detail)를 함께 넘겨주어 훨씬 더 논리적이고 설명 가능한 코멘트를 작성하게 유도합니다.
    const prompt = `
      당신은 소상공인 창업자를 위한 전문 금융 컨설턴트입니다.
      아래 [고객 정보]와 시스템이 계산한 [추천 상품별 적합도 세부 점수]를 바탕으로, 추천 상품 Top 3에 대해 각각 1~2줄의 명확한 추천 근거를 작성해주세요.

      [고객 정보]
      - 창업 경험: ${profile.startup_experience === 'first' ? '생애최초' : '재창업/확장'}
      - 청년 여부: ${profile.is_youth ? '청년(만 39세 이하)' : '해당 없음'}
      - 신용 상태: ${profile.credit_status}
      - 소득 상태: 중위소득 ${profile.median_income_ratio}%

      [추천 상품 Top 3 및 세부 점수]
      1순위: ${top3Products[0]?.product_name} (총점: ${top3Products[0]?.match_score}점)
      - 강점 요인: ${JSON.stringify(top3Products[0]?.score_detail)}
      2순위: ${top3Products[1]?.product_name} (총점: ${top3Products[1]?.match_score}점)
      - 강점 요인: ${JSON.stringify(top3Products[1]?.score_detail)}
      3순위: ${top3Products[2]?.product_name} (총점: ${top3Products[2]?.match_score}점)
      - 강점 요인: ${JSON.stringify(top3Products[2]?.score_detail)}

      *참고: 세부 점수 Key값 의미 (startup: 창업자조건, credit_collateral: 신용담보, purpose: 자금용도, coverage: 한도충족도, rate: 금리경쟁력, benefit: 우대조건)

      반드시 아래 JSON 형식으로만 응답을 반환해주세요. 환각을 방지하고, 점수가 높은 항목(강점 요인)을 언급하며 논리적으로 작성하세요.
      {
        "comments": [
          "1순위 상품 선정 이유",
          "2순위 상품 선정 이유",
          "3순위 상품 선정 이유"
        ]
      }
    `;

    let aiComments = [];
    if (top3Products.length > 0) {
      const gptResponse = await openai.chat.completions.create({
        model: "gpt-4o-mini",
        messages: [{ role: "user", content: prompt }],
        response_format: { type: "json_object" }
      });
      aiComments = JSON.parse(gptResponse.choices[0].message.content).comments;
    }

    // ==========================================
    // [최종 병합] 프론트엔드로 응답
    // ==========================================
    const finalResult = top3Products.map((item, index) => ({
      rank: index + 1,
      product_name: item.product_name,
      provider: item.provider,
      category: item.category,
      base_rate: item.base_rate,
      match_score: item.match_score,
      score_detail: item.score_detail, // 💡 프론트엔드 시각화용 데이터 추가
      ai_comment: aiComments[index] || '사장님의 조건에 잘 맞는 맞춤형 상품입니다.'
    }));

    res.status(200).json({
      financial_profile: {
        recommended_actions: finalResult
      }
    });

  } catch (error) {
    console.error('API/OpenAI 에러:', error);
    res.status(500).json({ success: false, message: '서버 에러 발생' });
  }
});

module.exports = router;