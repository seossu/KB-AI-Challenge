"""
건축HUB 건축물대장 (data.go.kr) → 점포특징·사업장 지표.

건물 단위 데이터라 상권에 직접 못 붙임 → 법정동별로 표본 집계해 사용:
  bld_floor      평균 지상층수        (점포특징: 층수)
  bld_area       평균 연면적(㎡)      (점포특징: 전용면적 대리)
  bld_comm_ratio 상업/근생 용도 비율  (사업장: 주용도)
  bld_solo_ratio 단독건물(단독주택 등) 비율 (사업장: 단독건물 여부)

bjdongCd 가 필수라 자치구별로 후보 코드(10100~ step100)를 탐색하고,
법정동마다 표본 SAMPLE 건만 받아 평균낸다(전수는 과도).
"""

from __future__ import annotations

import os
import time
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # kb/ 를 import 경로에
from src.config import get_key

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "data" / "_cache"
URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"
UA = "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
SAMPLE = 300                       # 법정동당 표본 건수
COMM_KEYS = ("근린생활", "판매", "업무", "상업", "숙박", "위락")


def _key() -> str:
    return get_key("DATAGO_KEY")


def fetch_dong(sigungu_cd: str, bjdong_cd: str, key: str) -> list[dict]:
    try:
        r = requests.get(URL, params={"serviceKey": key, "sigunguCd": sigungu_cd,
                                      "bjdongCd": bjdong_cd, "numOfRows": SAMPLE,
                                      "pageNo": 1, "_type": "json"},
                         headers={"User-Agent": UA}, timeout=40).json()
    except Exception:
        return []
    body = r.get("response", {}).get("body") or {}
    items = (body.get("items") or {})
    if not items:
        return []
    it = items.get("item") if isinstance(items, dict) else items
    return it if isinstance(it, list) else [it]


def collect_gu(sigungu_cd: str, gu_name: str, cache_dir: Path | None = None,
               force: bool = False) -> pd.DataFrame:
    """자치구 하나의 법정동별 건축물 집계."""
    cache_dir = cache_dir or DEFAULT_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv = cache_dir / f"bldrgst_{sigungu_cd}.csv"
    if csv.exists() and not force:
        return pd.read_csv(csv)

    key, rows = _key(), []
    for code in range(10100, 13600, 100):        # 법정동 후보 탐색
        items = fetch_dong(sigungu_cd, f"{code:05d}", key)
        if not items:
            continue
        df = pd.DataFrame(items)
        floors = pd.to_numeric(df.get("grndFlrCnt"), errors="coerce")
        area = pd.to_numeric(df.get("totArea"), errors="coerce")
        purps = df.get("mainPurpsCdNm", pd.Series(dtype=str)).fillna("")
        rows.append({
            "sigungu": gu_name, "bjdongCd": f"{code:05d}",
            "dong": (df["platPlc"].str.extract(r"구\s+(\S+?[동가])")[0].mode().iat[0]
                     if "platPlc" in df and len(df["platPlc"].str.extract(r"구\s+(\S+?[동가])")[0].mode()) else None),
            "n": len(df),
            "bld_floor": float(floors.mean()) if floors.notna().any() else None,
            "bld_area": float(area.mean()) if area.notna().any() else None,
            "bld_comm_ratio": float(purps.str.contains("|".join(COMM_KEYS)).mean()),
            "bld_solo_ratio": float(purps.str.contains("단독").mean()),
        })
        time.sleep(0.1)

    out = pd.DataFrame(rows)
    out.to_csv(csv, index=False, encoding="utf-8-sig")
    return out


if __name__ == "__main__":
    d = collect_gu("11440", "마포구")
    print(f"마포구 법정동 {len(d)}개 집계")
    print(d[["dong", "n", "bld_floor", "bld_area", "bld_comm_ratio", "bld_solo_ratio"]]
          .sort_values("bld_comm_ratio", ascending=False).head(10).to_string(index=False))
