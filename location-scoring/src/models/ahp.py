"""
AHP (Analytic Hierarchy Process, Saaty 1980) 가중치 산출.

이론/문헌 기반 가중치: 평가기준 쌍대비교행렬 → 주고유벡터(정규화) = 가중치.
일관성비율 CR = CI/RI < 0.1 이면 판단이 일관됨(수용).

우리 스코어링(service.scoring)의 base_weights 로 그대로 투입 가능.
논문의 쌍대비교행렬(또는 최종 가중치)만 넣으면 됨.
"""

from __future__ import annotations

import numpy as np

# Saaty 무작위지수(RI): 행렬 크기 n별 기준값
RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24,
      7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


def ahp_weights(matrix, labels: list[str] | None = None) -> dict:
    """쌍대비교행렬 → 가중치 + 일관성 진단.

    matrix : n×n. a_ij = 기준 i가 j보다 몇 배 중요(Saaty 1~9, a_ji=1/a_ij).
    """
    A = np.asarray(matrix, dtype=float)
    n = A.shape[0]
    if A.shape[1] != n:
        raise ValueError("정방행렬이어야 합니다.")

    eigvals, eigvecs = np.linalg.eig(A)
    k = int(np.argmax(eigvals.real))
    w = np.abs(eigvecs[:, k].real)
    w = w / w.sum()
    lam_max = float(eigvals[k].real)

    ci = (lam_max - n) / (n - 1) if n > 1 else 0.0
    ri = RI.get(n, 1.49)
    cr = ci / ri if ri else 0.0

    labels = labels or [f"C{i}" for i in range(n)]
    return {
        "weights": {lab: round(float(wi), 4) for lab, wi in zip(labels, w)},
        "lambda_max": round(lam_max, 4),
        "CI": round(ci, 4),
        "CR": round(cr, 4),
        "consistent": cr < 0.10,
    }


def to_base_weights(ahp_result: dict, criteria_to_feature: dict) -> dict:
    """AHP 기준명 → 스코어링 피처키 매핑하여 base_weights dict 생성."""
    w = ahp_result["weights"]
    out = {feat: w[crit] for crit, feat in criteria_to_feature.items() if crit in w}
    total = sum(out.values()) or 1.0
    return {k: round(v / total, 4) for k, v in out.items()}


if __name__ == "__main__":
    # 예시(가짜 판단): 유동인구>임대료>경쟁>교통>배후인구 순으로 중요하다고 볼 때
    labels = ["유동인구", "임대료", "경쟁밀도", "교통", "배후인구"]
    M = [
        [1,   2,   3,   4,   5],
        [1/2, 1,   2,   3,   4],
        [1/3, 1/2, 1,   2,   3],
        [1/4, 1/3, 1/2, 1,   2],
        [1/5, 1/4, 1/3, 1/2, 1],
    ]
    r = ahp_weights(M, labels)
    for lab, wt in r["weights"].items():
        print(f"  {lab:<8}{wt:.3f}")
    print(f"CR = {r['CR']}  → {'일관성 OK' if r['consistent'] else '재검토 필요'}")
