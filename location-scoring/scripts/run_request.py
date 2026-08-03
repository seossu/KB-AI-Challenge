"""
1팀 입력 JSON으로 입지 추천 실행.

실행:  python kb/scripts/run_request.py [입력json경로]
기본:  kb/data/team1_input.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.service.request_handler import recommend
from src.service.team1_adapter import adapt
from src.service.financial_profile import build_profile, format_profile

LABEL = {"transit": "교통", "vitality": "상권활력", "diversity": "업종다양성",
         "competition": "동종경쟁", "foot": "유동인구", "resident": "배후인구",
         "growth": "성장성", "school": "학교근접", "rent": "임대료",
         "parking": "주차면수", "bld_area": "건물연면적",
         "bld_comm_ratio": "상업용도비율", "supermarket": "대형마트"}


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "team1_input.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    req = adapt(raw)   # 1팀 JSON(감싸진 형태·문자열 capital·배열 region)도 수용

    print("=" * 70)
    print("입력 (1팀 JSON)")
    print("=" * 70)
    for k, v in req.items():
        if k.startswith("_"):
            continue
        print(f"  {k:<18}{v}")

    res = recommend(req)

    print("\n" + "=" * 70)
    print("입력 해석")
    print("=" * 70)
    print(f"  업종      : {req['business_type']} → 데이터업종 '{res['induty']}' → AHP '{res['ahp_industry'] or '없음(학습 경로)'}'")
    print(f"  지역      : {req['preferred_region']} → 자치구 '{res['sigungu']}'")
    print(f"  타깃연령   : {res['ages'] or '전체(미지정)'} → 유동인구 세그먼트")
    print(f"  가중치 출처 : {res['weight_source']}")
    print(f"  AHP 커버율 : {res['coverage']*100:.1f}%")

    print("\n가중치: AHP(base) → priority 재가중(final)")
    keys = sorted(set(res["weights_base"]) | set(res["weights_final"]),
                  key=lambda k: -res["weights_final"].get(k, 0))
    print(f"  {'지표':<14}{'base':>8}{'final':>8}")
    for k in keys:
        b = res["weights_base"].get(k, 0)
        f = res["weights_final"].get(k, 0)
        tag = " ←priority" if f > b + 1e-4 else ""
        print(f"  {LABEL.get(k,k):<14}{b:>8.3f}{f:>8.3f}{tag}")

    print("\n" + "=" * 70)
    print(f"추천 결과 (후보 {res['n_candidates']}곳 / 조건탈락 {len(res['filtered'])}곳 "
          f"/ 업종표본없음 {len(res['no_sample'])}곳)")
    print("=" * 70)
    for i, r in enumerate(res["rows"], 1):
        print(f"  {i}. {r['name']:<22}{r['score']:>6} 점")

    if res["rows"]:
        top = res["rows"][0]
        print(f"\n1위 [{top['name']}] 근거")
        for k, v in sorted(top["contrib"].items(), key=lambda x: -x[1]):
            print(f"    {LABEL.get(k,k):<14}백분위 {float(top['norm'][k]):>3.0f}%  기여 {v:>5.1f}")

        # ③④⑤ 금융 프로파일 (추천 1위 상권 기준)
        req_ctx = dict(req)
        req_ctx["_induty"] = res["induty"]
        req_ctx["_sigungu"] = res["sigungu"]
        req_ctx["_pyeong"] = req.get("store_size_pyeong")
        top_loc = {"name": top["name"], "sigungu": res["sigungu"],
                   "adstrd": top.get("adstrd")}
        profile = build_profile(req_ctx, top_loc)
        print("\n" + "=" * 70)
        print(format_profile(profile))
        print("=" * 70)
        gapf, gapo = profile["gap_facility"], profile["gap_operating"]
        if profile["affordability"] == "sufficient":
            print("→ 보유자금으로 충분. 금융추천 불필요.")
        elif profile["affordability"] == "over_budget":
            print(f"→ ⚠️ 부족자금 {profile['fund_gap']/1e4:,.0f}만 > 대출여력 "
                  f"{profile['loan_capacity']/1e4:,.0f}만 — 규모 축소나 저가 상권을 권장")
        else:
            need = []
            if gapf > 0:
                need.append(f"시설자금 {gapf/1e4:,.0f}만")
            if gapo > 0:
                need.append(f"운영자금 {gapo/1e4:,.0f}만")
            print(f"→ [⑥ 금융수요] {' + '.join(need)} 부족 (대출여력 내) → 금융상품 추천으로")

    if res["filtered"][:5]:
        print("\n하드필터 탈락 예시:")
        for f in res["filtered"][:5]:
            print(f"    {f['name']:<22}{', '.join(f['reasons'])}")


if __name__ == "__main__":
    main()
