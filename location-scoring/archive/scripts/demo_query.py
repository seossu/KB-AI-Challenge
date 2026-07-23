"""
자연어 질의 → 입지 추천 데모.

예: "마포구에 분식점을 하나 차릴거야. 학교 근처이면 좋겠다"

흐름:
  [1] 자연어 파싱(LLM 역할)  → 지역/업종/우선순위
  [2] 업종 → AHP 산업 매핑    → 없으면 유사 산업 폴백
  [3] AHP 가중치 + 사용자 우선순위 볼록결합 재가중
  [4] 해당 자치구 상권 스코어링
  [5] Top-N + 기여도 근거

실행:  python kb/scripts/demo_query.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service.industry_scoring import (
    INDUSTRY_AHP, build_indicator_panel, normalize, resolve_weights,
)

LABEL = {"transit": "교통", "vitality": "상권활력", "diversity": "업종다양성",
         "competition": "동종경쟁", "supermarket": "대형마트", "foot": "유동인구",
         "resident": "배후인구", "growth": "성장성", "school": "학교근접"}

# 업종 → AHP 산업 폴백 매핑 (AHP 표에 없는 업종은 유사 산업 차용)
INDUTY_TO_AHP_FALLBACK = {
    "분식전문점": ("패스트푸드", "유사 매핑: 저가·고회전 외식업"),
    "치킨전문점": ("패스트푸드", "유사 매핑: 저가·고회전 외식업"),
    "한식음식점": ("패밀리레스토랑", "유사 매핑: 일반 외식업"),
    "슈퍼마켓": ("편의점(서울)", "유사 매핑: 생활 소매"),
    "미용실": ("네일", "유사 매핑: 미용 서비스"),
}

QUERY = "마포구에 분식점을 하나 차릴거야. 학교 근처이면 좋겠다"

# [1] 자연어 파싱 결과 (실서비스에선 LLM이 수행)
PARSED = {
    "sigungu": "마포구",
    "induty": "분식전문점",          # 데이터 업종 100개 중 하나로 정규화
    "priority": ["school"],          # "학교 근처" → 학교근접 지표
    "alpha": 0.35,                   # 우선순위 반영 강도
}


def main() -> None:
    print("=" * 70)
    print(f'사용자 입력: "{QUERY}"')
    print("=" * 70)

    # [1] 파싱
    print("\n[1] 자연어 파싱 (LLM)")
    print(f"    지역     : {PARSED['sigungu']}")
    print(f"    업종     : 분식점 → 데이터 업종 '{PARSED['induty']}'")
    print(f"    우선순위  : '학교 근처' → 지표 '학교근접' (α={PARSED['alpha']})")

    # [2] 업종 → AHP 산업
    ahp_ind, reason = INDUTY_TO_AHP_FALLBACK[PARSED["induty"]]
    print("\n[2] AHP 산업 매핑")
    print(f"    '{PARSED['induty']}'은 AHP 12개 산업에 없음 → 폴백")
    print(f"    → '{ahp_ind}' 가중치 차용  ({reason})")

    # [3] 가중치: AHP → 사용가능 지표 재정규화 → 사용자 우선순위 볼록결합
    weights, directions, missing, cov = resolve_weights(ahp_ind)
    print(f"\n[3] 가중치 결정  (AHP 커버율 {cov*100:.1f}%)")
    print(f"    AHP({ahp_ind}) 기반:")
    for k, w in sorted(weights.items(), key=lambda x: -x[1]):
        print(f"      {LABEL.get(k,k):<10}{w:>6.3f}")

    a = PARSED["alpha"]
    pref = {p: 1.0 / len(PARSED["priority"]) for p in PARSED["priority"]}
    final = {k: (1 - a) * w for k, w in weights.items()}
    for k, v in pref.items():                       # 새 지표(학교)도 편입 가능
        final[k] = final.get(k, 0.0) + a * v
    directions.setdefault("school", "up")
    print(f"    + 사용자 우선순위 볼록결합 (α={a}) → 최종:")
    for k, w in sorted(final.items(), key=lambda x: -x[1]):
        tag = " ←사용자" if k in pref else ""
        print(f"      {LABEL.get(k,k):<10}{w:>6.3f}{tag}")

    # [4] 해당 자치구 상권 스코어링
    panel = build_indicator_panel(PARSED["induty"])
    norm = normalize(panel, directions)
    norm["sigungu"] = panel["sigungu"]
    sel = norm["sigungu"] == PARSED["sigungu"]
    sel &= pd.to_numeric(panel["competition"], errors="coerce").fillna(0) >= 3  # 표본 최소

    rows = []
    for idx in norm[sel].index:
        contrib = {k: final[k] * float(norm.loc[idx, k])
                   for k in final if pd.notna(norm.loc[idx, k])}
        if contrib:
            rows.append({"name": norm.loc[idx, "trdar_cd_nm"],
                         "score": round(sum(contrib.values()), 1),
                         "contrib": contrib,
                         "stores": panel.loc[idx, "competition"],
                         "school": panel.loc[idx, "school"]})
    rows.sort(key=lambda r: -r["score"])

    print(f"\n[4] {PARSED['sigungu']} 상권 스코어링 — 분식전문점 3곳 이상 상권 {len(rows)}개")
    print("\n" + "=" * 70)
    print(f"추천 결과 (Top 5)")
    print("=" * 70)
    print(f"{'순위':<4}{'상권':<20}{'점수':>6}{'분식점수':>9}{'학교수':>7}")
    for i, r in enumerate(rows[:5], 1):
        print(f"{i:<4}{r['name']:<20}{r['score']:>6}{int(r['stores']):>9}{int(r['school']):>7}")

    # [5] 1위 근거
    if rows:
        top = rows[0]
        print(f"\n[5] 1위 [{top['name']}] 추천 근거")
        for k, v in sorted(top["contrib"].items(), key=lambda x: -x[1]):
            print(f"    {LABEL.get(k,k):<10} 기여 {v:>5.1f}  (백분위 {float(norm.loc[[i for i in norm[sel].index if norm.loc[i,'trdar_cd_nm']==top['name']][0], k]):>3.0f}%)")


if __name__ == "__main__":
    main()
