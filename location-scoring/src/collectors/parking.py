"""
전국주차장정보 표준데이터 (data.go.kr) → 주차편리 지표.

18,000여 건 전국 주차장을 수집해 서울만 필터 → 자치구·동별 주차면수 집계.
(좌표가 있으나 상권 좌표는 TM 좌표계라 변환 없이 주소 기반으로 매칭)

지표: parking = 해당 동(없으면 자치구)의 총 주차구획수
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # kb/ 를 import 경로에
from src.config import get_key

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "data" / "_cache"
URL = "https://api.data.go.kr/openapi/tn_pubr_prkplce_info_api"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
PAGE = 1000

KEEP = ["prkplceNm", "prkplceSe", "prkplceType", "rdnmadr", "lnmadr",
        "prkcmprt", "latitude", "longitude"]


def _key() -> str:
    return get_key("DATAGO_KEY")


def collect(cache_dir: Path | None = None, force: bool = False) -> pd.DataFrame:
    """전국 수집 → 서울만 남겨 캐시."""
    cache_dir = cache_dir or DEFAULT_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv = cache_dir / "parking_seoul.csv"
    if csv.exists() and not force:
        return pd.read_csv(csv)

    key, rows, page = _key(), [], 1
    while True:
        r = requests.get(URL, params={"serviceKey": key, "pageNo": page,
                                      "numOfRows": PAGE, "type": "json"},
                         headers={"User-Agent": UA}, timeout=60).json()
        body = r["response"]["body"]
        items = body.get("items") or []
        if not items:
            break
        rows += items
        if page * PAGE >= int(body.get("totalCount", 0)):
            break
        page += 1

    df = pd.DataFrame(rows)
    df = df[[c for c in KEEP if c in df.columns]]
    addr = df["lnmadr"].fillna("") + " " + df["rdnmadr"].fillna("")
    df = df[addr.str.contains("서울", na=False)].copy()

    df["sigungu"] = addr[df.index].str.extract(r"(\S+구)\s")[0]
    df["dong"] = addr[df.index].str.extract(r"구\s+(\S+?[동가])\s")[0]
    df["prkcmprt"] = pd.to_numeric(df["prkcmprt"], errors="coerce").fillna(0)
    df.to_csv(csv, index=False, encoding="utf-8-sig")
    return df


def build_parking_index(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(동별, 자치구별) 주차면수 합계 + 주차장 수."""
    dong = (df.dropna(subset=["dong"]).groupby(["sigungu", "dong"])
              .agg(parking_slots=("prkcmprt", "sum"), lots=("prkcmprt", "size"))
              .reset_index())
    gu = (df.groupby("sigungu")
            .agg(parking_slots=("prkcmprt", "sum"), lots=("prkcmprt", "size"))
            .reset_index())
    return dong, gu


if __name__ == "__main__":
    d = collect()
    print(f"서울 주차장 {len(d)}개 / 총 주차면 {d['prkcmprt'].sum():,.0f}면")
    dong, gu = build_parking_index(d)
    print("\n자치구별 주차면수 상위:")
    print(gu.sort_values("parking_slots", ascending=False).head(8).to_string(index=False))
    print("\n마포구 동별:")
    print(dong[dong["sigungu"] == "마포구"].sort_values("parking_slots", ascending=False)
          .head(8).to_string(index=False))
