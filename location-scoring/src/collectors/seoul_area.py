"""
서울 상권 영역(OA-15560) — 상권↔자치구/행정동 매핑 + 좌표·면적.

키 불필요(파일). shapefile 이지만 속성(DBF)만 필요하므로 geopandas 없이 직접 파싱.
"마포구에 분식점" 같은 지역 질의를 상권 후보로 바꾸는 데 필수.

컬럼: trdar_cd, trdar_cd_nm, sigungu, adstrd, x, y, area
"""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = ROOT / "data" / "_cache"
URL = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?useCache=false"
PARAMS = {"infId": "OA-15560", "seqNo": "5", "seq": "5", "infSeq": "3"}

RENAME = {"TRDAR_CD": "trdar_cd", "TRDAR_CD_N": "trdar_cd_nm",
          "SIGNGU_CD_": "sigungu", "ADSTRD_CD_": "adstrd",
          "XCNTS_VALU": "x", "YDNTS_VALU": "y", "RELM_AR": "area"}


def _parse_dbf(data: bytes, encoding: str = "utf-8") -> pd.DataFrame:
    """DBF 속성 파싱. 이 shapefile 의 .cpg 는 UTF-8 (cp949 로 읽으면 깨짐)."""
    numrec, headerlen, reclen = struct.unpack("<IHH", data[4:12])
    nfields = (headerlen - 33) // 32
    fields = []
    for i in range(nfields):
        off = 32 + i * 32
        name = data[off:off + 11].split(b"\x00")[0].decode("ascii", "ignore")
        fields.append((name, chr(data[off + 11]), data[off + 16]))

    rows, pos = [], headerlen
    for _ in range(numrec):
        rec = data[pos:pos + reclen]
        pos += reclen
        if not rec or rec[:1] == b"*":          # 삭제 표시 레코드
            continue
        vals, off = {}, 1
        for name, typ, size in fields:
            s = rec[off:off + size].decode(encoding, "ignore").strip()
            off += size
            if typ == "N":
                try:
                    s = float(s) if s else None
                except ValueError:
                    s = None
            vals[name] = s
        rows.append(vals)
    return pd.DataFrame(rows)


def load_area(cache_dir: Path | None = None, force: bool = False) -> pd.DataFrame:
    cache_dir = cache_dir or DEFAULT_CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    csv_path = cache_dir / "seoul_area_trdar.csv"
    if csv_path.exists() and not force:
        return pd.read_csv(csv_path)

    zip_path = cache_dir / "area_trdar.zip"
    if not zip_path.exists() or force:
        r = requests.post(URL, data=PARAMS,
                          headers={"Referer": "https://data.seoul.go.kr/dataList/OA-15560/S/1/datasetView.do"},
                          timeout=120)
        r.raise_for_status()
        zip_path.write_bytes(r.content)

    z = zipfile.ZipFile(zip_path)
    dbf = [n for n in z.namelist() if n.lower().endswith(".dbf")][0]
    df = _parse_dbf(z.read(dbf)).rename(columns=RENAME)
    df = df[list(RENAME.values())]
    df["trdar_cd"] = pd.to_numeric(df["trdar_cd"], errors="coerce").astype("Int64")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return df


if __name__ == "__main__":
    a = load_area()
    print(f"상권 {len(a)}개 / 자치구 {a['sigungu'].nunique()}개")
    mp = a[a["sigungu"] == "마포구"]
    print(f"\n마포구 상권 {len(mp)}개 (일부):")
    print(mp[["trdar_cd", "trdar_cd_nm", "adstrd"]].head(12).to_string(index=False))
