"""
Regime-Switching 프로토타입 데모.

실행:  python kb/scripts/prototype_regime.py

수행:
  1. 성수동 합성 유동인구(30개월) 생성 → 국면 추정
  2. 신생상권(10개월) → 표본부족 방어로직 확인
  3. Ablation: 단순 임계값 규칙 vs Markov Switching 비교 (§4.4)
  4. 성장확률 시계열을 outputs/ 에 PNG 로 저장(가능 시)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 패키지 경로 등록
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.synthetic import make_monthly_foot_traffic, make_new_district
from src.models.regime_switching import estimate_regime, regime_multiplier


def rule_based_regime(mom_growth: pd.Series, window: int = 3, threshold: float = 0.0) -> str:
    """비교 기준선(baseline): 최근 window개월 평균 성장률이 threshold 초과면 'growth'."""
    recent = mom_growth.dropna().tail(window).mean()
    return "growth" if recent > threshold else "contraction"


def line(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main() -> None:
    # --- 1. 성수동 ---
    line("1) 성수동 (30개월) — Markov Regime-Switching")
    df = make_monthly_foot_traffic("성수동", n_months=30)
    res = estimate_regime(df["mom_growth"], region_name="성수동")
    print(f"n_obs            : {res.n_obs}")
    print(f"model_confidence : {res.model_confidence}")
    print(f"current_regime   : {res.current_regime}")
    print(f"growth_prob      : {res.growth_prob:.3f}")
    print(f"persistence P(스테이): {res.persistence}")
    print(f"regime_multiplier: {regime_multiplier(res)}")
    print(f"note             : {res.note}")

    # --- 2. 신생상권 방어로직 ---
    line("2) 신생상권 (10개월) — 표본부족 방어로직")
    df2 = make_new_district("신생상권", n_months=10)
    res2 = estimate_regime(df2["mom_growth"], region_name="신생상권")
    print(f"n_obs            : {res2.n_obs}")
    print(f"model_confidence : {res2.model_confidence}  (기대: low)")
    print(f"growth_prob      : {res2.growth_prob}  (중립 0.5)")
    print(f"regime_multiplier: {regime_multiplier(res2)}  (기대: 1.0, 무력화)")
    print(f"note             : {res2.note}")

    # --- 3. Ablation ---
    line("3) Ablation — 단순 임계값 규칙 vs Markov Switching")
    print(f"{'시점':<12}{'MoM(%)':>10}{'규칙기반':>12}{'Markov P(growth)':>20}")
    smoothed = res.smoothed_growth_prob
    for i in range(len(df) - 6, len(df)):  # 마지막 6개월
        month = df.index[i].strftime("%Y-%m")
        mom = df["mom_growth"].iloc[i]
        rule = rule_based_regime(df["mom_growth"].iloc[: i + 1])
        p = smoothed[i] if i < len(smoothed) else float("nan")
        print(f"{month:<12}{mom:>10.2f}{rule:>12}{p:>20.3f}")
    print("\n해석: 규칙기반은 최근 평균 부호만 보므로 국면전환 근처에서 진동/지연."
          "\n      Markov 는 전이확률로 국면 지속성을 반영해 더 매끄럽게 전환 시점을 잡음.")

    # --- 4. 시각화 저장(선택) ---
    try:
        import warnings
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # 한글 폰트(가능 시). 없으면 라벨만 깨지고 그래프는 정상.
        for _f in ("AppleGothic", "Malgun Gothic", "NanumGothic"):
            try:
                matplotlib.rcParams["font.family"] = _f
                break
            except Exception:
                continue
        matplotlib.rcParams["axes.unicode_minus"] = False
        warnings.filterwarnings("ignore")  # 폰트 glyph 경고 억제

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        ax1.plot(df.index, df["foot_traffic"], color="#1f77b4")
        ax1.set_title("성수동 월별 유동인구 (합성)")
        ax1.set_ylabel("유동인구")

        ax2.plot(df.index[: len(smoothed)], smoothed, color="#d62728")
        ax2.axhline(0.5, ls="--", color="gray", lw=1)
        ax2.set_title("성장국면 확률 P(growth) — Markov smoothed")
        ax2.set_ylabel("prob")
        ax2.set_ylim(-0.02, 1.02)

        fig.tight_layout()
        out = ROOT / "outputs" / "regime_seongsu.png"
        fig.savefig(out, dpi=120)
        print(f"\n[저장] {out}")
    except Exception as exc:
        print(f"\n[시각화 skip] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
