"""
학습 가중치 (지도학습 ML) — 데이터_명세.md §2.3 확장.

지금까지 스코어링 가중치는 손으로 정한 값(BASE_WEIGHTS)이었다.
이 모듈은 과거 상권 데이터(피처 → 실제 '성공' 여부)로 로지스틱 회귀를 학습해,
각 지표가 성공에 기여한 정도(표준화 계수)를 데이터 기반 가중치로 환산한다.

  - 규칙기반 → ML 기반 승격: "가중치가 임의가 아니라 실증데이터로 학습됨"
  - 화이트박스(로지스틱): 설명가능 → 금감원/금융 맥락 가점
  - 백테스트 검증과 직결 (holdout AUC 리포트)

실서비스에서는 generate_training_data 를 소진공 과거 데이터(t 시점 피처 →
t+12개월 생존/매출 성공 라벨)로 교체하면 됨.
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.data.market_panel import FEATURES
from src.service.scoring import normalize

FEATURE_KEYS = [f["key"] for f in FEATURES]

# 합성 성공라벨 생성용 '실제(latent) 중요도'. 데모에서 직관과 어긋나게 설계:
# 유동인구는 생각보다 낮고, 폐업률·매출·경쟁이 생존에 더 결정적.
# (실데이터로 교체하면 이 값은 쓰이지 않음 — 순수 라벨 생성기 역할)
_TRUE_IMPORTANCE = {
    "foot_traffic": 0.10, "rent_per_m2": 0.12, "competition": 0.16,
    "closure_rate": 0.22, "sales_index": 0.20, "transit": 0.08,
    "infra": 0.06, "residential": 0.06,
}


def generate_training_data(n: int = 1500, seed: int = 7) -> pd.DataFrame:
    """과거 상권 패널(원자료) 합성. market_panel 분포와 동일 스케일."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "foot_traffic": rng.uniform(5_000, 60_000, n),
        "rent_per_m2": rng.uniform(30_000, 130_000, n),
        "competition": rng.uniform(0.5, 8.0, n),
        "closure_rate": rng.uniform(0.02, 0.20, n),
        "sales_index": rng.uniform(50, 150, n),
        "transit": rng.uniform(10, 100, n),
        "infra": rng.uniform(5, 200, n),
        "residential": rng.uniform(3_000, 40_000, n),
    })


def _success_labels(norm_df: pd.DataFrame, seed: int, signal: float = 2.2) -> np.ndarray:
    """정규화(방향통일) 피처에 latent 중요도를 걸어 성공확률 → 이진 라벨 샘플.

    실데이터에서는 이 함수 대신 실제 생존/매출 성공 라벨을 쓴다.
    """
    rng = np.random.default_rng(seed + 1)
    z = (norm_df[FEATURE_KEYS] - norm_df[FEATURE_KEYS].mean()) / norm_df[FEATURE_KEYS].std()
    w = np.array([_TRUE_IMPORTANCE[k] for k in FEATURE_KEYS])
    logit = signal * (z.values @ w) + rng.normal(0, 1.0, len(z))
    p = 1.0 / (1.0 + np.exp(-logit))
    return (rng.random(len(z)) < p).astype(int)


def learn_weights(training_raw: pd.DataFrame | None = None,
                  seed: int = 7, test_size: float = 0.3) -> dict:
    """로지스틱 회귀로 지표별 데이터 기반 가중치 학습.

    Returns dict: weights, coef, auc_holdout, success_rate, n
    """
    raw = generate_training_data(seed=seed) if training_raw is None else training_raw
    norm = normalize(raw)                       # 백분위 + 방향통일 (scoring과 동일)
    y = _success_labels(norm, seed=seed)

    X = norm[FEATURE_KEYS].values
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)

    Xtr, Xte, ytr, yte = train_test_split(Xs, y, test_size=test_size, random_state=seed)
    clf = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
    auc = roc_auc_score(yte, clf.predict_proba(Xte)[:, 1])

    coef = clf.coef_[0]
    # 계수 → 가중치: 방향통일된 피처라 양(+)이 기대됨. 음수는 0으로 클립 후 합=1 정규화.
    w = np.clip(coef, 0.0, None)
    if w.sum() == 0:
        w = np.abs(coef)
    w = w / w.sum()

    return {
        "weights": {k: round(float(wi), 4) for k, wi in zip(FEATURE_KEYS, w)},
        "coef": {k: round(float(c), 3) for k, c in zip(FEATURE_KEYS, coef)},
        "auc_holdout": round(float(auc), 3),
        "success_rate": round(float(y.mean()), 3),
        "n": int(len(y)),
    }


if __name__ == "__main__":
    r = learn_weights()
    print(f"n={r['n']}, 성공률={r['success_rate']}, holdout AUC={r['auc_holdout']}")
    print("학습 가중치:")
    for k, v in sorted(r["weights"].items(), key=lambda x: -x[1]):
        print(f"  {k:<14}{v:.3f}  (coef {r['coef'][k]:+.2f})")
