"""
산업별 AHP 가중치 기반 입지 스코어링.

구조:
  INDUSTRY_AHP   : 산업 → {AHP 기준: 가중치}   (1팀 AHP 결과)
  CRITERION_MAP  : AHP 기준 → (데이터 지표, 방향) | (None, 필요데이터)
  → 보유 지표로 매핑되는 기준만 남기고 가중치 재정규화
  → 최종점수 = Σ(백분위 × 재정규화 가중치)

가시성은 사용자 결정에 따라 유동인구(foot)에 포함.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.collectors.seoul_area import load_area
from src.collectors.seoul_golmok import load
from src.collectors.seoul_openapi import fetch

# ── 1팀 AHP 산업별 가중치 ─────────────────────────────────────────
INDUSTRY_AHP = {
    "카페":        {"접근성": .229, "상권환경": .374, "경쟁성": .19, "경쟁업체": .125, "점포특징": .083},
    "패밀리레스토랑": {"접근성": .375, "주변환경": .273, "경쟁환경": .105, "사업장": .185, "재무경제": .062},
    "베이커리":     {"접근성": .217, "주변환경": .149, "가시성": .229, "주차편리": .405},
    "편의점(서울)":  {"접근성": .122, "상권다양성": .136, "상권복합도": .078, "1인가구밀집도": .079,
                   "인구비율": .442, "유동인구": .022, "지역경제력": .121},
    "편의점(경남부산)": {"이면도로유형": .211, "경쟁점포수": .369, "대형마트수": .216, "거주인구": .204},
    "네일":        {"접근성": .476, "경쟁회피": .150, "성장가능성": .075, "입지경제성": .303},
    "학원":        {"접근성": .473, "주변환경": .527},
    "동물병원":     {"교통": .15, "경제.상권": .2, "경쟁환경": .05, "인구": .35, "주거특성": .25},
    "패스트푸드":    {"교통": .351, "접근성": .202, "주변상권": .174, "인구": .217, "가시성": .056},
    "태권도장":     {"교통": .339, "주변상권": .128, "경쟁환경": .014, "인구수요": .519},
    "해산물프랜차이즈": {"접근성": .388, "주변상권": .243, "동종점포": .037, "유동인구": .105,
                   "가시성": .074, "점포가치(비용)": .153},
    "대형할인점":    {"인접도로폭": .103, "경쟁업체수": .142, "총인구수": .098, "상권인구": .242, "부지": .171},
}

# 산업 → 데이터상의 업종명(동종 경쟁 계산용). None이면 경쟁 지표 사용 불가
INDUSTRY_INDUTY = {
    "카페": "커피-음료", "베이커리": "제과점", "편의점(서울)": "편의점",
    "편의점(경남부산)": "편의점", "네일": "네일숍", "학원": "일반교습학원",
    "동물병원": "동물병원", "패스트푸드": "패스트푸드점",
    "패밀리레스토랑": "양식음식점", "해산물프랜차이즈": "일식음식점",
    "태권도장": None, "대형할인점": None,
}

# AHP 기준 → (지표키, 방향) / 미보유는 (None, 필요데이터)
CRITERION_MAP = {
    # 교통·접근성
    "접근성": ("transit", "up"), "교통": ("transit", "up"),
    "이면도로유형": (None, "도로망 데이터"), "인접도로폭": (None, "도로망 데이터"),
    # 주변환경(상권 활력)
    "상권환경": ("vitality", "up"), "주변환경": ("vitality", "up"),
    "주변상권": ("vitality", "up"), "경제.상권": ("vitality", "up"),
    "상권다양성": ("diversity", "up"), "상권복합도": ("diversity", "up"),
    # 경쟁
    "경쟁성": ("competition", "down"), "경쟁업체": ("competition", "down"),
    "경쟁환경": ("competition", "down"), "경쟁회피": ("competition", "down"),
    "경쟁점포수": ("competition", "down"), "동종점포": ("competition", "down"),
    "경쟁업체수": ("competition", "down"), "대형마트수": ("supermarket", "down"),
    # 인구 (가시성 포함 — 사용자 결정)
    "인구": ("foot", "up"), "인구수요": ("foot", "up"), "유동인구": ("foot", "up"),
    "가시성": ("foot", "up"),
    "인구비율": ("resident", "up"), "총인구수": ("resident", "up"),
    "상권인구": ("resident", "up"), "거주인구": ("resident", "up"),
    "주거특성": ("resident", "up"),
    "1인가구밀집도": (None, "1인가구 데이터"),
    # 성장
    "성장가능성": ("growth", "up"),
    # 미보유 (외부 키/파일 필요)
    "점포특징": ("bld_area", "up"),          # 건축물대장 평균 연면적
    "사업장": ("bld_comm_ratio", "up"),      # 상업·근생 용도 비율
    "재무경제": ("rent", "down"),            # ㎡당 시세(낮을수록 유리)
    "입지경제성": ("rent", "down"),
    "점포가치(비용)": ("rent", "down"),
    "주차편리": ("parking", "up"),           # 주차면수
    "지역경제력": (None, "소득소비-상권(서울, 서비스명 미확인)"),
    "부지": (None, "토지이용계획정보(data.go.kr)"),
}

Q_CUR, Q_PREV = 20254, 20253


AGE_COL = {"10": "AGRDE_10_FLPOP_CO", "20": "AGRDE_20_FLPOP_CO",
           "30": "AGRDE_30_FLPOP_CO", "40": "AGRDE_40_FLPOP_CO",
           "50": "AGRDE_50_FLPOP_CO", "60": "AGRDE_60_ABOVE_FLPOP_CO"}


def build_indicator_panel(induty: str | None, quarter: int = Q_CUR,
                          sigungu: str | None = None,
                          ages: list[str] | None = None) -> pd.DataFrame:
    """상권 × 지표 원자료. induty = 해당 산업의 업종명(동종 경쟁용)."""
    store_all = load("store", induty=None, quarter=None)
    sales_all = load("sales", induty=None, quarter=None)

    cur_store = store_all[store_all["stdr_yyqu_cd"] == quarter]
    cur_sales = sales_all[sales_all["stdr_yyqu_cd"] == quarter]

    # 상권 활력 = 전 업종 매출 합 / 업종 다양성 = 업종 수
    vitality = cur_sales.groupby("trdar_cd")["sales_amt"].sum().rename("vitality")
    diversity = cur_store.groupby("trdar_cd")["svc_induty_cd_nm"].nunique().rename("diversity")
    names = cur_store.groupby("trdar_cd")["trdar_cd_nm"].first().rename("trdar_cd_nm")

    panel = pd.concat([names, vitality, diversity], axis=1)

    # 동종 경쟁·성장·생산성 (해당 업종)
    if induty:
        s = cur_store[cur_store["svc_induty_cd_nm"] == induty].set_index("trdar_cd")
        panel["competition"] = s["stor_co"]
        v = cur_sales[cur_sales["svc_induty_cd_nm"] == induty].set_index("trdar_cd")["sales_amt"]
        prev = sales_all[(sales_all["stdr_yyqu_cd"] == Q_PREV) &
                         (sales_all["svc_induty_cd_nm"] == induty)].set_index("trdar_cd")["sales_amt"]
        panel["growth"] = ((v - prev) / prev.replace(0, pd.NA)) * 100
        panel["productivity"] = v / s["stor_co"].replace(0, pd.NA)
    else:
        panel["competition"] = pd.NA
        panel["growth"] = pd.NA

    # API 지표
    def api(service, cols, name):
        d = fetch(service).rename(columns={"STDR_YYQU_CD": "q", "TRDAR_CD": "trdar_cd"})
        d = d[d["q"].astype(int) == quarter]
        d["trdar_cd"] = d["trdar_cd"].astype(int)
        return d.set_index("trdar_cd")[cols].sum(axis=1).rename(name)

    foot_cols = [AGE_COL[a] for a in ages if a in AGE_COL] if ages else ["TOT_FLPOP_CO"]
    panel["foot"] = api("VwsmTrdarFlpopQq", foot_cols or ["TOT_FLPOP_CO"], "foot")
    panel["resident"] = api("VwsmTrdarRepopQq", ["TOT_REPOP_CO"], "resident")
    panel["transit"] = api("VwsmTrdarFcltyQq", ["SUBWAY_STATN_CO", "BUS_STTN_CO"], "transit")
    panel["supermarket"] = api("VwsmTrdarFcltyQq", ["SUPMK_CO"], "supermarket")
    # 학교(초·중·고·대) — "학교 근처" 같은 사용자 조건용
    panel["school"] = api("VwsmTrdarFcltyQq",
                          ["ELESCH_CO", "MSKUL_CO", "HGSCHL_CO", "UNIV_CO"], "school")

    # 자치구·행정동 조인 (지역 질의용)
    area = load_area().set_index("trdar_cd")[["sigungu", "adstrd"]]
    panel = panel.join(area)

    # 외부 API 지표 결합 (실거래가 rent / 주차장 parking / 건축물대장 bld_*)
    from src.service.external_indicators import attach
    panel = attach(panel, sigungu=sigungu)
    return panel


def normalize(panel: pd.DataFrame, used: dict) -> pd.DataFrame:
    """used = {지표키: 방향} → 백분위(0~100, 방향통일)."""
    norm = pd.DataFrame(index=panel.index)
    norm["trdar_cd_nm"] = panel["trdar_cd_nm"]
    for key, direction in used.items():
        col = pd.to_numeric(panel[key], errors="coerce")
        pct = col.rank(pct=True) * 100
        norm[key] = (100 - pct) if direction == "down" else pct
    return norm


def resolve_weights(industry: str) -> tuple[dict, dict, list, float]:
    """AHP 가중치 → 사용가능 지표 가중치(재정규화), 방향, 미보유 목록, 커버리지."""
    ahp = INDUSTRY_AHP[industry]
    usable, directions, missing = {}, {}, []
    for crit, w in ahp.items():
        key, info = CRITERION_MAP.get(crit, (None, "매핑없음"))
        if key is None:
            missing.append((crit, w, info))
        else:
            usable[key] = usable.get(key, 0) + w   # 같은 지표에 매핑되면 합산
            directions[key] = info                 # info == 방향("up"/"down")
    coverage = sum(usable.values())                # 재정규화 전 = 커버된 가중치 비율
    weights = {k: v / (coverage or 1.0) for k, v in usable.items()}
    return weights, directions, missing, coverage


def score_industry(industry: str, region: str = "성수", min_store: int = 0,
                   panel: pd.DataFrame | None = None, sigungu: str | None = None) -> dict:
    induty = INDUSTRY_INDUTY.get(industry)
    weights, directions, missing, coverage = resolve_weights(industry)
    if panel is None:
        panel = build_indicator_panel(induty, sigungu=sigungu)
    norm = normalize(panel, directions)

    sel = norm["trdar_cd_nm"].astype(str).str.contains(region, na=False)
    if min_store:
        sel &= pd.to_numeric(panel["competition"], errors="coerce").fillna(0) >= min_store

    rows = []
    for idx in norm[sel].index:
        contrib = {k: weights[k] * float(norm.loc[idx, k])
                   for k in weights if pd.notna(norm.loc[idx, k])}
        if not contrib:
            continue
        rows.append({"name": norm.loc[idx, "trdar_cd_nm"],
                     "score": round(sum(contrib.values()), 1), "contrib": contrib})
    rows.sort(key=lambda r: -r["score"])
    return {"industry": industry, "induty": induty, "weights": weights,
            "missing": missing, "coverage": coverage, "rows": rows}
