# KB AI Challenge — AI 데이터 기반 최적 입지 컨설팅 서비스

동적 환경 변화를 감지해 입지 전략과 금융상품을 실시간 재조정하는 에이전트.
이론 프레임: **Dynamic Capabilities Theory** (Sensing → Seizing → Transforming),
각 단계 조작화는 Markov Regime-Switching / Real Options / 규칙기반 금융매칭.

## 현재 구현 (프로토타입 단계)

API 키 승인 전이라 **합성 데이터**로 Sensing 파이프라인을 end-to-end 검증한 상태.

```
kb/
├── requirements.txt
├── 데이터_명세.md                  # 데이터 수집·가공·스코어링·평가 기준 문서
├── data/sample_input.json          # 사용자 입력 예시 (성수동 카페)
├── src/
│   ├── collectors/
│   │   └── seoul_golmok.py         # ★실데이터 수집기(키 불필요): 서울 상권분석 점포·매출
│   ├── data/
│   │   ├── synthetic.py            # 합성 유동인구 시계열 (regime 데모용)
│   │   └── market_panel.py         # 합성 상권 패널 + 국면 스프레드 (실데이터 교체 대상)
│   ├── models/
│   │   ├── regime_switching.py     # Markov 2-state 국면추정 + 18개월 방어로직
│   │   └── weight_learner.py       # 실증 데이터로 지표 가중치 지도학습(로지스틱)
│   └── service/
│       ├── schema.py               # 입력 JSON → UserQuery
│       └── scoring.py              # 정규화→하드필터→가중합→국면승수→랭킹
├── scripts/
│   ├── prototype_regime.py         # 국면추정 데모 (추정+방어로직+ablation+PNG)
│   └── prototype_location.py       # Phase 1 입지 스코어링 데모 (금융추천 제외)
└── outputs/regime_seongsu.png
```

## 셋업 (최초 1회)

```bash
pip install -r requirements.txt

# API 키 설정 — .env.example 를 복사해 값 채우기
cp .env.example .env
#   SEOUL_API_KEY=...   서울 열린데이터광장 (즉시 발급)
#   DATAGO_KEY=...      공공데이터포털 (API별 '활용신청' 필요)
```

⚠️ `.env` 와 `data/_cache/`(94MB, API 재수집 가능)는 **gitignore 처리**되어 커밋되지 않습니다.
데이터는 최초 실행 시 자동 수집·캐시됩니다.

### 필요한 API 활용신청 (data.go.kr)
- 국토교통부_상업업무용 부동산 매매 실거래가 (임대료)
- 국토교통부_건축HUB_건축물대장정보 (점포특징·사업장)
- 전국주차장정보 표준데이터 (주차편리)

## 실행

```bash
# 1팀 JSON 입력 → 입지 추천 (메인)
python scripts/run_request.py data/team1_input.json

# 산업별 AHP 커버리지 + 추천
python scripts/industry_recommend.py 카페 성동구
```

<!-- 이전 실행 안내 -->

```bash
pip install -r kb/requirements.txt

# Phase 1 — 입지 스코어링 (JSON 입력 → Top-N 랭킹)
python kb/scripts/prototype_location.py            # 기본: data/sample_input.json
python kb/scripts/prototype_location.py 다른입력.json

# 국면추정 단독 데모 (방어로직 + ablation + 시각화)
python kb/scripts/prototype_regime.py

# ★실데이터 폐업예측 모델 (서울 상권분석 점포+매출, 키 불필요, holdout AUC≈0.80)
python kb/scripts/real_multivariate.py
```

## 실데이터 (API 키 불필요)

`seoul_golmok.py`가 서울 열린데이터광장 상권분석서비스를 **본인인증 없이** 파일 다운로드
(datafile.seoul.go.kr POST 재현). 최초 실행 시 `data/_cache/`에 CSV 캐시.

- `store`(OA-15577): 상권·업종·분기별 점포수/개폐업/프랜차이즈
- `sales`(OA-15572): 매출금액/건수 + 연령·시간·요일별 (20-30대·점심저녁 세그먼트 실측 가능)

`real_multivariate.py`: 두 파일을 조인해 Q3 피처→Q4 폐업 예측(1,059개 상권, AUC 0.80).
실증 결과 — **유사업종수·경쟁이 폐업↑, 객단가·20-30대비중·점심저녁비중이 생존↑** →
스코어링 설계를 실데이터로 검증. (※생활인구 실시간·실거래가 API는 별도 본인인증 필요)

`prototype_location.py` 출력: 입력조건 → 가중치 → 성수동 후보 4곳의
base_score / 국면확률 / 승수 / final_score 랭킹 + 하드필터 탈락 사유 + 1위 상세(자금격차).

## 핵심 설계 포인트

- **2-state** (성장 / 침체·정체), `switching_variance=True`.
- 국가단위 경기순환 모델을 **상권 미시국면**에 맞게 관측윈도우(월별)·상태수 조정해 적용.
- 표본 **18개월 미만이면 국면추정 skip** → `model_confidence="low"`, 승수 1.0 무력화.
  (신생 상권에서 억지 추정하지 않는 것 자체가 신뢰성 장치.)
- `regime_multiplier = 0.7 + 0.6 * growth_prob` → `final_score = base_score * multiplier`.

## 다음 단계 (TODO)

1. 서울 열린데이터광장 / 국토부 실거래가 API 연동 → `src/collectors/` 신설, 합성데이터 대체.
2. `src/models/static_score.py` (교통·인프라·경쟁밀도 정규화).
3. `src/service/location_matcher.py` (하드필터 → 가중치 → final_score → Top-5).
4. `src/service/funding_matcher.py` (정책자금 RAG + Claude API 설명 생성).
5. FastAPI `POST /api/v1/recommend` + Streamlit 데모.
6. 국내 Regime-Switching/상권분석 선행연구 인용 확보.
