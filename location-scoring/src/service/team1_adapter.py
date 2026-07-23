"""
1팀(GPT-4o 대화형 추출기) 출력 → 우리 recommend() 입력 어댑터.

1팀 main.py 는 다음 형태의 JSON 을 내보낸다:
  {
    "extracted_data": {
       "capital": "2억",                    # 문자열
       "preferred_region": ["서강대역","대흥"], # 배열
       ... },
    "next_question": ...,
    "ready_to_proceed": true
  }

우리 recommend() 는 평면 dict + capital(int) + preferred_region(str) 을 기대하므로 변환한다.
"""

from __future__ import annotations

import re

# 큰 단위(구간 구분) / 작은 단위(구간 내 자릿수)
_BIG = {"조": 1_0000_0000_0000, "억": 1_0000_0000, "만": 1_0000}
_SMALL = {"천": 1_000, "백": 100, "십": 10}


def parse_capital(value) -> int | None:
    """'2억'·'2억5천만'·'2억 5000만'·'200000000'·2억(int) → 원(int).

    큰 단위(조/억/만)에서 구간을 끊고, 각 구간 안의 '천/백/십'을 누적한다.
    예) '2억5천만' = 2×1억 + (5×1천)×1만 = 2.5억
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).replace(",", "").replace(" ", "").replace("원", "")
    if s.isdigit():
        return int(s)

    total, seg, num = 0, 0, ""      # total=확정합, seg=현재 구간 누적, num=숫자버퍼
    for ch in s:
        if ch.isdigit() or ch == ".":
            num += ch
        elif ch in _SMALL:                      # 천/백/십 → 구간 안에서 더함
            seg += (float(num) if num else 1) * _SMALL[ch]
            num = ""
        elif ch in _BIG:                        # 억/만 → 구간 확정
            seg += (float(num) if num else 0)
            total += (seg if seg else 1) * _BIG[ch]
            seg, num = 0, ""
    total += seg + (float(num) if num else 0)   # 단위 없이 남은 것
    return int(total) if total else None


def adapt(team1_json: dict) -> dict:
    """1팀 출력(감싸진 형태 또는 평면) → 우리 입력 dict."""
    data = team1_json.get("extracted_data", team1_json)  # 언랩(없으면 이미 평면)

    region = data.get("preferred_region")
    if isinstance(region, list):
        region = region[0] if region else None            # 첫 지역 사용(대표)

    out = dict(data)
    out["capital"] = parse_capital(data.get("capital"))
    out["preferred_region"] = region
    out["_all_regions"] = data.get("preferred_region")    # 원본 배열 보존(다중지역 확장용)
    return out


def ready(team1_json: dict) -> bool:
    """추천을 진행해도 되는 상태인지(1팀이 정보수집 종료했는지)."""
    return bool(team1_json.get("ready_to_proceed", True))


if __name__ == "__main__":
    sample = {
        "extracted_data": {
            "purpose": "창업", "business_type": "카페", "capital": "2억 5천만",
            "preferred_region": ["서강대역", "대흥"],
            "target_customer": "20~30대 직장인",
            "priority": ["유동인구", "낮은 임대료"],
            "store_size": "20평", "parking": True, "public_transport": True,
        },
        "next_question": None, "ready_to_proceed": True,
    }
    r = adapt(sample)
    print("capital :", r["capital"], "원")
    print("region  :", r["preferred_region"], "(전체:", r["_all_regions"], ")")
    print("ready   :", ready(sample))
