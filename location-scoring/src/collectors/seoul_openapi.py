"""
서울 열린데이터광장 OpenAPI 수집기 (상권 단위 유동인구·배후인구 등).

키가 필요한 데이터셋용 (파일 다운로드 안 되는 계열).
키는 소스에 박지 않고 환경변수 SEOUL_API_KEY 또는 kb/.seoul_key 파일에서 읽음.

주요 서비스:
  VwsmTrdarFlpopQq : 길단위인구-상권 (유동인구). 연령대·시간대·요일별 제공.
  VwsmTrdarRepopQq : 상주인구-상권 (배후인구)
  VwsmTrdarWrcPopltnQq : 직장인구-상권
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # kb/ 를 import 경로에
from src.config import get_key

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "data" / "_cache"
BASE = "http://openapi.seoul.go.kr:8088"
PAGE = 1000


def _key() -> str:
    return get_key("SEOUL_API_KEY")


def fetch(service: str, cache_dir: Path | None = None, force: bool = False) -> pd.DataFrame:
    """서비스 전체를 페이지네이션으로 수집 + CSV 캐시."""
    cache_dir = cache_dir or DEFAULT_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cache_dir / f"api_{service}.csv"
    if csv_path.exists() and not force:
        return pd.read_csv(csv_path)

    key = _key()
    first = requests.get(f"{BASE}/{key}/json/{service}/1/1/", timeout=30).json()
    total = first[service]["list_total_count"]

    rows = []
    for start in range(1, total + 1, PAGE):
        end = min(start + PAGE - 1, total)
        j = requests.get(f"{BASE}/{key}/json/{service}/{start}/{end}/", timeout=60).json()
        rows.extend(j[service]["row"])
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    fl = fetch("VwsmTrdarFlpopQq")
    print("유동인구 shape:", fl.shape)
    print("분기별 상권수:")
    print(fl.groupby("STDR_YYQU_CD")["TRDAR_CD"].nunique().tail(8))
