const express = require('express');
const router = express.Router();
const { createClient } = require('@supabase/supabase-js');
const { OpenAI } = require('openai');

// 지연 초기화: 키가 없어도 서버가 죽지 않게 (입지 추천은 이 라우트와 무관하게 동작)
let supabase = null;
let openai = null;
if (process.env.SUPABASE_URL && process.env.SUPABASE_ANON_KEY) {
  supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_ANON_KEY);
}
if (process.env.OPENAI_API_KEY) {
  openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
}

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
    const userAge = profile.is_youth ? 35 : 45;
    query = query.gte('req_age_max', userAge); 
    query = query.gte('req_max_biz_years', profile.business_stage_years);

    // 2. 자금 용도 (시설자금, 운전자금 등)
    const validPurposes = [...profile.loan_purpose, 'all'];
    query = query.in('req_loan_purpose', validPurposes);

    // 3. 담보 여력 (자가/전월세)
    if (!profile.has_collateral) {
      query = query.eq('needs_collateral', false);
    }

    // 4. [확장판] 특화 대상 철벽 방어
    // 유저가 해당하지 않는 특수 조건(여성, 장애인, 국가유공자, 다문화가정)의 전용 상품은 DB 조회 시점부터 원천 차단
    const allSpecialTargets = ['women', 'disabled', 'veteran', 'multicultural'];
    const userTargets = profile.special_targets || [];
    
    allSpecialTargets.forEach(target => {
      // 유저 배열에 이 target이 없으면, 해당 target 전용 상품은 쳐낸다.
      if (!userTargets.includes(target)) {
        query = query.neq('target_special', target);
      }
    });

    const { data: filteredProducts, error } = await query;
    if (error) throw error;

    // ==========================================
    // [2 & 3단계] 3단계 스코어링 파이프라인
    // ==========================================
    const scoredProducts = filteredProducts.map(product => {
      let baseScore = 0;
      let bonusScore = 0;
      
      // ----------------------------------------
      // Base Score (핵심 조건 매칭)
      // ----------------------------------------
      const isPerfectTarget = 
        (product.req_startup_exp === profile.startup_experience) ||
        (product.target_special === 'youth' && profile.is_youth) ||
        (product.req_credit_min === 'low' && profile.credit_status === 'low');
      
      if (isPerfectTarget) baseScore = 100;
      else baseScore = 70;

      // ----------------------------------------
      // Bonus Score (우대 가중치)
      // ----------------------------------------
      // 1. 가구 구성 금리 우대 (+30점) : 다자녀, 신혼부부, 한부모가정 포함
      const hasFamilyBonus = profile.special_interest_rate?.some(rate => 
        ['다자녀', '신혼부부', '한부모가정'].includes(rate)
      );
      if (hasFamilyBonus && product.category === '정책자금') {
        bonusScore += 30;
      }

      // 2. 서민금융 한도 우대 (+20점) : 중위소득 80% 이하 & 저신용
      const isLowIncome = profile.median_income_ratio <= 80;
      if (isLowIncome && profile.credit_status === 'low' && product.category === '보증서') {
        bonusScore += 20;
      }

      // 3. 특화 대상 심사 우대 (+10점) : 자동화 로직
      // 상품의 target_special이 유저의 special_targets 배열에 존재하면 무조건 가점
      if (userTargets.includes(product.target_special)) {
        bonusScore += 10;
      }

      // 💡 참고: profile.capital_amount 와 profile.existing_loan_amount는 
      // 나중에 '추천 대출 한도 산출식'을 고도화할 때 활용할 수 있습니다. 
      // (지금은 스코어링 순위에 직접 영향을 주지 않도록 보류해 둡니다.)

      return {
        ...product,
        match_score: baseScore + bonusScore
      };
    });

    // ==========================================
    // [마무리 정렬] Top 3 추출
    // ==========================================
    const top3Products = scoredProducts
      .sort((a, b) => {
        if (b.match_score !== a.match_score) return b.match_score - a.match_score;
        const rateA = a.base_rate !== null ? a.base_rate : 99;
        const rateB = b.base_rate !== null ? b.base_rate : 99;
        return rateA - rateB;
      })
      .slice(0, 3);

    // ==========================================
    // [OpenAI] AI 코멘트 생성 (모든 정보 전달)
    // ==========================================
    const prompt = `
      당신은 소상공인 창업자를 위한 전문 금융 컨설턴트입니다.
      아래 [고객 정보]를 바탕으로, 시스템이 추천한 [추천 상품 Top 3]에 대해 각각 1~2줄의 명확하고 전문적인 선정 이유를 작성해주세요.

      [고객 정보]
      - 창업 경험: ${profile.startup_experience === 'first' ? '생애최초' : '재창업/확장'}
      - 청년 여부: ${profile.is_youth ? '청년(만 39세 이하)' : '해당 없음'}
      - 신용 상태: ${profile.credit_status}
      - 가구 우대: ${profile.special_interest_rate?.join(', ') || '없음'}
      - 특화 우대: ${profile.special_targets?.join(', ') || '없음'} (여성, 장애인, 국가유공자 등)
      - 소득 상태: 중위소득 ${profile.median_income_ratio}%

      [추천 상품 Top 3]
      1순위: ${top3Products[0]?.product_name} (총점: ${top3Products[0]?.match_score}점)
      2순위: ${top3Products[1]?.product_name} (총점: ${top3Products[1]?.match_score}점)
      3순위: ${top3Products[2]?.product_name} (총점: ${top3Products[2]?.match_score}점)

      반드시 아래 JSON 형식으로만 응답을 반환해주세요. 
      고객 정보에 없는 혜택을 지어내지(환각) 마시고, 추천 상품명과 고객 정보를 논리적으로 연결해서 작성하세요.
      {
        "comments": [
          "1순위 상품 선정 이유",
          "2순위 상품 선정 이유",
          "3순위 상품 선정 이유"
        ]
      }
    `;

    const gptResponse = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: prompt }],
      response_format: { type: "json_object" }
    });

    const aiComments = JSON.parse(gptResponse.choices[0].message.content).comments;

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
      ai_comment: aiComments[index] || '추천 상품입니다.'
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