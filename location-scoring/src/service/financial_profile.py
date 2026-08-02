"""
금융 프로파일 빌더 — 플로우 ③④⑤ 를 하나의 상태 객체로.

추천된 상권 1곳 + 사용자 입력 → 창업비용/보유자금/부족자금(용도별)/창업자특성 을
담은 financial_profile 을 만든다. 이게 ⑥⑦(금융수요 분석·상품 추천)의 입력이 된다.

  ③ 예상 창업비용   : startup_cost.estimate (프랜차이즈/개인 분기)
  ④ 보유자금 비교   : capital (본인 입력)
  ⑤ 부족자금 계산   : 시설 gap / 운영 gap 으로 분리 (⑥에서 용도별 판단에 필요)
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.service.startup_cost import estimate as estimate_cost

# 창업자 특성 기준
YOUTH_MAX_AGE = 39           # 청년 기준(만 나이)
LOAN_INCOME_MULT = 4         # 대출여력 ≈ 연소득 × 배수 (창업대출 통상, 간이 추정)
STAGE_ALIASES = {
    "예비창업": "예비창업", "예비": "예비창업", "예정": "예비창업",
    "1년미만": "1년미만", "1년 미만": "1년미만",
    "3년이내": "3년이내", "3년 이내": "3년이내",
    "3년이상": "3년이상", "3년 이상": "3년이상",
}


def _age(birth_year) -> int | None:
    if not birth_year:
        return None
    try:
        return date.today().year - int(birth_year)
    except (ValueError, TypeError):
        return None



def _parse_num(v):
    """'20평'·'20' → 20.0 / None → None"""
    if v is None:
        return None
    import re
    m = re.search(r"(\d+(?:\.\d+)?)", str(v))
    return float(m.group(1)) if m else None

def build_profile(req: dict, top_location: dict) -> dict:
    """사용자 입력(req) + 추천 상권 1곳(top_location) → 금융 프로파일.

    top_location 은 recommend() 결과의 rows[i] (name·norm 등 포함).
    창업비용 계산엔 상권의 임대 시세가 필요하므로 sigungu/dong 을 넘긴다.
    """
    induty = req.get("_induty") or req.get("business_type")
    # 평수: 대화형은 필수(프론트/백엔드에서 강제). 없으면 기본 20평(설문형 자금측정 등).
    pyeong = float(req.get("store_size_pyeong") or req.get("_pyeong")
                   or _parse_num(req.get("store_size")) or 20)
    sigungu = top_location.get("sigungu") or req.get("_sigungu")
    dong = top_location.get("adstrd")
    is_fr = bool(req.get("franchise", False))

    # ③ 예상 창업비용 (프랜차이즈/개인 분기)
    cost = estimate_cost(induty, pyeong, sigungu, is_franchise=is_fr, dong=dong)

    # ④ 보유자금
    capital = int(req.get("capital") or 0)

    # ⑤ 부족자금 — 시설/운영 분리
    #   보유자금은 '시설자금(고정투자)'에 먼저 투입한다고 가정(현실적 관행).
    facility = cost["시설자금계"]                 # 보증금+권리금+인테리어+설비+가맹비
    operating = cost["운영자금계"]                # 초기 운영비
    total = cost["총창업비용"]

    gap_total = max(0, total - capital)
    # 보유자금을 시설에 먼저 → 남으면 운영에
    cap_to_facility = min(capital, facility)
    gap_facility = max(0, facility - cap_to_facility)
    cap_left = capital - cap_to_facility
    gap_operating = max(0, operating - cap_left)

    # 창업자 특성
    age = _age(req.get("birth_year"))
    stage = STAGE_ALIASES.get(str(req.get("business_stage", "")).strip(), "미상")
    is_youth = age is not None and age <= YOUTH_MAX_AGE

    # 대출여력(간이): 연소득 × 배수. 부족자금을 감당할 수 있는지 현실성 체크용.
    annual_income = int(req.get("annual_income") or 0)
    loan_capacity = annual_income * LOAN_INCOME_MULT
    #  - coverable    : 대출로 부족분 감당 가능
    #  - over_budget  : 다 빌려도 부족 → 규모/입지 재검토 신호
    affordability = ("sufficient" if gap_total == 0
                     else "coverable" if gap_total <= loan_capacity
                     else "over_budget")

    return {
        "location": top_location.get("name"),
        "induty": induty, "type": cost["type"], "pyeong": pyeong,
        # ③ 비용
        "cost_breakdown": {k: cost[k] for k in
                           ["보증금", "권리금", "인테리어", "설비비", "가맹비", "운영자금"]},
        "required_fund": total,
        # ④ 보유
        "capital": capital,
        # ⑤ 부족 (용도별)
        "fund_gap": gap_total,
        "gap_facility": gap_facility,       # 시설자금 부족
        "gap_operating": gap_operating,     # 운영자금 부족
        # 창업자 특성 (⑥ 정책·보증 판단용)
        "age": age, "is_youth": is_youth, "business_stage": stage,
        "annual_income": annual_income,
        # 대출여력·감당 가능성 (현실성 체크)
        "loan_capacity": loan_capacity,
        "affordability": affordability,   # sufficient / coverable / over_budget
    }


def format_profile(p: dict) -> str:
    def won(x): return f"{x/1e4:,.0f}만"
    lines = [
        f"[금융 프로파일] {p['location']} · {p['induty']} {p['pyeong']:.0f}평 ({p['type']})",
        "─" * 52,
        "③ 예상 창업비용:",
    ]
    for k, v in p["cost_breakdown"].items():
        if v > 0:
            lines.append(f"     {k:<8}{won(v):>12}")
    lines += [
        f"   ─ 필요자금 합계    {won(p['required_fund']):>12}",
        f"④ 보유자금          {won(p['capital']):>12}",
        f"⑤ 부족자금 합계     {won(p['fund_gap']):>12}",
        f"     └ 시설자금 부족 {won(p['gap_facility']):>12}",
        f"     └ 운영자금 부족 {won(p['gap_operating']):>12}",
        f"창업자: 만{p['age']}세{' · 청년' if p['is_youth'] else ''} · {p['business_stage']}"
        f" · 연소득 {won(p['annual_income'])}",
        f"대출여력(간이): {won(p['loan_capacity'])}  → 감당 판정: "
        + {"sufficient": "보유자금으로 충분",
           "coverable": "대출로 감당 가능",
           "over_budget": "⚠️ 대출로도 부족(규모·입지 재검토 권장)"}[p["affordability"]],
    ]
    return "\n".join(lines)
