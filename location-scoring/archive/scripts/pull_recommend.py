"""
Pull(입지추천) 엔드투엔드 — 실데이터 → AHP base → 사용자 우선순위 재가중 → 점수·랭킹.

흐름:
  build_pull_panel → normalize_pull(백분위)
  → reweight(AHP base + 사용자 우선순위)         [AHP는 지금 placeholder]
  → 임대료 결측 차원 제외 + 가중치 재정규화
  → Σ(백분위 × 가중치) → 성수 상권 랭킹 + 1위 근거

실행:  python kb/scripts/pull_recommend.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service.pull_criteria import build_pull_panel, normalize_pull, CRITERIA, KEYS
from src.service.reweight import reweight

NAME = {c["key"]: c["name"] for c in CRITERIA}

# ★★★★★ 나중에 1팀 AHP 결과로 이 딕셔너리만 교체 (합=1) ★★★★★
AHP_BASE_PLACEHOLDER = {
    "foot_2030": 0.20, "competition": 0.15, "closure": 0.15,
    "productivity": 0.20, "rent": 0.15, "transit": 0.08, "amenity": 0.07,
}
# ★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★★

# ── 사용자 입력 예시 (프론트/1팀이 넘겨줄 부분) ──
USER_PRIORITY = ["productivity", "foot_2030"]   # 1위 점포당매출, 2위 유동인구
USER_RANKED = True                               # 순위 있음 → 차등
USER_ALPHA = 0.35                                # 반영 강도(보통)


def score_row(norm_row: pd.Series, weights: dict) -> tuple[float, dict]:
    """결측(placeholder) 차원 제외 후 가중치 재정규화 → 점수 + 기여도."""
    avail = [k for k in KEYS if pd.notna(norm_row[k])]
    wsum = sum(weights[k] for k in avail) or 1.0
    contrib = {k: (weights[k] / wsum) * float(norm_row[k]) for k in avail}
    return round(sum(contrib.values()), 1), contrib


def main() -> None:
    raw = build_pull_panel()
    norm = normalize_pull(raw)

    # 1) AHP base + 사용자 우선순위 → 최종 가중치
    final_w = reweight(AHP_BASE_PLACEHOLDER, USER_PRIORITY, USER_RANKED, USER_ALPHA)

    print("=" * 64)
    print("가중치 결정")
    print("=" * 64)
    print(f"{'차원':<16}{'AHP(1팀,임시)':>12}{'재가중후':>10}")
    for k in KEYS:
        print(f"{NAME[k]:<16}{AHP_BASE_PLACEHOLDER[k]:>12.2f}{final_w[k]:>10.2f}")
    print(f"사용자 우선순위: {[NAME[p] for p in USER_PRIORITY]} "
          f"({'순위차등' if USER_RANKED else '등가중'}, α={USER_ALPHA})")
    print("※ 임대료는 데이터 미확보 → 점수계산 시 제외하고 나머지 6개로 재정규화")

    # 2) 성수 상권 스코어링
    ss = norm[norm["trdar_cd_nm"].astype(str).str.contains("성수", na=False)
              & (raw["competition"] >= 5)].copy()
    rows = []
    for _, nrow in ss.iterrows():
        sc, contrib = score_row(nrow, final_w)
        rows.append({"name": nrow["trdar_cd_nm"], "score": sc,
                     "contrib": contrib, "norm": nrow})
    rows.sort(key=lambda x: -x["score"])

    print("\n" + "=" * 64)
    print("성수동 입지 추천 (실데이터 6차원 + AHP·우선순위 가중)")
    print("=" * 64)
    for i, r in enumerate(rows, 1):
        print(f"  {i}. {r['name']:<15} {r['score']:>5} 점")

    # 3) 1위 근거 (기여도 분해)
    top = rows[0]
    print("\n" + "=" * 64)
    print(f"추천 1위 — {top['name']} ({top['score']}점) : 왜?")
    print("=" * 64)
    parts = sorted(top["contrib"].items(), key=lambda x: -x[1])
    for k, v in parts:
        print(f"  {NAME[k]:<16} 기여 {v:>5.1f}  (백분위 {float(top['norm'][k]):>3.0f}%)")
    print(f"\n  → 강점: {NAME[parts[0][0]]}. 약점: {NAME[parts[-1][0]]}.")


if __name__ == "__main__":
    main()
