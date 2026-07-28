"""
산업별 AHP 가중치 기반 입지 추천 실행.

실행:  python kb/scripts/industry_recommend.py [산업명] [자치구]
기본:  카페 성동구
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service.industry_scoring import (
    INDUSTRY_AHP, INDUSTRY_INDUTY, build_indicator_panel, normalize, resolve_weights,
)

LABEL = {"transit": "교통", "vitality": "상권활력", "diversity": "업종다양성",
         "competition": "동종경쟁", "supermarket": "대형마트", "foot": "유동인구",
         "resident": "배후인구", "growth": "성장성", "school": "학교근접",
         "rent": "임대료(㎡)", "parking": "주차면수",
         "bld_area": "건물연면적", "bld_comm_ratio": "상업용도비율"}


def coverage_report() -> None:
    print("=" * 70)
    print("산업별 AHP 가중치 커버리지")
    print("=" * 70)
    for ind in INDUSTRY_AHP:
        _, _, missing, cov = resolve_weights(ind)
        miss = ", ".join(f"{c}({w})" for c, w, _ in missing) or "—"
        print(f"{ind:<16}{cov*100:>6.1f}%  {miss}")


def main() -> None:
    industry = sys.argv[1] if len(sys.argv) > 1 else "카페"
    gu = sys.argv[2] if len(sys.argv) > 2 else "성동구"

    coverage_report()

    weights, directions, missing, cov = resolve_weights(industry)
    print("\n" + "=" * 70)
    print(f"[{industry}] @ {gu}   (업종='{INDUSTRY_INDUTY.get(industry)}', 커버율 {cov*100:.1f}%)")
    print("=" * 70)
    print("AHP 기준 → 지표 매핑:")
    for c, w in INDUSTRY_AHP[industry].items():
        key = None if any(cc == c for cc, _, _ in missing) else "✅"
        note = next((i for cc, _, i in missing if cc == c), "")
        print(f"  {c:<14}{w:>6.3f}  {key or '❌ ' + note}")
    print("\n재정규화 가중치:")
    for k, w in sorted(weights.items(), key=lambda x: -x[1]):
        print(f"  {LABEL.get(k,k):<14}{w:>6.3f}")

    panel = build_indicator_panel(INDUSTRY_INDUTY.get(industry), sigungu=gu)
    norm = normalize(panel, directions)
    norm["sigungu"] = panel["sigungu"]
    sel = (norm["sigungu"] == gu) & (pd.to_numeric(panel["competition"],
                                                   errors="coerce").fillna(0) >= 3)

    rows = []
    for idx in norm[sel].index:
        contrib = {k: weights[k] * float(norm.loc[idx, k])
                   for k in weights if pd.notna(norm.loc[idx, k])}
        if not contrib:
            continue
        used = sum(weights[k] for k in contrib)
        rows.append({"name": norm.loc[idx, "trdar_cd_nm"],
                     "score": round(sum(contrib.values()) / (used or 1), 1),
                     "contrib": contrib, "norm": norm.loc[idx]})
    rows.sort(key=lambda r: -r["score"])

    print("\n" + "=" * 70)
    print(f"{gu} [{industry}] 입지 추천 (후보 {len(rows)}곳)")
    print("=" * 70)
    for i, r in enumerate(rows[:8], 1):
        print(f"  {i}. {r['name']:<22}{r['score']:>6} 점")

    if rows:
        top = rows[0]
        print(f"\n1위 [{top['name']}] 근거 (지표 백분위):")
        for k, v in sorted(top["contrib"].items(), key=lambda x: -x[1]):
            print(f"  {LABEL.get(k,k):<14}{float(top['norm'][k]):>5.0f}%  기여 {v:>5.1f}")


if __name__ == "__main__":
    main()
