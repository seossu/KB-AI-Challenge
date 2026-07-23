"""
Pull(입지추천) 데이터 설계 — 7개 평가 차원.

각 차원 = 대표지표 1개 (차원 중복 없음, 주제 요건 전부 커버).
가중치는 AHP(1팀)+사용자 우선순위(reweight)로 오므로, 지표를 많이 써도
과적합 없음(fitting 아님). 여기선 상권별 원자료(raw)만 조립·정규화.

파이프라인: build_pull_panel() → normalize_pull() → reweight → Σ(백분위×가중치)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.real_multivariate import build_dataset

# 7개 평가 차원 정의. dir: up=높을수록 좋음 / down=낮을수록 좋음(정규화때 반전)
CRITERIA = [
    {"key": "foot_2030",    "name": "유동인구(20-30대)", "dim": "수요",   "dir": "up",   "status": "real"},
    {"key": "competition",  "name": "경쟁밀도",          "dim": "경쟁",   "dir": "down", "status": "real"},
    {"key": "closure",      "name": "폐업률",            "dim": "안정성", "dir": "down", "status": "real"},
    {"key": "productivity", "name": "점포당매출",        "dim": "수익",   "dir": "up",   "status": "real"},
    {"key": "rent",         "name": "임대료",            "dim": "비용",   "dir": "down", "status": "placeholder"},
    {"key": "transit",      "name": "교통",              "dim": "접근성", "dir": "up",   "status": "real"},
    {"key": "amenity",      "name": "생활인프라",        "dim": "편의",   "dir": "up",   "status": "real"},
]
KEYS = [c["key"] for c in CRITERIA]


def build_pull_panel(quarter: int = 20254) -> pd.DataFrame:
    """서울 전역 상권 × 7차원 원자료 패널 (정규화의 기준 분포이자 후보 소스)."""
    m = build_dataset()
    cur = m[m["stdr_yyqu_cd"] == quarter].copy()

    panel = pd.DataFrame(index=cur.index)
    panel["trdar_cd_nm"] = cur["trdar_cd_nm"]
    panel["foot_2030"]    = cur["foot_2030"]
    panel["competition"]  = cur["stor_co"]
    panel["closure"]      = cur["clsbiz_rt"]
    panel["productivity"] = cur["sales_amt"] / cur["stor_co"]
    panel["rent"]         = pd.NA                       # 국토부 키 확보 시 채움
    panel["transit"]      = cur["transit"]
    panel["amenity"]      = cur["infra"]
    return panel


def normalize_pull(panel: pd.DataFrame) -> pd.DataFrame:
    """서울 전역 대비 백분위(0~100), 방향 통일(down은 100-p). placeholder는 NaN 유지."""
    norm = pd.DataFrame(index=panel.index)
    norm["trdar_cd_nm"] = panel["trdar_cd_nm"]
    for c in CRITERIA:
        col = panel[c["key"]]
        if col.isna().all():                            # placeholder(임대료)
            norm[c["key"]] = pd.NA
            continue
        pct = col.rank(pct=True) * 100
        norm[c["key"]] = (100 - pct) if c["dir"] == "down" else pct
    return norm


if __name__ == "__main__":
    raw = build_pull_panel()
    norm = normalize_pull(raw)
    ss = raw["trdar_cd_nm"].astype(str).str.contains("성수", na=False) & (raw["competition"] >= 5)
    names = raw[ss]["trdar_cd_nm"]

    print(f"활성 지표: {[c['name'] for c in CRITERIA if c['status']=='real']}")
    print(f"placeholder: {[c['name'] for c in CRITERIA if c['status']!='real']}\n")
    print("성수 상권 — 원자료 / (백분위)")
    hdr = f"{'상권':<15}" + "".join(f"{c['name'][:6]:>9}" for c in CRITERIA)
    print(hdr)
    for idx in names.index:
        r, n = raw.loc[idx], norm.loc[idx]
        cells = ""
        for c in CRITERIA:
            if c["status"] != "real":
                cells += f"{'-':>9}"
            elif c["key"] == "productivity":
                cells += f"{r[c['key']]/1e4:>6,.0f}만"
            else:
                cells += f"{r[c['key']]:>9,.0f}"
        print(f"{raw.loc[idx,'trdar_cd_nm']:<15}{cells}")
        pcts = "".join(f"{n[c['key']]:>8.0f}%" if c['status']=='real' else f"{'-':>9}" for c in CRITERIA)
        print(f"{'  →백분위':<15}{pcts}")
