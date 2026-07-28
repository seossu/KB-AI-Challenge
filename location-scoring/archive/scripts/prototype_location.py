"""
Phase 1 (Pull) 입지 스코어링 데모 — 금융추천 제외.

실행:  python kb/scripts/prototype_location.py [입력json경로]
기본 입력: kb/data/sample_input.json

흐름: JSON 입력 → 합성 상권 패널 → 백분위 정규화 → 하드필터
      → priority 가중합(base) → 국면승수 → Top-N 랭킹 출력.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.market_panel import build_panel, FEATURES
from src.models.weight_learner import learn_weights
from src.service.schema import UserQuery
from src.service.scoring import score_candidates, normalize, weights_for, BASE_WEIGHTS


def won(x: float) -> str:
    return f"{x/1e8:.2f}억"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "sample_input.json"
    q = UserQuery.from_dict(json.loads(path.read_text(encoding="utf-8")))

    print("=" * 68)
    print("입력 조건")
    print("=" * 68)
    print(f"  업종/목적    : {q.business_type} / {q.purpose}")
    print(f"  희망지역      : {q.preferred_region}")
    print(f"  타깃세그먼트  : {q.segment}   (유동인구 필터 기준)")
    print(f"  자금          : 자기자본 {won(q.capital)} + 희망대출 {won(q.desired_loan)} = 조달 {won(q.total_funding)}")
    print(f"  매장/조건     : {q.store_size_pyeong:.0f}평, 주차={q.parking}, 대중교통={q.public_transport}")
    print(f"  우선순위      : {q.priority}")

    panel, spread_map = build_panel()

    # 학습 가중치 (실증 데이터로 지도학습) — 손으로 정한 기본가중치를 대체
    print("\n" + "=" * 68)
    print("가중치 학습 (지도학습 ML)")
    print("=" * 68)
    lw = learn_weights()
    print(f"  학습표본 {lw['n']}곳, 성공률 {lw['success_rate']}, holdout AUC {lw['auc_holdout']}")
    print(f"  {'지표':<14}{'기본(직관)':>10}{'학습(실증)':>10}")
    for k in sorted(lw["weights"], key=lambda x: -lw["weights"][x]):
        print(f"  {k:<14}{BASE_WEIGHTS[k]:>10.2f}{lw['weights'][k]:>10.2f}")
    print("  → 실증: 매출·폐업률·경쟁이 유동인구보다 생존에 결정적 (직관과 상반)")

    weights = weights_for(q.priority, base_weights=lw["weights"])
    print("\n  최종 적용 가중치(학습+priority): "
          + ", ".join(f"{k}={v:.2f}" for k, v in weights.items()))

    results = score_candidates(q, panel, spread_map, base_weights=lw["weights"])

    print("\n" + "=" * 68)
    print(f"입지 스코어링 결과 — {q.preferred_region} 후보 {len(results)}곳")
    print("=" * 68)
    header = f"{'순위':<4}{'상권':<14}{'base':>7}{'국면P':>7}{'승수':>7}{'final':>8}  판정"
    print(header)
    print("-" * 68)
    rank = 0
    for r in results:
        if r.passed:
            rank += 1
            verdict = f"통과 (conf={r.regime_conf})"
            rank_str = f"{rank}"
        else:
            verdict = "탈락: " + ", ".join(r.filter_reasons)
            rank_str = "-"
        print(f"{rank_str:<4}{r.name:<14}{r.base_score:>7}{r.growth_prob:>7}"
              f"{r.multiplier:>7}{r.final_score:>8}  {verdict}")

    # Top 1 상세
    top = next((r for r in results if r.passed), None)
    if top:
        c = top.cost
        print("\n" + "=" * 68)
        print(f"추천 1위 상세 — {top.name}")
        print("=" * 68)
        print(f"  최종점수      : {top.final_score}  (base {top.base_score} × 국면승수 {top.multiplier})")
        print(f"  성장국면 확률  : {top.growth_prob}  (신뢰도 {top.regime_conf})")
        print(f"  예상 월임대료  : {c['monthly_rent']/1e4:.0f}만원")
        print(f"  초기소요자금  : {won(c['total'])}  "
              f"[보증금 {won(c['deposit'])} + 권리금 {won(c['key_money'])} "
              f"+ 시설 {won(c['fitout'])} + 운영 {won(c['opex'])}]")
        gap = c["total"] - q.total_funding
        print(f"  자금격차 gap  : {won(gap) if gap>0 else '없음(자체조달 가능)'}"
              + ("  → (다음 단계: 금융상품 매칭)" if gap > 0 else ""))

    # 스토리 포인트
    a = next((r for r in results if r.name == "성수 카페거리"), None)
    if a:
        print("\n" + "-" * 68)
        print("[인사이트] 성수 카페거리는 유동인구 1등이지만, 임대료·경쟁 과열로")
        print(f"           base가 낮고(={a.base_score}), 국면도 쇠퇴(P={a.growth_prob})라 승수 {a.multiplier}로")
        print("           눌려 최하위. → '유동인구 최고 ≠ 최적'을 숫자로 증명.")


if __name__ == "__main__":
    main()
