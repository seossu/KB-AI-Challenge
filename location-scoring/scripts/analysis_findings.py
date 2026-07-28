"""
지금 보유한 실데이터(6종)로 계산 가능한 분석 결과 모음.

1) 매출(점포당 생산성) 결정요인 회귀 — 무엇이 '내 가게' 매출을 올리나
2) 생존 vs 매출 상충 — 같은 지표가 폐업/매출에 정반대로 작용하는지
3) 성수 상권 실측 프로파일 + 서울 전역 백분위

실행:  python kb/scripts/analysis_findings.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.real_multivariate import build_dataset, LABELS, Q_FEAT, Q_LABEL

# 생산성(점포당매출)은 분모에 점포수가 있으므로, 예측엔 '외부 입지지표'만 사용
# (점포수·유사업종수를 넣으면 기계적 공선성 → 계수 폭발).
CONTRAST = ["foot_2030", "working_pop", "residential", "infra",
            "transit", "seg2030_ratio", "pmdinner_ratio"]


def sec(t):
    print("\n" + "=" * 66 + f"\n{t}\n" + "=" * 66)


def main() -> None:
    m = build_dataset()
    cur = m[m["stdr_yyqu_cd"] == Q_LABEL].copy()
    cur["prod"] = cur["sales_amt"] / cur["stor_co"]          # 점포당 매출(생산성)

    # ---------- 1) 매출(생산성) 결정요인 ----------
    sec("1) 점포당 매출(생산성) 결정요인 — 무엇이 내 가게 매출을 올리나")
    rev = cur.dropna(subset=CONTRAST + ["prod"])
    rev = rev[rev["prod"] > 0]
    Xr = StandardScaler().fit_transform(rev[CONTRAST].values)
    yr = np.log(rev["prod"].values)
    r2 = cross_val_score(Ridge(alpha=1.0), Xr, yr, cv=5, scoring="r2").mean()
    coef = Ridge(alpha=1.0).fit(Xr, yr).coef_
    print(f"표본 {len(rev)}개 상권 · 5-fold R² = {r2:.3f}  (로그 점포당매출)")
    print(f"{'지표':<16}{'표준화영향(±1SD)':>16}")
    for i in np.argsort(-np.abs(coef)):
        print(f"{LABELS[CONTRAST[i]]:<16}{coef[i]:>+16.3f}")

    # ---------- 2) 생존 vs 매출 상충 ----------
    sec("2) 생존(폐업↓) vs 매출 — 같은 지표의 상반된 역할")
    q3 = m[m["stdr_yyqu_cd"] == Q_FEAT]
    q4 = m[m["stdr_yyqu_cd"] == Q_LABEL][["trdar_cd", "clsbiz_rt"]].rename(
        columns={"clsbiz_rt": "cls_q4"})
    s = q3.merge(q4, on="trdar_cd").dropna(subset=CONTRAST + ["cls_q4"])
    ys = (s["cls_q4"] <= s["cls_q4"].median()).astype(int).values   # 1=안정
    Xs = StandardScaler().fit_transform(s[CONTRAST].values)
    surv = LogisticRegression(C=1.0, max_iter=2000).fit(Xs, ys).coef_[0]
    print(f"{'지표':<16}{'생존기여':>10}{'매출기여':>10}   해석")
    for i in np.argsort(-np.abs(coef)):
        sv, rv = surv[i], coef[i]
        note = ""
        if sv < -0.05 and rv > 0.05:
            note = "← 매출엔 +, 생존엔 −  (전형적 트레이드오프)"
        elif sv > 0.05 and rv > 0.05:
            note = "← 둘 다 + (좋은 지표)"
        print(f"{LABELS[CONTRAST[i]]:<16}{sv:>+10.2f}{rv:>+10.2f}   {note}")
    print("\n※ '생존기여'는 로그오즈(+안정), '매출기여'는 로그 점포당매출 표준화계수.")

    # ---------- 3) 성수 상권 실측 프로파일 ----------
    sec("3) 성수 상권 실측 프로파일 (2025 4분기) + 서울 전역 백분위")
    def pr(col):  # 서울 전역 백분위(%)
        return (cur[col].rank(pct=True) * 100)
    cur["p_comp"] = pr("stor_co"); cur["p_foot"] = pr("foot_2030")
    cur["p_prod"] = pr("prod"); cur["p_work"] = pr("working_pop")
    ss = cur[cur["trdar_cd_nm"].astype(str).str.contains("성수", na=False)]
    ss = ss[ss["stor_co"] >= 5].sort_values("prod", ascending=False)
    print(f"{'상권':<15}{'점포':>4}{'폐업%':>6}{'유동인구':>8}{'직장인구':>8}"
          f"{'점포당매출':>10}{'생산성%':>7}")
    for _, r in ss.iterrows():
        print(f"{r['trdar_cd_nm']:<15}{int(r['stor_co']):>4}{r['clsbiz_rt']:>6.0f}"
              f"{int(r['foot_2030']):>8,}{int(r['working_pop']):>8,}"
              f"{r['prod']/1e4:>9,.0f}만{r['p_prod']:>6.0f}%")
    print("\n※ 생산성%=점포당 매출의 서울 전역 백분위. 유동인구·직장인구 많아도 점포당매출은 별개.")


if __name__ == "__main__":
    main()
