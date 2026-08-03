"""
1팀 입력 JSON → 입지 추천 (엔드투엔드 핸들러).

입력 예:
{
  "purpose":"창업", "business_type":"카페", "capital":200000000,
  "preferred_region":"성수동", "target_customer":"20~30대 직장인",
  "priority":["유동인구","낮은 임대료"], "store_size":"20평",
  "parking":true, "public_transport":true
}

필드 처리:
  business_type      → 데이터업종 + AHP 산업 (없으면 유사산업 폴백)
  preferred_region   → 자치구 / 행정동 / 상권명 순으로 해석
  target_customer    → 연령대 유동인구 세그먼트 (NULL이면 전체)
  priority           → 지표로 매핑 후 AHP 가중치와 볼록결합 재가중
  capital+store_size → 초기자금 추정(임대료 기반) 하드필터
  parking            → 주차면수 0 제외
  public_transport   → 교통 접점 0 제외
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.collectors.molit_rtms import SEOUL_LAWD
from src.collectors.seoul_area import load_area
from src.service.industry_scoring import (
    INDUSTRY_AHP, INDUSTRY_INDUTY, build_indicator_panel, normalize, resolve_weights,
)
from src.models.industry_weight_learner import learn_weights as _learn
from src.service.reweight import reweight
from src.service.team1_adapter import adapt

# 업종(데이터 100종) → AHP 산업 폴백
INDUTY_TO_AHP = {
    "커피-음료": "카페", "제과점": "베이커리", "편의점": "편의점(서울)",
    "패스트푸드점": "패스트푸드", "네일숍": "네일", "동물병원": "동물병원",
    "일반교습학원": "학원", "외국어학원": "학원", "양식음식점": "패밀리레스토랑",
    "일식음식점": "해산물프랜차이즈",
    # 유사 매핑
    "분식전문점": "패스트푸드", "치킨전문점": "패스트푸드",
    "한식음식점": "패밀리레스토랑", "중식음식점": "패밀리레스토랑",
    "호프-간이주점": "패밀리레스토랑", "슈퍼마켓": "편의점(서울)",
    "미용실": "네일", "피부관리실": "네일",
}
BUSINESS_TO_INDUTY = {
    "카페": "커피-음료", "분식점": "분식전문점", "베이커리": "제과점", "빵집": "제과점",
    "편의점": "편의점", "치킨집": "치킨전문점", "네일샵": "네일숍",
    "학원": "일반교습학원", "동물병원": "동물병원", "미용실": "미용실",
    "PC방": "PC방", "피시방": "PC방", "노래방": "노래방",
    "세탁소": "세탁소", "호프집": "호프-간이주점", "술집": "호프-간이주점",
}

# priority 라벨 → 지표키 (★ '???' 였던 부분)
PRIORITY_MAP = {
    "유동인구": "foot", "인구": "foot",
    "낮은 임대료": "rent", "임대료": "rent", "저렴한 임대료": "rent",
    "낮은 경쟁": "competition", "경쟁": "competition", "낮은 경쟁밀도": "competition",
    "교통": "transit", "교통접근성": "transit", "대중교통": "transit",
    "배후인구": "resident", "주거": "resident",
    "주차": "parking", "주차편리": "parking",
    "상권활력": "vitality", "학교": "school", "성장성": "growth",
}
PYEONG_M2 = 3.3058
CAP_RATE = 0.04          # 매매가 대비 연 임대수익률 가정 → 월세 환산
FITOUT_PER_PYEONG = 3_000_000


def parse_ages(target_customer: str | None) -> list[str] | None:
    """'20~30대 직장인' → ['20','30'] / None이면 전체 연령."""
    if not target_customer:
        return None
    ages = re.findall(r"(\d0)", target_customer)
    return ages or None


def parse_pyeong(store_size) -> float | None:
    if store_size is None:
        return None
    if isinstance(store_size, (int, float)):
        return float(store_size)
    m = re.search(r"(\d+(?:\.\d+)?)", str(store_size))
    return float(m.group(1)) if m else None


def resolve_region(region: str, area: pd.DataFrame) -> tuple[str | None, pd.Series]:
    """지역명 → (자치구, 상권 선택 마스크). 자치구 > 행정동 > 상권명 순."""
    if region in SEOUL_LAWD:
        return region, area["sigungu"] == region
    base = re.sub(r"(\d+가?)?동$", "", region)          # '성수동'→'성수'
    m = area["adstrd"].astype(str).str.startswith(base)
    if m.any():
        gu = area.loc[m, "sigungu"].mode()
        return (gu.iat[0] if len(gu) else None), m
    m = area["trdar_cd_nm"].astype(str).str.contains(region, na=False)
    gu = area.loc[m, "sigungu"].mode()
    return (gu.iat[0] if len(gu) else None), m


def estimate_initial_cost(rent_per_m2: float, pyeong: float) -> dict:
    """매매 ㎡시세 → 월세 환산 → 초기자금 추정."""
    area_m2 = pyeong * PYEONG_M2
    monthly = rent_per_m2 * area_m2 * CAP_RATE / 12
    deposit, key_money, opex = monthly * 10, monthly * 12, monthly * 3
    fitout = pyeong * FITOUT_PER_PYEONG
    return {"monthly": monthly, "deposit": deposit, "key_money": key_money,
            "fitout": fitout, "opex": opex,
            "total": deposit + key_money + fitout + opex}


def recommend(req: dict, alpha: float = 0.35, top_n: int = 5,
              min_store: int = 1) -> dict:
    """min_store: 해당 업종 점포가 이 수 미만인 상권은 후보 제외.
    (업종이 아예 없는 곳은 '경쟁 없어 좋은 곳'이 아니라 '수요 없는 곳'일 수 있고,
     경쟁 지표가 NaN 이 되어 점수가 부풀려지므로 검증 불가로 간주)"""
    req = adapt(req)   # 1팀 JSON({extracted_data,...}·문자열 capital·배열 region) 정규화
    induty = BUSINESS_TO_INDUTY.get(req["business_type"], req["business_type"])
    ahp_ind = INDUTY_TO_AHP.get(induty)
    ages = parse_ages(req.get("target_customer"))
    # 평수: store_size_pyeong(대화형·설문형) 우선, 없으면 store_size(문자열) 파싱
    pyeong = parse_pyeong(req.get("store_size_pyeong") if req.get("store_size_pyeong") is not None
                          else req.get("store_size"))

    area = load_area()
    gu, region_mask = resolve_region(req["preferred_region"], area)
    trdar_ids = set(area.loc[region_mask, "trdar_cd"].dropna().astype(int))

    # 가중치 출처 결정: ① AHP 문헌 ② 실데이터 학습 ③ 균등 가중치 최종 폴백
    is_fallback = False
    fallback_reason = None
    if ahp_ind:
        weights, directions, missing, cov = resolve_weights(ahp_ind)
        wsource = f"AHP 문헌 ({ahp_ind})"
    else:
        lr = _learn(induty)
        if lr.get("ok"):
            weights = dict(lr["weights"])
            directions = dict(lr["directions"])
            missing, cov = [], 1.0
            wsource = f"실데이터 학습 (표본 {lr['n']}개 상권, CV AUC {lr['auc']:.3f})"
        else:                                    # 학습도 실패 → 균등 폴백
            keys = ["competition", "vitality", "foot", "resident", "transit"]
            weights = {k: 1 / len(keys) for k in keys}
            directions = {"competition": "down", "vitality": "up", "foot": "up",
                          "resident": "up", "transit": "up"}
            missing, cov = [], 0.0
            is_fallback = True
            fallback_reason = lr.get("reason", "학습 불가")
            wsource = f"균등 가중 폴백 ({fallback_reason})"
    prios = [PRIORITY_MAP[p] for p in (req.get("priority") or []) if p in PRIORITY_MAP]
    final = reweight(weights, prios, ranked=True, alpha=alpha) if prios else weights
    for p in prios:
        directions.setdefault(p, "down" if p == "rent" else "up")

    panel = build_indicator_panel(induty, sigungu=gu, ages=ages)
    norm = normalize(panel, directions)

    rows, filtered, no_sample = [], [], []
    for idx in panel.index:
        if int(idx) not in trdar_ids:
            continue
        p = panel.loc[idx]
        reasons = []
        # AHP/학습 모델은 업종 표본이 있어야 검증 가능하다. 균등 폴백에서는 이
        # 필터를 해제해, 업종 데이터가 없는 롱테일 입력도 범용 지표로 추천한다.
        n_store = pd.to_numeric(pd.Series([p.get("competition")]),
                                errors="coerce").fillna(0).iat[0]
        if not is_fallback and n_store < min_store:
            no_sample.append(p["trdar_cd_nm"])
            continue
        # 하드필터
        if req.get("parking") and not (pd.notna(p.get("parking")) and p["parking"] > 0):
            reasons.append("주차 없음")
        if req.get("public_transport") and not (pd.notna(p.get("transit")) and p["transit"] > 0):
            reasons.append("대중교통 없음")
        cost = None
        if pyeong and pd.notna(p.get("rent")):
            cost = estimate_initial_cost(float(p["rent"]), pyeong)
            # ※ 자금 부족은 하드필터 대상이 아님 — ⑤부족자금→⑥금융추천에서 대출로 메꿈.
            #    입지 자체가 부적합한 조건(주차·교통·평수)만 여기서 탈락시킨다.
        if reasons:
            filtered.append({"name": p["trdar_cd_nm"], "reasons": reasons})
            continue
        contrib = {k: final[k] * float(norm.loc[idx, k])
                   for k in final if k in norm and pd.notna(norm.loc[idx, k])}
        if not contrib:
            continue
        used = sum(final[k] for k in contrib) or 1
        rows.append({"name": p["trdar_cd_nm"], "score": round(sum(contrib.values()) / used, 1),
                     "contrib": contrib, "cost": cost, "norm": norm.loc[idx],
                     "adstrd": p.get("adstrd")})
    rows.sort(key=lambda r: -r["score"])
    return {"induty": induty, "ahp_industry": ahp_ind, "weight_source": wsource,
            "is_fallback": is_fallback, "fallback_reason": fallback_reason,
            "sigungu": gu, "ages": ages,
            "coverage": cov, "weights_base": weights, "weights_final": final,
            "rows": rows[:top_n], "filtered": filtered, "no_sample": no_sample,
            "n_candidates": len(rows)}
