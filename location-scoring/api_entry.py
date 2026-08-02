"""
프론트엔드/백엔드용 JSON 진입점.

stdin 으로 입력 JSON(1팀 형식)을 받아 → 추천 결과를 stdout 으로 JSON 출력.
백엔드(Node) 가 이 스크립트를 spawn 해서 호출한다.

실행:
    echo '{"business_type":"학원","preferred_region":"대치동","capital":200000000}' \
        | python3 api_entry.py

출력(JSON):
    {
      "ok": true,
      "location": { "name","score","lat","lng","naverQuery","reasons":[...] },
      "candidates": [ {name,score}, ... ],
      "cost": { "required","capital","gap","gap_facility","gap_operating" },
      "financial_profile": { is_youth, credit_status, ... },   # 설문 있으면 반영
      "induty","ahp_industry","weight_source"
    }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.collectors.seoul_area import load_area          # 좌표(TM)→ 프론트용
from src.service.request_handler import recommend
from src.service.team1_adapter import adapt

# TM(중부원점) → WGS84 변환 (pyproj 없이 근사). 서울 범위에서 오차 수십 m.
# 정확도가 필요하면 pyproj 로 교체.
def _tm_to_wgs(x, y):
    # 간이 변환 계수(서울 국지 선형근사). x,y 는 EPSG:5181/5186 계열 좌표.
    try:
        x = float(x); y = float(y)
    except (TypeError, ValueError):
        return None, None
    lng = 126.9779 + (x - 198000.0) / 88000.0 * 1.0
    lat = 37.5663 + (y - 452000.0) / 111000.0 * 1.0
    if 37.3 < lat < 37.75 and 126.7 < lng < 127.25:
        return round(lat, 6), round(lng, 6)
    return None, None


def _coords_for(trdar_name, sigungu):
    """추천 상권명 → 좌표. seoul_area 의 TM 좌표를 WGS84 근사 변환."""
    try:
        area = load_area()
        row = area[area["trdar_cd_nm"] == trdar_name]
        if len(row):
            lat, lng = _tm_to_wgs(row["x"].iloc[0], row["y"].iloc[0])
            if lat:
                return lat, lng
    except Exception:
        pass
    return None, None


def run(req: dict) -> dict:
    req = adapt(req)
    res = recommend(req)

    rows = res.get("rows", [])
    if not rows:
        return {"ok": False, "reason": "추천 후보 없음 (조건에 맞는 상권을 찾지 못함)",
                "sigungu": res.get("sigungu"), "induty": res.get("induty")}

    LABEL = {"transit": "교통", "vitality": "상권활력", "competition": "동종경쟁",
             "foot": "유동인구", "resident": "배후인구", "growth": "성장성",
             "rent": "임대료", "parking": "주차", "bld_area": "건물규모",
             "supermarket": "대형마트", "school": "학교근접", "diversity": "업종다양성"}
    sigungu = res.get("sigungu")

    # 한 후보(row)를 프론트가 쓰는 완전한 입지객체로 변환 (좌표·상위3 이유 포함)
    def build_loc(row):
        la, ln = _coords_for(row["name"], sigungu)
        reasons = [{"label": LABEL.get(k, k), "pct": round(float(row["norm"].get(k, 0)))}
                   for k, _ in sorted(row["contrib"].items(), key=lambda x: -x[1])[:3]]
        return {"name": row["name"], "score": row["score"],
                "lat": la, "lng": ln, "naverQuery": row["name"], "reasons": reasons}

    top = rows[0]
    out = {
        "ok": True,
        "location": build_loc(top),                       # 1순위 (하위호환)
        "candidates": [build_loc(r) for r in rows[:3]],   # 1·2·3순위 (좌표·이유 포함)
        "induty": res.get("induty"), "ahp_industry": res.get("ahp_industry"),
        "weight_source": res.get("weight_source"), "sigungu": sigungu,
    }

    # 금융 프로파일(③④⑤) — 창업비용 계산은 상권 임대 시세 필요
    try:
        from src.service.financial_profile import build_profile
        ctx = dict(req)
        ctx["_induty"] = res.get("induty")
        ctx["_sigungu"] = res.get("sigungu")
        prof = build_profile(ctx, {"name": top["name"], "sigungu": res.get("sigungu"),
                                   "adstrd": top.get("adstrd")})
        out["cost"] = {
            "required": prof["required_fund"], "capital": prof["capital"],
            "gap": prof["fund_gap"], "gap_facility": prof["gap_facility"],
            "gap_operating": prof["gap_operating"],
        }
        out["financial_profile"] = {
            "is_youth": prof["is_youth"], "business_stage": prof["business_stage"],
            "loan_capacity": prof["loan_capacity"], "affordability": prof["affordability"],
        }
    except Exception as e:
        out["cost_error"] = str(e)[:120]

    return out


def main():
    raw = sys.stdin.read()
    try:
        req = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "reason": f"입력 JSON 파싱 실패: {e}"}, ensure_ascii=False))
        return
    try:
        result = run(req)
    except Exception as e:
        import traceback
        result = {"ok": False, "reason": str(e)[:200], "trace": traceback.format_exc()[-500:]}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
