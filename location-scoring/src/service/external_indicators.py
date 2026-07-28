"""
외부 API 지표(실거래가·주차장·건축물대장)를 상권 패널에 결합.

세 소스 모두 자치구/동 단위라, 상권의 (sigungu, adstrd)에
동명 매칭 → 실패 시 자치구 평균으로 폴백한다.

붙는 지표:
  rent           ㎡당 시세(원)        ← 실거래가   (입지경제성·점포가치·재무경제, 낮을수록↑)
  parking        주차면수             ← 주차장     (주차편리, 높을수록↑)
  bld_area       평균 연면적          ← 건축물대장 (점포특징, 높을수록↑)
  bld_comm_ratio 상업·근생 용도 비율  ← 건축물대장 (사업장, 높을수록↑)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.collectors.bldrgst import collect_gu
from src.collectors.molit_rtms import SEOUL_LAWD, build_rent_index, collect as collect_rtms
from src.collectors.parking import build_parking_index, collect as collect_parking

MONTHS = ["202501", "202502", "202503", "202504", "202505", "202506"]


def _norm_dong(s: pd.Series) -> pd.Series:
    """행정동 → 법정동 근사: '망원1동'→'망원동', '성산2동'→'성산동'."""
    return s.astype(str).str.replace(r"(\D+?)\d+(동|가)$", r"\1\2", regex=True)


def _join(panel: pd.DataFrame, dong_df: pd.DataFrame, gu_df: pd.DataFrame,
          gu_col: str, dong_col: str, value_cols: list[str]) -> pd.DataFrame:
    """동명(정규화) 매칭 → 자치구 평균 폴백."""
    d = dong_df.rename(columns={gu_col: "sigungu", dong_col: "dong"}).copy()
    d["dong"] = _norm_dong(d["dong"])
    d = d.groupby(["sigungu", "dong"], as_index=False)[value_cols].mean()
    g = gu_df.rename(columns={gu_col: "sigungu"})
    out = panel.copy()
    key = pd.DataFrame({"sigungu": out["sigungu"], "dong": _norm_dong(out["adstrd"])})
    merged = key.merge(d[["sigungu", "dong"] + value_cols], on=["sigungu", "dong"], how="left")
    fallback = key[["sigungu"]].merge(g[["sigungu"] + value_cols], on="sigungu", how="left")
    for c in value_cols:
        out[c] = merged[c].values
        out[c] = out[c].fillna(pd.Series(fallback[c].values, index=out.index))
    return out


def attach(panel: pd.DataFrame, sigungu: str | None = None) -> pd.DataFrame:
    """패널에 외부 지표 결합. sigungu 지정 시 그 구의 건축물대장까지 수집."""
    print("  (최초 실행은 공개데이터 다운로드로 수 분 소요됩니다. 이후엔 캐시로 즉시)", flush=True)
    # 1) 실거래가 → rent
    rtms = collect_rtms(MONTHS)
    if not rtms.empty:
        dong, gu = build_rent_index(rtms)
        dong = dong.rename(columns={"price_per_m2": "rent"})
        gu = gu.rename(columns={"price_per_m2": "rent"})
        panel = _join(panel, dong, gu, "sggNm", "umdNm", ["rent"])

    # 2) 주차장 → parking
    pk = collect_parking()
    if not pk.empty:
        dong, gu = build_parking_index(pk)
        dong = dong.rename(columns={"parking_slots": "parking"})
        gu = gu.rename(columns={"parking_slots": "parking"})
        panel = _join(panel, dong, gu, "sigungu", "dong", ["parking"])

    # 3) 건축물대장 → bld_* (요청 자치구만 수집, 나머지는 결측 → 자동 제외·재정규화)
    if sigungu and sigungu in SEOUL_LAWD:
        b = collect_gu(SEOUL_LAWD[sigungu], sigungu)
        if not b.empty:
            cols = ["bld_area", "bld_comm_ratio"]
            gu_avg = b[cols].mean().to_frame().T
            gu_avg["sigungu"] = sigungu
            panel = _join(panel, b, gu_avg, "sigungu", "dong", cols)
    return panel


if __name__ == "__main__":
    from src.service.industry_scoring import build_indicator_panel
    p = build_indicator_panel("분식전문점")
    p = attach(p, sigungu="마포구")
    mp = p[p["sigungu"] == "마포구"]
    print(f"마포구 상권 {len(mp)}개 — 외부지표 결합 결과 (일부)")
    print(mp[["trdar_cd_nm", "adstrd", "rent", "parking", "bld_area", "bld_comm_ratio"]]
          .head(10).to_string(index=False))
