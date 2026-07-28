"""
예상 창업비용 계산 — 프랜차이즈 / 개인창업 분기.

항목별 데이터 성격이 다르다:
  · 보증금·월세  : 상권별로 다름 → 국토부 실거래 ㎡시세로 동적 계산 (이미 수집됨)
  · 권리금       : 업종별 통계   → 부동산원 상가건물 임대차 실태조사 (서울 평균 4,915만/2024)
  · 인테리어·설비 : 업종별 통계   → 공정위 가맹정보 창업비용 / 통계청 소상공인실태조사
  · 가맹비       : 프랜차이즈만   → 공정위 정보공개서 (가입비+교육비+계약이행보증)
  · 운영자금     : 규칙          → 월 고정비 × N개월 (소진공 권장 3~6개월)

권리금·인테리어·설비·가맹비는 상권이 아니라 '업종' 단위 통계라 API 매번 호출이
불필요 → 공개 통계수치를 업종별 테이블로 둔다(근거 주석). 실거래만 동적.
※ 값은 공개 통계 기반 캘리브레이션 추정치. 정확 견적은 시공사·브랜드별 상이.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.collectors.molit_rtms import build_rent_index, collect

PYEONG_M2 = 3.3058
CAP_RATE = 0.04        # 매매가 대비 연 임대수익률 → 월세 환산
DEPOSIT_MONTHS = 10    # 보증금 ≈ 월세 × 개월
MONTHS = ["202501", "202502", "202503", "202504", "202505", "202506"]

# ── 업종별 비용 테이블 (단위: 만원). 공개 통계 기반 추정 ──
# interior_*: 만원/평 (인테리어 평당 단가, 프랜차이즈 fr / 개인 ps)
# equip_*   : 만원 (설비 기본 세트)
# fee       : 만원 (프랜차이즈 가맹비: 가입비+교육비+보증금)
# goodwill  : 만원 (업종 평균 권리금, 부동산원 실태조사 기반)
COST_TABLE = {
    #                 인테리어평당(fr/ps)  설비(fr/ps)     가맹비   권리금
    "커피-음료":   dict(int_fr=280, int_ps=210, eq_fr=3000, eq_ps=2500, fee=1000, gw=4500),
    "제과점":     dict(int_fr=300, int_ps=230, eq_fr=4500, eq_ps=3800, fee=1200, gw=5000),
    "한식음식점":  dict(int_fr=250, int_ps=190, eq_fr=5000, eq_ps=4000, fee=1200, gw=5500),
    "패스트푸드점": dict(int_fr=260, int_ps=200, eq_fr=4500, eq_ps=3800, fee=1500, gw=5000),
    "분식전문점":  dict(int_fr=220, int_ps=170, eq_fr=3500, eq_ps=2800, fee=800,  gw=4000),
    "치킨전문점":  dict(int_fr=230, int_ps=180, eq_fr=3800, eq_ps=3200, fee=1000, gw=4500),
    "호프-간이주점": dict(int_fr=240, int_ps=180, eq_fr=3500, eq_ps=2800, fee=1000, gw=5000),
    "편의점":     dict(int_fr=180, int_ps=150, eq_fr=4000, eq_ps=3500, fee=1500, gw=4000),
    "네일숍":     dict(int_fr=200, int_ps=160, eq_fr=1500, eq_ps=1200, fee=800,  gw=3000),
    "미용실":     dict(int_fr=220, int_ps=170, eq_fr=2500, eq_ps=2000, fee=1000, gw=3500),
    "일반교습학원": dict(int_fr=150, int_ps=120, eq_fr=1500, eq_ps=1200, fee=1200, gw=2500),
    "_default":   dict(int_fr=250, int_ps=190, eq_fr=3500, eq_ps=2800, fee=1000, gw=4000),
}

# 지역 권리금 보정(부동산원 2024: 서울 4,915만 vs 전국 3,443만 ≈ ×1.43). 서울 기준 1.0.
GOODWILL_REGION_MULT = 1.0

_rent_cache: dict = {}


def _rent_index():
    if "dong" not in _rent_cache:
        d = collect(MONTHS)
        dong, gu = build_rent_index(d)
        _rent_cache["dong"], _rent_cache["gu"] = dong, gu
    return _rent_cache["dong"], _rent_cache["gu"]


def rent_and_deposit(sigungu: str, pyeong: float, dong: str | None = None) -> tuple[float, float]:
    """실거래 ㎡시세 → (월세, 보증금) 원. 동 매칭 실패 시 자치구 중앙값."""
    dong_df, gu_df = _rent_index()
    per_m2 = None
    if dong is not None:
        hit = dong_df[(dong_df["sggNm"] == sigungu) & (dong_df["umdNm"] == dong)]
        if len(hit):
            per_m2 = float(hit["price_per_m2"].iat[0])
    if per_m2 is None:
        hit = gu_df[gu_df["sggNm"] == sigungu]
        per_m2 = float(hit["price_per_m2"].iat[0]) if len(hit) else 8_000_000.0
    monthly = per_m2 * pyeong * PYEONG_M2 * CAP_RATE / 12
    return monthly, monthly * DEPOSIT_MONTHS


def estimate(induty: str, pyeong: float, sigungu: str, is_franchise: bool,
             dong: str | None = None, opex_months: int = 3) -> dict:
    """예상 창업비용 분해. is_franchise 로 인테리어/설비/가맹비 분기."""
    c = COST_TABLE.get(induty, COST_TABLE["_default"])
    monthly, deposit = rent_and_deposit(sigungu, pyeong, dong)

    interior = pyeong * (c["int_fr"] if is_franchise else c["int_ps"]) * 1e4
    equipment = (c["eq_fr"] if is_franchise else c["eq_ps"]) * 1e4
    franchise_fee = c["fee"] * 1e4 if is_franchise else 0.0
    goodwill = c["gw"] * GOODWILL_REGION_MULT * 1e4
    operating = monthly * opex_months          # 운영자금(초기 N개월)

    facility = deposit + goodwill + interior + equipment + franchise_fee  # 시설·초기투자
    total = facility + operating

    return {
        "induty": induty, "type": "프랜차이즈" if is_franchise else "개인창업",
        "pyeong": pyeong, "sigungu": sigungu,
        "monthly_rent": monthly,
        "보증금": deposit, "권리금": goodwill, "인테리어": interior,
        "설비비": equipment, "가맹비": franchise_fee,
        "운영자금": operating,
        "시설자금계": facility, "운영자금계": operating, "총창업비용": total,
    }


if __name__ == "__main__":
    def won(x): return f"{x/1e4:,.0f}만"
    print("=== 카페 20평 @ 성동구 — 프랜차이즈 vs 개인창업 ===\n")
    fr = estimate("커피-음료", 20, "성동구", is_franchise=True)
    ps = estimate("커피-음료", 20, "성동구", is_franchise=False)
    rows = ["보증금", "권리금", "인테리어", "설비비", "가맹비", "운영자금", "총창업비용"]
    print(f"{'항목':<10}{'프랜차이즈':>14}{'개인창업':>14}")
    for k in rows:
        print(f"{k:<10}{won(fr[k]):>14}{won(ps[k]):>14}")
