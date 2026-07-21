"""
Sensing 단계 조작화: Markov Regime-Switching Model (Hamilton, 1989).

거시경제 경기순환 판별 기법을 '상권 단위 미시국면'에 맞게 스케일 조정해 적용한다.
- 관측 단위: 월별 집계 지표 (유동인구 MoM 성장률 등)
- 상태 수: 2-state (성장국면 / 침체·정체국면)
- 방어 로직: 표본 18개월 미만이면 국면판단을 skip 하고 model_confidence="low" 반환.
  신생 상권처럼 표본이 부족할 때 억지 추정하지 않는 것 자체가 신뢰성 확보 장치.

반환 growth_prob 은 location_matcher 의 regime_multiplier = 0.7 + 0.6 * growth_prob 로 소비된다.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

# 유의미한 국면추정을 위한 최소 관측치(월). 24개월(2년)이면 high, 그 사이는 medium.
MIN_OBS = 18
CONF_HIGH_OBS = 24


@dataclass
class RegimeResult:
    region_name: str
    n_obs: int
    model_confidence: str                     # "high" | "medium" | "low"
    growth_prob: float                        # 최신 시점 성장국면 확률 (0~1)
    current_regime: str                       # "growth" | "contraction" | "unknown"
    growth_state_id: Optional[int] = None     # 성장으로 식별된 state index
    persistence: Optional[float] = None       # 현재 국면 지속확률 P(stay)
    smoothed_growth_prob: list[float] = field(default_factory=list)  # 시계열 전체 성장확률
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _confidence(n_obs: int) -> str:
    if n_obs < MIN_OBS:
        return "low"
    return "high" if n_obs >= CONF_HIGH_OBS else "medium"


def estimate_regime(
    series: pd.Series,
    region_name: str = "unknown",
    k_regimes: int = 2,
) -> RegimeResult:
    """월별 지표 시계열에서 성장국면 확률을 추정한다.

    Parameters
    ----------
    series : pd.Series
        월별 지표(권장: 유동인구 MoM 성장률, %). DatetimeIndex 권장.
    region_name : str
    k_regimes : int
        상태 수. 기본 2 (성장/침체).
    """
    s = series.dropna().astype(float)
    n = len(s)

    # --- 방어 로직: 표본 부족 시 국면판단 skip ---
    if n < MIN_OBS:
        return RegimeResult(
            region_name=region_name,
            n_obs=n,
            model_confidence="low",
            growth_prob=0.5,                 # 중립값 → multiplier=1.0 로 무력화됨
            current_regime="unknown",
            note=f"표본 {n}개월 < 최소 {MIN_OBS}개월. 국면추정 skip, 중립 처리.",
        )

    # 평균/분산 모두 국면에 따라 달라진다고 가정 (switching_variance=True).
    model = MarkovRegression(
        s.values,
        k_regimes=k_regimes,
        trend="c",
        switching_variance=True,
    )

    try:
        res = model.fit(maxiter=200, disp=False)
    except Exception as exc:  # 수렴 실패 등 → 중립 처리로 안전 폴백
        return RegimeResult(
            region_name=region_name,
            n_obs=n,
            model_confidence="low",
            growth_prob=0.5,
            current_regime="unknown",
            note=f"모델 적합 실패({type(exc).__name__}). 중립 처리.",
        )

    # state별 상수항(평균) 중 가장 큰 쪽을 '성장국면'으로 식별.
    # res.params 는 이름 없는 ndarray 이므로 param_names 로 인덱스를 찾는다.
    names = list(res.model.param_names)
    const_params = np.array(
        [res.params[names.index(f"const[{i}]")] for i in range(k_regimes)]
    )
    growth_state = int(np.argmax(const_params))

    smoothed = res.smoothed_marginal_probabilities  # shape (n_obs, k_regimes)
    growth_series = np.asarray(smoothed)[:, growth_state]
    growth_prob = float(growth_series[-1])

    # 전이확률 행렬에서 성장국면 지속확률 P(growth->growth).
    try:
        trans = res.regime_transition[:, :, 0]  # (k, k)
        persistence = float(trans[growth_state, growth_state])
    except Exception:
        persistence = None

    return RegimeResult(
        region_name=region_name,
        n_obs=n,
        model_confidence=_confidence(n),
        growth_prob=growth_prob,
        current_regime="growth" if growth_prob >= 0.5 else "contraction",
        growth_state_id=growth_state,
        persistence=persistence,
        smoothed_growth_prob=[round(float(x), 4) for x in growth_series],
        note="정상 추정.",
    )


def regime_multiplier(result: RegimeResult) -> float:
    """final_score 조정용 승수. confidence 낮으면 1.0(무력화)."""
    if result.model_confidence == "low":
        return 1.0
    return round(0.7 + 0.6 * result.growth_prob, 4)


if __name__ == "__main__":
    # 최소 자체 점검: 뚜렷한 두 국면을 가진 합성 시계열.
    rng = np.random.default_rng(0)
    up = rng.normal(3.0, 1.0, 18)     # 성장
    down = rng.normal(-2.0, 1.0, 18)  # 침체
    demo = pd.Series(np.concatenate([up, down, up[:6]]))
    r = estimate_regime(demo, region_name="self-test")
    print(r.to_dict())
    print("multiplier:", regime_multiplier(r))
