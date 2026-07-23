# 프로젝트 구조 (실행 파이프라인)

## 진입점
`scripts/run_request.py <입력.json>` → 1팀 JSON을 받아 입지 추천 출력

## 메인 파이프라인 (실제 실행 경로)
```
run_request.py
 └ src/service/request_handler.py        # 오케스트레이터
    ├ src/service/team1_adapter.py       # 1팀 JSON 정규화(언랩·금액·지역배열)
    ├ src/service/industry_scoring.py    # 지표 패널 + 산업별 AHP 매핑
    │   ├ collectors/seoul_golmok.py     # 점포·매출 (키 불필요)
    │   ├ collectors/seoul_openapi.py    # 유동/배후/직장/집객 (서울 키)
    │   ├ collectors/seoul_area.py       # 상권↔자치구/좌표 (키 불필요)
    │   └ service/external_indicators.py
    │       ├ collectors/molit_rtms.py   # 실거래가(임대료) (data.go.kr 키)
    │       ├ collectors/parking.py      # 공영주차장 (data.go.kr 키)
    │       └ collectors/bldrgst.py      # 건축물대장 (data.go.kr 키)
    ├ src/models/industry_weight_learner.py  # AHP 없는 업종 → 실데이터 학습
    ├ src/service/reweight.py            # 사용자 우선순위 재가중(볼록결합)
    └ src/config.py                      # .env 키 로더
```

## 보조 (발표 근거·분석, 단독 실행)
- `scripts/real_multivariate.py`   : 폐업예측 실증모델(경쟁밀도 지배 근거)
- `scripts/analysis_findings.py`   : 생산성/트레이드오프/성수 프로파일 분석
- `scripts/industry_recommend.py`  : 산업별 AHP 커버리지 + 추천 CLI
- `src/models/ahp.py`              : AHP 쌍대비교→가중치+CR (1팀 AHP 검증용)
- `src/models/regime_switching.py` : Push(국면) 프로토타입

## archive/
개발 과정의 초기 프로토타입(합성데이터 시절). 실행 파이프라인 미사용, 이력 보관.
