"""
합성 상권 데이터 생성기 (API 승인 전 프로토타이핑용).

실데이터(서울 열린데이터광장 생활인구, 소진공 상권분석)로 교체하기 전까지
Regime-Switching 파이프라인을 end-to-end 로 돌려보기 위한 대체물.

성수동을 모티프로: 초기 완만한 성장 → 팝업/핫플화로 급성장 국면 →
임대료 급등·젠트리피케이션으로 유동인구 성장 둔화(정체국면) 시나리오를 생성한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_monthly_foot_traffic(
    region_name: str = "성수동",
    n_months: int = 30,
    seed: int = 42,
) -> pd.DataFrame:
    """월별 유동인구 수준(level)과 MoM 성장률(%)을 생성.

    Returns
    -------
    DataFrame(index=month, columns=[region, foot_traffic, mom_growth])
    """
    rng = np.random.default_rng(seed)

    # 국면별 월간 성장률(%) 평균: 성장 vs 정체.
    # 앞 1/3 완만성장 → 중간 1/3 급성장 → 마지막 1/3 정체.
    third = n_months // 3
    regime_means = (
        [1.0] * third                         # 완만한 성장
        + [4.5] * third                       # 급성장(핫플화)
        + [-0.8] * (n_months - 2 * third)     # 정체/둔화(젠트리피케이션)
    )
    growth = np.array(regime_means) + rng.normal(0, 1.2, n_months)

    # 성장률 → 수준 복원 (기준 유동인구 100,000명/월).
    level = 100_000 * np.cumprod(1 + growth / 100)

    idx = pd.period_range("2023-01", periods=n_months, freq="M").to_timestamp()
    df = pd.DataFrame(
        {
            "region": region_name,
            "foot_traffic": level.round(0),
            "mom_growth": growth.round(3),
        },
        index=idx,
    )
    df.index.name = "month"
    return df


def make_new_district(region_name: str = "신생상권", n_months: int = 10, seed: int = 7) -> pd.DataFrame:
    """표본 부족(<18개월) 상권. model_confidence='low' 방어로직 시연용."""
    return make_monthly_foot_traffic(region_name, n_months=n_months, seed=seed)


if __name__ == "__main__":
    df = make_monthly_foot_traffic()
    print(df.head())
    print("...")
    print(df.tail())
