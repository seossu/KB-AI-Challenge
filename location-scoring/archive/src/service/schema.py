"""
사용자 입력 JSON → 계량 변수(UserQuery).

데이터_명세.md §2.1, §5 스키마 확정안을 코드로 옮긴 것.
실서비스에서는 target_customer 파싱을 LLM이 하지만, 데모는 규칙기반으로 근사.
"""

from __future__ import annotations

from dataclasses import dataclass

PRIORITY_ENUM = {
    "foot_traffic",       # 유동인구
    "low_rent",           # 낮은 임대료
    "low_competition",    # 낮은 경쟁밀도
    "transit",            # 교통접근성
    "residential_base",   # 배후인구
}

PYEONG_TO_M2 = 3.3058


@dataclass
class UserQuery:
    purpose: str
    business_type: str
    capital: int
    desired_loan: int
    preferred_region: str
    target_customer: str
    priority: list[str]
    store_size_pyeong: float
    parking: bool
    public_transport: bool

    def __post_init__(self) -> None:
        bad = set(self.priority) - PRIORITY_ENUM
        if bad:
            raise ValueError(f"priority에 허용되지 않은 값: {bad}. 허용: {PRIORITY_ENUM}")

    @property
    def total_funding(self) -> int:
        """자기자본 + 희망대출 = 총 조달가능 자금."""
        return self.capital + self.desired_loan

    @property
    def area_m2(self) -> float:
        return round(self.store_size_pyeong * PYEONG_TO_M2, 2)

    @property
    def segment(self) -> dict:
        """target_customer 문자열 → 유동인구 세그먼트(연령·시간대) 근사 파싱."""
        s = self.target_customer
        age = "20-30" if ("20" in s or "30" in s) else "all"
        time = "weekday_lunch_dinner" if ("직장" in s or "회사" in s) else "all_day"
        return {"age": age, "time": time}

    @classmethod
    def from_dict(cls, d: dict) -> "UserQuery":
        return cls(
            purpose=d["purpose"],
            business_type=d["business_type"],
            capital=int(d["capital"]),
            desired_loan=int(d.get("desired_loan", 0)),
            preferred_region=d["preferred_region"],
            target_customer=d.get("target_customer", ""),
            priority=list(d.get("priority", [])),
            store_size_pyeong=float(d["store_size_pyeong"]),
            parking=bool(d.get("parking", False)),
            public_transport=bool(d.get("public_transport", False)),
        )
