"""
AHP가 없는 업종의 가중치를 실데이터로 학습 (4단 폴백의 마지막 단계).

방식: 그 업종의 '생존'을 예측하는 모델을 학습하고, 계수를 가중치로 환산.
  피처 = 우리 상권 지표(백분위)  ·  라벨 = 다음 분기 저폐업(안정) 여부
  L1 로지스틱 + 5-fold CV → 중복 지표 제거, 과적합 방지
  가중치 = |계수| 정규화 ,  방향 = 계수 부호(+ 안정기여 / − 폐업기여)

AHP(전문가 판단)가 없어도 데이터가 있으면 가중치를 만들 수 있어,
서울 상권분석의 100개 업종 전부를 커버할 수 있다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegressionCV
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.collectors.seoul_golmok import load
from src.service.industry_scoring import build_indicator_panel

Q_FEAT, Q_LABEL = 20253, 20254

# 학습에 쓸 지표 (업종 무관하게 항상 만들 수 있는 것들)
FEATURES = ["competition", "vitality", "diversity", "foot", "resident",
            "transit", "supermarket", "rent", "parking"]
LABEL = {"competition": "동종경쟁", "vitality": "상권활력", "diversity": "업종다양성",
         "foot": "유동인구", "resident": "배후인구", "transit": "교통",
         "supermarket": "대형마트", "rent": "임대료", "parking": "주차면수"}


def learn_weights(induty: str, min_samples: int = 100,
                  penalty: str = "l2") -> dict:
    """업종 하나의 가중치를 실데이터로 학습."""
    panel = build_indicator_panel(induty, quarter=Q_FEAT)

    # 라벨: 다음 분기 폐업률이 중앙값 이하 → '안정'
    store = load("store", induty=induty, quarter=Q_LABEL)
    nxt = store.set_index("trdar_cd")["clsbiz_rt"]

    d = panel.join(nxt.rename("cls_next"), how="inner")
    d = d[pd.to_numeric(d["competition"], errors="coerce").fillna(0) > 0]
    d = d.dropna(subset=FEATURES + ["cls_next"])
    if len(d) < min_samples:
        return {"induty": induty, "ok": False, "n": len(d),
                "reason": f"표본 부족({len(d)} < {min_samples})"}

    thr = d["cls_next"].median()
    y = (d["cls_next"] <= thr).astype(int).values
    if y.min() == y.max():                       # 라벨이 한쪽뿐이면 학습 불가
        return {"induty": induty, "ok": False, "n": len(d), "reason": "라벨 편중"}

    # 백분위 정규화 후 표준화 (스케일 이질성 제거)
    pct = d[FEATURES].rank(pct=True) * 100
    X = StandardScaler().fit_transform(pct.values)

    # L2(ridge): 지표를 남기되 기여도에 비례한 '등급화된' 가중치를 얻는다.
    # (L1은 경쟁밀도 하나만 남기고 다 제거해버려 다기준 가중치로 부적합)
    clf = LogisticRegressionCV(Cs=np.logspace(-2, 1, 10), cv=5, penalty=penalty,
                               solver="liblinear", scoring="roc_auc",
                               max_iter=3000).fit(X, y)
    best = int(np.argmin(np.abs(clf.Cs_ - clf.C_[0])))
    auc = float(clf.scores_[1].mean(axis=0)[best])
    coef = clf.coef_[0]

    total = np.abs(coef).sum()
    if total == 0:
        return {"induty": induty, "ok": False, "n": len(d), "reason": "유효 계수 없음"}

    weights, directions = {}, {}
    for f, c in zip(FEATURES, coef):
        if c == 0:
            continue                              # L1 이 제거한 지표
        weights[f] = float(abs(c) / total)
        directions[f] = "up" if c > 0 else "down"   # +면 클수록 안정 → up
    return {"induty": induty, "ok": True, "n": len(d), "auc": auc,
            "weights": weights, "directions": directions,
            "coef": {f: float(c) for f, c in zip(FEATURES, coef)}}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "PC방"
    r = learn_weights(target)
    print(f"=== [{target}] 실데이터 가중치 학습 ===")
    if not r["ok"]:
        print("실패:", r["reason"])
        sys.exit(0)
    print(f"표본 {r['n']}개 상권 · 5-fold CV AUC {r['auc']:.3f}")
    print(f"\n{'지표':<12}{'계수':>8}{'방향':>8}{'가중치':>9}")
    for f, w in sorted(r["weights"].items(), key=lambda x: -x[1]):
        c = r["coef"][f]
        print(f"{LABEL[f]:<12}{c:>+8.2f}{'클수록↑' if c>0 else '작을수록↑':>9}{w:>9.3f}")
    dropped = [LABEL[f] for f in FEATURES if r["coef"][f] == 0]
    if dropped:
        print(f"\n제거된 지표: {', '.join(dropped)}")
