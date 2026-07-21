# 🏢 KB AI Challenge - 창업 입지 컨설팅 에이전트

LLM(GPT-4o)과 Pydantic을 활용하여 사용자의 창업 목적, 업종, 예산, 선호 지역 등의 정보를 대화형으로 자연스럽게 수집하고 상권 분석 데이터를 추출하는 컨설팅 에이전트 서비스입니다.

---

## 🛠️ 주요 기능 (Features)
- **자연스러운 멀티턴 대화 수집:** 사용자와의 대화 맥락을 파악하여 필수 정보 및 선택 정보를 누적(Accumulation) 및 업데이트합니다.
- **체계적인 수집 단계:**
  1. **필수 정보 수집:** 창업 목적(`purpose`), 업종(`business_type`), 자본금(`capital`), 선호 지역(`preferred_region`, 배열 형태)
  2. **선택 정보 유도:** 필수 정보가 모두 채워지면, 사용자가 주도적으로 추가 정보(타겟층, 매장 크기, 주차 여부, 대중교통 등)를 입력할 수 있도록 유도
  3. **우선순위 수집:** 가장 마지막 순서로 사용자의 우선순위(`priority`)를 파악
- **Pydantic 데이터 검증:** 구조화된 JSON 포맷을 엄격하게 검증하여 안정적인 데이터 파싱 보장

---

## 📂 프로젝트 구조 (Project Structure)
📦 KB-AI-Challenge
 ┣ 📜 .env               # API 키 설정 (Gitignore 적용)
 ┣ 📜 .gitignore         # Git 추적 제외 파일 설정
 ┣ 📜 main.py            # 메인 컨설팅 에이전트 실행 코드
 ┣ 📜 requirements.txt   # 파이썬 패키지 의존성 파일
 ┗ 📜 README.md          # 프로젝트 설명 문서

---

## 🚀 시작 가이드 (Getting Started)

### 1. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Mac / Linux
# venv\Scripts\activate   # Windows