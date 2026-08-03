🏦 AI 소상공인 금융상품 추천 API (Phase 2 Backend)
사용자의 재무 상태와 우대 조건을 분석하여 최적의 금융상품 Top 3를 추천하고, OpenAI를 활용해 맞춤형 선정 이유를 제공하는 Node.js 기반 REST API 서버입니다.

🛠 Tech Stack
Runtime: Node.js

Framework: Express.js

Database: Supabase (PostgreSQL)

AI Integration: OpenAI API (gpt-4o-mini)

⚙️ 실행 환경 세팅 방법 (Getting Started)
프로젝트를 로컬 환경에서 실행하기 위한 필수 설정입니다.

1. 패키지 설치
터미널에서 프로젝트 루트 디렉토리로 이동한 후 아래 명령어를 실행합니다.

Bash
npm install
2. 환경변수(.env) 설정
루트 디렉토리에 .env 파일을 생성하고 아래 양식에 맞게 API 키를 입력합니다. (GitHub에 절대 커밋하지 마세요!)

코드 스니펫
PORT=8080
SUPABASE_URL=당신의_SUPABASE_PROJECT_URL
SUPABASE_ANON_KEY=당신의_SUPABASE_ANON_KEY
OPENAI_API_KEY=sk-당신의_OPENAI_API_KEY
3. 서버 실행

Bash
node server.js
서버가 정상적으로 켜지면 🚀 서버가 http://localhost:8080 에서 안전하게 실행 중입니다. 메시지가 출력됩니다.

📖 API 명세서 (API Specification)
프론트엔드 연동을 위한 엔드포인트 및 데이터 스키마 안내입니다.

[POST] /api/recommend
사용자 설문 데이터를 받아 스코어링(Hard Filter -> Base Score -> Bonus Score)을 거친 후, Top 3 추천 상품과 AI 코멘트를 반환합니다.

📥 Request (프론트엔드 -> 백엔드)
Content-Type: application/json

JSON
{
  "financial_profile": {
    "business_stage_years": 0,
    "startup_experience": "first",
    "is_youth": true,
    "credit_status": "medium",
    "has_collateral": false,
    "loan_purpose": ["facility", "operation"],
    "capital_amount": 100000000,
    "existing_loan_amount": 0,
    "household_size": 4,
    "median_income_ratio": 82,
    "special_targets": ["women", "low_income"],
    "special_interest_rate": ["다자녀"]
  }
}
📤 Response (백엔드 -> 프론트엔드)
Status: 200 OK

JSON
{
  "financial_profile": {
    "recommended_actions": [
      {
        "rank": 1,
        "product_name": "중진공 청년전용창업자금",
        "provider": "중소벤처기업진흥공단",
        "category": "정책자금",
        "base_rate": 2.50,
        "match_score": 130,
        "ai_comment": "대표님은 청년 요건에 해당하며, 창업 경험이 없는 청년 창업자에게 맞춤형 지원을 제공하여 초기 창업 비용 부담을 줄이는 데 도움이 됩니다."
      },
      {
        "rank": 2,
        "product_name": "KB 생애최초 소호 창업대출",
        "provider": "KB국민은행",
        "category": "자체대출",
        "base_rate": 4.50,
        "match_score": 100,
        "ai_comment": "생애 최초 창업자를 위한 KB 전용 상품으로 대표님의 현재 자격 요건과 부합하여 빠르고 안정적인 심사가 가능합니다."
      },
      {
        "rank": 3,
        "product_name": "여성기업종합지원센터 특화자금",
        "provider": "여성기업종합지원센터",
        "category": "정책자금",
        "base_rate": 2.80,
        "match_score": 90,
        "ai_comment": "여성 창업자 우대 조건에 해당하시어 일반 상품 대비 넉넉한 한도 확보가 가능한 특화 상품입니다."
      }
    ]
  }
}
