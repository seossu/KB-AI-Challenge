"""
합성 상권 패널 (API 승인 전 대체물).

실데이터로 교체 시 이 모듈만 갈아끼우면 됨:
  - panel: 상권 폴리곤 × 지표(원자료) 테이블. 정규화의 기준 분포이자 후보 소스.
  - spread_map: 성수동 후보별 '수익성 스프레드(매출증가율 − 임대료증가율)' 월별 시계열
                → Regime-Switching 국면추정 입력. (데이터_명세.md §2.4)

원자료(raw)를 생성하고, 정규화/필터/스코어링은 service.scoring 이 담당.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# 정규화 대상 지표와 방향. dir="up"=클수록 좋음 / "down"=작을수록 좋음(반전)
FEATURES = [
    {"key": "foot_traffic",  "dir": "up",   "label": "유동인구(20-30대)"},
    {"key": "rent_per_m2",   "dir": "down", "label": "임대료(㎡·월)"},
    {"key": "competition",   "dir": "down", "label": "경쟁밀도(카페)"},
    {"key": "closure_rate",  "dir": "down", "label": "폐업률"},
    {"key": "sales_index",   "dir": "up",   "label": "매출지수"},
    {"key": "transit",       "dir": "up",   "label": "교통접근성"},
    {"key": "infra",         "dir": "up",   "label": "생활인프라"},
    {"key": "residential",   "dir": "up",   "label": "배후인구"},
]

# 성수동 후보 4곳 (원자료). 스토리를 위해 값 고정.
#   A 카페거리 : 유동인구 최고이나 임대료·경쟁 과열 + 쇠퇴국면(젠트리피케이션)
#   B 성수역이면: 균형 + 성장국면  → 최종 1위 기대
#   C 서울숲인근: 유동인구 낮지만 저렴·저경쟁 + 성장국면
#   D 프리미엄  : 임대료 과다 + 주차불가 → 하드필터 탈락 시연용
_SEONGSU = [
    # name,             foot,  rent,  comp, close, sales, trans, infra, resi, park, avail
    ("성수 카페거리",   55000, 120000, 7.5, 0.15, 140, 82, 160, 12000, True, 40),
    ("성수역 이면",     34000,  80000, 3.2, 0.08, 110, 90, 120, 20000, True, 45),
    ("서울숲 인근",     22000,  65000, 2.0, 0.06,  95, 70, 110, 28000, True, 50),
    ("성수 프리미엄",   40000, 175000, 5.0, 0.10, 130, 60, 100, 10000, False, 35),
]

# 국면 스토리: 스프레드 월별 성장률(%) 평균 패턴.
# 2-state 식별이 안정적으로 되도록 저국면/고국면 분리를 뚜렷하게(노이즈 대비) 설계.
_SPREAD_PATTERN = {
    "성수 카페거리": [3.5] * 15 + [-2.0] * 15,   # 성장 → 쇠퇴 (끝이 저국면) → 쇠퇴
    "성수역 이면":   [-0.5] * 12 + [3.0] * 18,    # 저국면 → 성장 (끝이 고국면) → 성장
    "서울숲 인근":   [-0.3] * 12 + [2.6] * 18,    # 저국면 → 성장 (끝이 고국면) → 성장
    "성수 프리미엄": [3.0] * 15 + [-1.0] * 15,    # (탈락하지만 참고) 둔화
}


def _spread_series(pattern: list[float], seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    growth = np.array(pattern) + rng.normal(0, 0.8, len(pattern))
    idx = pd.period_range("2023-01", periods=len(pattern), freq="M").to_timestamp()
    return pd.Series(growth.round(3), index=idx)


def build_panel(n_other: int = 60, seed: int = 42) -> tuple[pd.DataFrame, dict]:
    """서울 상권 패널(정규화 기준 분포) + 성수동 후보 spread 시계열 반환."""
    rng = np.random.default_rng(seed)

    # 배경 분포: 서울 기타 상권 n_other 곳 (백분위 정규화의 기준)
    other = pd.DataFrame({
        "region": "기타",
        "foot_traffic": rng.uniform(5_000, 60_000, n_other).round(0),
        "rent_per_m2": rng.uniform(30_000, 130_000, n_other).round(0),
        "competition": rng.uniform(0.5, 8.0, n_other).round(2),
        "closure_rate": rng.uniform(0.02, 0.20, n_other).round(3),
        "sales_index": rng.uniform(50, 150, n_other).round(1),
        "transit": rng.uniform(10, 100, n_other).round(1),
        "infra": rng.uniform(5, 200, n_other).round(0),
        "residential": rng.uniform(3_000, 40_000, n_other).round(0),
        "has_parking": rng.random(n_other) < 0.5,
        "max_available_pyeong": rng.uniform(15, 60, n_other).round(0),
    }, index=[f"기타상권_{i:02d}" for i in range(n_other)])

    # 성수동 후보 주입
    cols = ["foot_traffic", "rent_per_m2", "competition", "closure_rate",
            "sales_index", "transit", "infra", "residential",
            "has_parking", "max_available_pyeong"]
    seongsu = pd.DataFrame(
        [row[1:] for row in _SEONGSU],
        index=[row[0] for row in _SEONGSU],
        columns=cols,
    )
    seongsu.insert(0, "region", "성수동")

    panel = pd.concat([seongsu, other])
    panel["has_parking"] = panel["has_parking"].astype(bool)

    spread_map = {
        name: _spread_series(pat, seed=100 + i)
        for i, (name, pat) in enumerate(_SPREAD_PATTERN.items())
    }
    return panel, spread_map


if __name__ == "__main__":
    p, s = build_panel()
    print(p.loc[p["region"] == "성수동"])
    print("spread series keys:", list(s.keys()))
