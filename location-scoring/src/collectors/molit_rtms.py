"""
국토교통부 상업업무용 부동산 매매 실거래가 (data.go.kr).

용도: 임대료 대리지표(㎡당 시세) → 입지경제성·점포가치·재무경제 + 하드필터(자금 감당),
      덤으로 landUse(용도지역) → '부지' 기준 부분 대체.

집계: 자치구(sggCd) × 법정동(umdNm) 별 ㎡당 거래가 중앙값.
      상권에 붙일 때 행정동명 매칭 → 실패 시 자치구 중앙값으로 폴백.
키:   kb/.datago_key (환경변수 DATAGO_KEY 우선)
"""

from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # kb/ 를 import 경로에
from src.config import get_key

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "data" / "_cache"
URL = "https://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"

SEOUL_LAWD = {
    "종로구": "11110", "중구": "11140", "용산구": "11170", "성동구": "11200",
    "광진구": "11215", "동대문구": "11230", "중랑구": "11260", "성북구": "11290",
    "강북구": "11305", "도봉구": "11320", "노원구": "11350", "은평구": "11380",
    "서대문구": "11410", "마포구": "11440", "양천구": "11470", "강서구": "11500",
    "구로구": "11530", "금천구": "11545", "영등포구": "11560", "동작구": "11590",
    "관악구": "11620", "서초구": "11650", "강남구": "11680", "송파구": "11710",
    "강동구": "11740",
}
FIELDS = ["dealAmount", "buildingAr", "plottageAr", "landUse", "buildingUse",
          "umdNm", "sggNm", "sggCd", "dealYear", "dealMonth", "buildYear"]


def _key() -> str:
    return get_key("DATAGO_KEY")


def fetch_month(lawd_cd: str, ym: str, key: str | None = None) -> list[dict]:
    """자치구 × 월 실거래 목록."""
    key = key or _key()
    r = requests.get(URL, params={"serviceKey": key, "LAWD_CD": lawd_cd,
                                  "DEAL_YMD": ym, "numOfRows": 1000, "pageNo": 1},
                     headers={"User-Agent": UA}, timeout=40)
    r.raise_for_status()
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        return []
    if (root.findtext(".//resultCode") or "").strip() not in ("00", "000"):
        return []
    out = []
    for it in root.findall(".//item"):
        out.append({f: (it.findtext(f) or "").strip() for f in FIELDS})
    return out


def collect(months: list[str], gus: list[str] | None = None,
            cache_dir: Path | None = None, force: bool = False) -> pd.DataFrame:
    """서울 자치구 × 여러 월 수집 + 캐시."""
    cache_dir = cache_dir or DEFAULT_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{min(months)}_{max(months)}"
    csv = cache_dir / f"molit_nrg_{tag}.csv"
    if csv.exists() and not force:
        return pd.read_csv(csv)

    key = _key()
    gus = gus or list(SEOUL_LAWD)
    rows = []
    for gu in gus:
        for ym in months:
            try:
                rows += fetch_month(SEOUL_LAWD[gu], ym, key)
            except Exception:
                pass
            time.sleep(0.1)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["dealAmount"] = pd.to_numeric(df["dealAmount"].str.replace(",", ""), errors="coerce")
    df["buildingAr"] = pd.to_numeric(df["buildingAr"], errors="coerce")
    df = df[(df["dealAmount"] > 0) & (df["buildingAr"] > 0)]
    df["price_per_m2"] = df["dealAmount"] * 10_000 / df["buildingAr"]   # 원/㎡
    df.to_csv(csv, index=False, encoding="utf-8-sig")
    return df


def build_rent_index(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(법정동별, 자치구별) ㎡당 시세 중앙값 + 대표 용도지역."""
    dong = (df.groupby(["sggNm", "umdNm"])
              .agg(price_per_m2=("price_per_m2", "median"),
                   n=("price_per_m2", "size"),
                   landUse=("landUse", lambda s: s.mode().iat[0] if len(s.mode()) else None))
              .reset_index())
    gu = (df.groupby("sggNm")
            .agg(price_per_m2=("price_per_m2", "median"), n=("price_per_m2", "size"))
            .reset_index())
    return dong, gu


if __name__ == "__main__":
    months = ["202501", "202502", "202503", "202504", "202505", "202506"]
    d = collect(months)
    print(f"수집 {len(d)}건")
    dong, gu = build_rent_index(d)
    print("\n자치구별 ㎡당 시세(원) 상위:")
    print(gu.sort_values("price_per_m2", ascending=False).head(8).to_string(index=False))
    print("\n마포구 법정동별:")
    print(dong[dong["sggNm"].str.contains("마포", na=False)]
          .sort_values("price_per_m2", ascending=False).head(8).to_string(index=False))
