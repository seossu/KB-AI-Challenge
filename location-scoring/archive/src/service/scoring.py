"""
스코어링 엔진 (데이터_명세.md §2~§3).

흐름: 백분위 정규화 → 하드필터 → priority 가중합(base_score)
      → 국면승수(final_score) → Top-N 랭킹.

Pull/Push 공유 엔진. Pull = 후보 여러 곳에 1회 실행, Push = 한 곳에 월별 실행.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.data.market_panel import FEATURES
from src.models.regime_switching import estimate_regime, regime_multiplier
from src.service.schema import UserQuery, PYEONG_TO_M2

# 지표 기본 가중치(합=1). priority에 포함되면 BOOST 배 → 재정규화. (§2.3)
BASE_WEIGHTS = {
    "foot_traffic": 0.18, "rent_per_m2": 0.15, "competition": 0.13,
    "closure_rate": 0.10, "sales_index": 0.12, "transit": 0.12,
    "infra": 0.10, "residential": 0.10,
}
PRIORITY_TO_FEATURE = {
    "foot_traffic": "foot_traffic", "low_rent": "rent_per_m2",
    "low_competition": "competition", "transit": "transit",
    "residential_base": "residential",
}
BOOST = 2.0

# 하드필터·비용 파라미터
TRANSIT_MIN = 40          # 대중교통 접근성 최소 점수
DEPOSIT_MONTHS = 10       # 보증금 ≈ 월세 × 개월
KEY_MONEY_MONTHS = 12     # 권리금(추정) ≈ 월세 × 개월
OPEX_MONTHS = 3           # 초기 운영비 ≈ 월세 × 개월
FITOUT_PER_PYEONG = 3_000_000  # 평당 시설비


@dataclass
class CandidateResult:
    name: str
    passed: bool
    filter_reasons: list[str]
    base_score: float
    growth_prob: float
    regime_conf: str
    multiplier: float
    final_score: float
    cost: dict = field(default_factory=dict)


def normalize(panel: pd.DataFrame) -> pd.DataFrame:
    """방향 통일한 백분위(0~100). down 지표는 100-백분위로 반전. (§2.2)"""
    norm = pd.DataFrame(index=panel.index)
    for f in FEATURES:
        pct = panel[f["key"]].rank(pct=True) * 100
        norm[f["key"]] = (100 - pct) if f["dir"] == "down" else pct
    return norm


def weights_for(priority: list[str], base_weights: dict | None = None) -> dict:
    """base_weights(기본: 손으로 정한 BASE_WEIGHTS, 또는 학습 가중치) 위에
    사용자 priority를 BOOST배 얹어 재정규화."""
    w = dict(base_weights or BASE_WEIGHTS)
    for p in priority:
        key = PRIORITY_TO_FEATURE.get(p)
        if key:
            w[key] *= BOOST
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def estimate_cost(row: pd.Series, q: UserQuery) -> dict:
    monthly_rent = row["rent_per_m2"] * (q.store_size_pyeong * PYEONG_TO_M2)
    deposit = monthly_rent * DEPOSIT_MONTHS
    key_money = monthly_rent * KEY_MONEY_MONTHS
    fitout = q.store_size_pyeong * FITOUT_PER_PYEONG
    opex = monthly_rent * OPEX_MONTHS
    total = deposit + key_money + fitout + opex
    return {"monthly_rent": monthly_rent, "deposit": deposit,
            "key_money": key_money, "fitout": fitout, "opex": opex, "total": total}


def hard_filter(row: pd.Series, q: UserQuery, cost: dict) -> list[str]:
    """감당 불가 조건 → 탈락 사유 리스트. 빈 리스트면 통과. (§3.2)"""
    reasons = []
    if q.parking and not row["has_parking"]:
        reasons.append("주차 불가")
    if q.public_transport and row["transit"] < TRANSIT_MIN:
        reasons.append("대중교통 접근성 미달")
    if q.store_size_pyeong > row["max_available_pyeong"]:
        reasons.append(f"{q.store_size_pyeong:.0f}평 매물 확보 불가")
    if cost["total"] > q.total_funding:
        reasons.append(
            f"초기자금 초과(필요 {cost['total']/1e8:.2f}억 > 가용 {q.total_funding/1e8:.2f}억)")
    return reasons


def score_candidates(q: UserQuery, panel: pd.DataFrame, spread_map: dict,
                     base_weights: dict | None = None) -> list[CandidateResult]:
    """preferred_region 후보들을 스코어링해 정렬된 결과 반환.

    base_weights=None 이면 손으로 정한 기본가중치, 지정 시 학습 가중치를 base로 사용.
    """
    norm = normalize(panel)                       # 전체 패널 대비 백분위
    weights = weights_for(q.priority, base_weights)
    candidates = panel[panel["region"] == q.preferred_region]

    results: list[CandidateResult] = []
    for name, row in candidates.iterrows():
        cost = estimate_cost(row, q)
        reasons = hard_filter(row, q, cost)
        base = sum(weights[f["key"]] * norm.loc[name, f["key"]] for f in FEATURES)

        series = spread_map.get(name)
        if series is not None:
            reg = estimate_regime(series, region_name=name)
            mult = regime_multiplier(reg)
            gp, conf = reg.growth_prob, reg.model_confidence
        else:
            mult, gp, conf = 1.0, 0.5, "none"

        results.append(CandidateResult(
            name=name, passed=(not reasons), filter_reasons=reasons,
            base_score=round(base, 1), growth_prob=round(gp, 3),
            regime_conf=conf, multiplier=round(mult, 3),
            final_score=round(base * mult, 1), cost=cost,
        ))

    # 통과 후보를 final_score 내림차순, 탈락 후보는 뒤로
    results.sort(key=lambda r: (r.passed, r.final_score), reverse=True)
    return results
