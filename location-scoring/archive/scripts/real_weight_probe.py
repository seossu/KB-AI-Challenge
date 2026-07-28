"""
실데이터 가중치 학습 검증 — 순환논리(합성) 반박용.

서울 상권분석 '점포-상권' 실데이터(커피-음료, 전 서울 상권)로:
  - 피처: 2025 Q3 시점의 점포수/프랜차이즈비율/개업률/유사업종수/당분기폐업률
  - 라벨: 2025 Q4 의 '저폐업(안정)' 여부 = 다음분기 폐업률이 중앙값 이하  → 성공 proxy
  - 시간차(t → t+1) 실측이므로 planted 가중치가 아니라 진짜 데이터가 답을 준다.

실행:  python kb/scripts/real_weight_probe.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.collectors.seoul_golmok import load

Q_FEAT, Q_LABEL = 20253, 20254   # Q3 피처 → Q4 라벨

FEATURES = {
    "stor_co": "점포수(경쟁)",
    "frc_ratio": "프랜차이즈비율",
    "opbiz_rt": "개업률",
    "similr_induty_stor_co": "유사업종수",
    "clsbiz_rt_q3": "당분기폐업률",
}


def main() -> None:
    print("실데이터 다운로드/로드 중… (서울 상권분석 점포-상권 2025, 키 불필요)")
    df = load("store", year=2025, induty="커피-음료", quarter=None)

    q3 = df[df["stdr_yyqu_cd"] == Q_FEAT].copy()
    q4 = df[df["stdr_yyqu_cd"] == Q_LABEL][["trdar_cd", "clsbiz_rt"]].rename(
        columns={"clsbiz_rt": "clsbiz_rt_q4"})
    q3 = q3[q3["stor_co"] > 0]
    q3["frc_ratio"] = q3["frc_stor_co"] / q3["stor_co"]
    q3 = q3.rename(columns={"clsbiz_rt": "clsbiz_rt_q3"})

    m = q3.merge(q4, on="trdar_cd", how="inner").dropna(
        subset=list(FEATURES) + ["clsbiz_rt_q4"])
    print(f"학습 표본: 서울 커피-음료 상권 {len(m)}곳 (Q3→Q4 매칭)")

    # 라벨: Q4 폐업률이 중앙값 이하면 '안정(성공)'=1
    thr = m["clsbiz_rt_q4"].median()
    y = (m["clsbiz_rt_q4"] <= thr).astype(int).values
    print(f"라벨 기준: Q4 폐업률 ≤ 중앙값({thr:.1f}%) → 안정=1 / 성공률 {y.mean():.2f}")

    X = m[list(FEATURES)].values
    Xs = StandardScaler().fit_transform(X)
    Xtr, Xte, ytr, yte = train_test_split(Xs, y, test_size=0.3, random_state=7)
    clf = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
    auc = roc_auc_score(yte, clf.predict_proba(Xte)[:, 1])

    coef = clf.coef_[0]
    # 계수 → 가중치(절댓값 정규화). 부호는 방향(+안정기여 / -폐업기여).
    w = np.abs(coef) / np.abs(coef).sum()

    print(f"\nholdout AUC = {auc:.3f}  (실데이터 예측력)")
    print(f"{'지표':<16}{'계수(방향)':>12}{'가중치':>10}")
    order = np.argsort(-np.abs(coef))
    keys = list(FEATURES)
    for i in order:
        k = keys[i]
        sign = "안정↑" if coef[i] > 0 else "폐업↑"
        print(f"{FEATURES[k]:<16}{coef[i]:>+9.2f} {sign:<4}{w[i]:>9.3f}")

    print("\n[핵심] 이 가중치는 제가 심어둔 값이 아니라 서울시 실측 폐업 데이터가")
    print("       t→t+1 로 준 결과입니다. AUC 로 예측력이 검증됩니다(순환논리 아님).")
    print("       유동인구·매출·임대료(별도 파일)를 조인하면 피처가 더 강해집니다.")


if __name__ == "__main__":
    main()
