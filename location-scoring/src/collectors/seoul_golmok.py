"""
서울시 상권분석서비스 실데이터 수집기 (API 키 불필요 · 파일 다운로드).

출처: 서울 열린데이터광장 (data.seoul.go.kr) — 분기별·상권별·업종별.
다운로드: datafile.seoul.go.kr 로의 POST (datasetView 의 JS downloadFile 재현).
  frmFile 파라미터: infId, seq(=연도별 seqNo), infSeq="3"(파일다운로드 폼 공통).

지원 데이터셋:
  store : 점포-상권    (OA-15577) — 점포수/개폐업/프랜차이즈. 컬럼=영문코드
  sales : 추정매출-상권 (OA-15572) — 매출금액/건수/연령·시간·요일별. 컬럼=한글 → 영문 정규화

실데이터 검증: 두 파일을 trdar_cd + 분기로 조인 → 폐업예측 모델(AUC≈0.80).
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

DOWNLOAD_URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?useCache=false"
INF_SEQ = "3"  # 파일다운로드 폼(frmFile) 공통값
DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "_cache"

# 매출 파일(한글 컬럼) → 영문 표준키
_SALES_RENAME = {
    "기준_년분기_코드": "stdr_yyqu_cd", "상권_구분_코드_명": "trdar_se_cd_nm",
    "상권_코드": "trdar_cd", "상권_코드_명": "trdar_cd_nm",
    "서비스_업종_코드_명": "svc_induty_cd_nm",
    "당월_매출_금액": "sales_amt", "당월_매출_건수": "sales_cnt",
    "연령대_20_매출_금액": "amt_age20", "연령대_30_매출_금액": "amt_age30",
    "시간대_11~14_매출_금액": "amt_lunch", "시간대_17~21_매출_금액": "amt_dinner",
}

DATASETS = {
    "store": {"infId": "OA-15577",
              "year_seq": {2023: "18", 2024: "19", 2025: "20"},
              "rename": {}},
    "sales": {"infId": "OA-15572",
              "year_seq": {2023: "49", 2024: "50", 2025: "51"},
              "rename": _SALES_RENAME},
}


def download(dataset: str, year: int = 2025, cache_dir: Path | None = None,
             force: bool = False) -> Path:
    """연도별 CSV 다운로드 + 캐시. 반환: CSV 경로."""
    cfg = DATASETS[dataset]
    cache_dir = cache_dir or DEFAULT_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cache_dir / f"seoul_{dataset}_{year}.csv"
    if csv_path.exists() and not force:
        return csv_path

    seq = cfg["year_seq"][year]
    resp = requests.post(
        DOWNLOAD_URL,
        data={"infId": cfg["infId"], "seqNo": seq, "seq": seq, "infSeq": INF_SEQ},
        headers={"Referer": f"https://data.seoul.go.kr/dataList/{cfg['infId']}/S/1/datasetView.do"},
        timeout=180,
    )
    resp.raise_for_status()
    if not resp.content[:2] == b"PK":
        raise RuntimeError(f"다운로드 실패(zip 아님): {resp.content[:120]!r}")
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    csv_path.write_bytes(zf.read(zf.namelist()[0]))
    return csv_path


def load(dataset: str, year: int = 2025, induty: str | None = "커피-음료",
         region_contains: str | None = None, quarter: int | None = None,
         cache_dir: Path | None = None) -> pd.DataFrame:
    """실데이터 로드 + 컬럼 정규화 + 필터."""
    path = download(dataset, year, cache_dir=cache_dir)
    df = pd.read_csv(path, encoding="cp949")
    rename = DATASETS[dataset]["rename"]
    if rename:
        df = df.rename(columns=rename)
    if induty is not None:
        df = df[df["svc_induty_cd_nm"] == induty]
    if region_contains is not None:
        df = df[df["trdar_cd_nm"].astype(str).str.contains(region_contains, na=False)]
    if quarter is not None:
        df = df[df["stdr_yyqu_cd"] == quarter]
    return df.reset_index(drop=True)


if __name__ == "__main__":
    s = load("store", region_contains="성수", quarter=20254)
    print("점포:", s[["trdar_cd_nm", "stor_co", "clsbiz_rt"]].to_string(index=False))
    v = load("sales", region_contains="성수", quarter=20254)
    print("매출:", v[["trdar_cd_nm", "sales_amt", "amt_age20", "amt_age30"]].head().to_string(index=False))
