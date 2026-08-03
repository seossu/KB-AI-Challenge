"""
하이브리드 Phase 1 (Pull) — 실데이터로 성수 상권 입지 점수화 + Push 트렌드.

지금 가능한 실데이터(점포+매출, 키 불필요)만으로:
  - Pull: 서울 전역 대비 백분위 → ML 학습 가중치·방향으로 base_score → 성수 상권 랭킹
  - Push: 고른 상권의 분기별 폐업률·경쟁·매출 추세 + 트리거

미포함(키 발급 시 추가): 유동인구·임대료·교통·인프라·배후인구.

실행:  python kb/scripts/hybrid_pull.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.real_multivariate import learn_real_weights, build_dataset, FEATURES, LABELS

LATEST_Q = 20254
PENDING = ["임대료(국토부 키 필요)"]


def percentile(s: pd.Series) -> pd.Series:
    return s.rank(pct=True) * 100


def main() -> None:
    print("실데이터 로드 + 실측 가중치 학습 중 (키 불필요)…")
    r = learn_real_weights()
    print(f"학습 가중치 출처: 서울 {r['n']}개 상권 폐업모델 (holdout AUC {r['auc']:.3f})\n")

    m = build_dataset()
    panel = m[m["stdr_yyqu_cd"] == LATEST_Q].dropna(subset=FEATURES).copy()

    # 백분위 정규화 + 학습 방향으로 정렬(up=그대로 / down=반전) → 가중합
    base = np.zeros(len(panel))
    for f in FEATURES:
        pct = percentile(panel[f])
        oriented = pct if r["direction"][f] == "up" else (100 - pct)
        base += r["weight"][f] * oriented.values
    panel["base_score"] = base.round(1)

    # 성수 상권만, 점포 5개 이상(유의미)
    seongsu = panel[panel["trdar_cd_nm"].astype(str).str.contains("성수", na=False)]
    seongsu = seongsu[seongsu["stor_co"] >= 5].sort_values("base_score", ascending=False)

    print("=" * 70)
    print("Pull — 성수 상권 입지 점수 (실데이터, 커피-음료, 2025 4분기)")
    print("=" * 70)
    print(f"{'순위':<4}{'상권':<16}{'점수':>6}{'점포':>5}{'폐업%':>6}{'객단가(원)':>11}{'20-30%':>8}")
    for i, (_, row) in enumerate(seongsu.iterrows(), 1):
        print(f"{i:<4}{row['trdar_cd_nm']:<16}{row['base_score']:>6}"
              f"{int(row['stor_co']):>5}{row['clsbiz_rt']:>6.0f}"
              f"{row['avg_ticket']:>11,.0f}{row['seg2030_ratio']*100:>7.0f}%")
    print(f"\n※ 점수 = 서울 전역 백분위 × 실측ML 가중치·방향. 미포함 지표: {', '.join(PENDING)} (키 발급 시 추가)")

    # 학습 가중치·방향 표
    print("\n적용된 실측 가중치 (폐업모델이 준 값·방향):")
    for f in sorted(FEATURES, key=lambda x: -r["weight"][x]):
        arrow = "높을수록 유리" if r["direction"][f] == "up" else "낮을수록 유리"
        print(f"  {LABELS[f]:<16}{r['weight'][f]:.3f}  ({arrow})")

    # ---- Push: 1위 상권의 분기별 추세 + 트리거 ----
    top = seongsu.iloc[0]["trdar_cd_nm"]
    hist = m[(m["trdar_cd_nm"] == top)].sort_values("stdr_yyqu_cd")
    print("\n" + "=" * 70)
    print(f"Push — '{top}' 분기별 모니터링 (실데이터)")
    print("=" * 70)
    print(f"{'분기':<8}{'점포수':>7}{'폐업률%':>8}{'매출(억)':>10}")
    for _, h in hist.iterrows():
        print(f"{int(h['stdr_yyqu_cd']):<8}{int(h['stor_co']):>7}{h['clsbiz_rt']:>8.0f}"
              f"{h['sales_amt']/1e8:>10.1f}")
    # 간단 트리거: 최근 분기 폐업률 상승 or 경쟁 점포수 증가
    if len(hist) >= 2:
        last, prev = hist.iloc[-1], hist.iloc[-2]
        alerts = []
        if last["clsbiz_rt"] > prev["clsbiz_rt"]:
            alerts.append(f"폐업률 상승({prev['clsbiz_rt']:.0f}→{last['clsbiz_rt']:.0f}%)")
        if last["stor_co"] > prev["stor_co"]:
            alerts.append(f"경쟁 심화(점포 {int(prev['stor_co'])}→{int(last['stor_co'])})")
        if last["sales_amt"] < prev["sales_amt"]:
            alerts.append("매출 감소")
        print("\n[트리거] " + (" / ".join(alerts) if alerts else "특이신호 없음(안정)"))
    print("※ 국면(성장/쇠퇴) 확률은 월별 유동인구 확보 시 활성화 — 현재는 분기 추세 기반.")


if __name__ == "__main__":
    main()
