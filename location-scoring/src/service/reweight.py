"""
사용자 우선순위 기반 가중치 재조정 (2층 개인화).

1팀이 준 base 가중치(AHP 등) 위에 사용자 우선순위를 볼록결합으로 얹는다:

    final = (1 - α) · base + α · pref

  - pref(선호벡터)는 사용자 우선순위로 생성. 세 경우:
      ① 순위 있음   → 차등(Borda: 1위=k, 2위=k-1, …) 정규화
      ② 순위 없음   → 선택 항목 등가중(1/k)
      ③ 선택 없음   → base 그대로 (α 무시)
  - base·pref 둘 다 합=1 → final 도 자동 합=1 (재정규화 불필요).
  - 비선택 항목도 (1-α)·base 로 남아 전문가 가중치가 사라지지 않음.

α = 우선순위 반영 강도 (약0.2 / 보통0.35 / 강0.5). 기본 0.3.
"""

from __future__ import annotations


def build_pref_vector(priorities: list[str], criteria: list[str],
                      ranked: bool) -> dict | None:
    """사용자 우선순위 → 선호벡터(합=1). 선택 없으면 None."""
    picks = list(dict.fromkeys(priorities))[:3]   # 최대 3개 (base에 없는 지표도 허용)
    k = len(picks)
    if k == 0:
        return None
    if ranked:
        raw = {c: (k - i) for i, c in enumerate(picks)}     # 1위=k … 마지막=1
    else:
        raw = {c: 1 for c in picks}                          # 등가중
    total = sum(raw.values())
    keys = list(dict.fromkeys(list(criteria) + picks))   # base ∪ 우선순위
    return {c: raw.get(c, 0) / total for c in keys}


def reweight(base: dict, priorities: list[str] | None = None,
             ranked: bool = True, alpha: float = 0.3) -> dict:
    """base 가중치 + 사용자 우선순위 → 최종 가중치(합=1)."""
    criteria = list(base)
    pref = build_pref_vector(priorities or [], criteria, ranked)
    if pref is None:                                         # ③ 선택 없음
        return {c: round(base[c], 4) for c in criteria}
    return {c: round((1 - alpha) * base.get(c, 0.0) + alpha * pref[c], 4) for c in pref}


if __name__ == "__main__":
    base = {"유동인구": 0.30, "임대료": 0.25, "경쟁밀도": 0.20,
            "교통": 0.15, "배후인구": 0.10}

    def show(title, w):
        print(f"\n{title}")
        for c, v in w.items():
            print(f"  {c:<8}{v:.3f}")
        print(f"  합계    {sum(w.values()):.3f}")

    show("base (1팀 AHP)", base)
    show("① 순위 있음  [임대료>유동인구>경쟁밀도], α=0.3",
         reweight(base, ["임대료", "유동인구", "경쟁밀도"], ranked=True, alpha=0.3))
    show("② 순위 없음  {임대료, 유동인구, 경쟁밀도} 등가중, α=0.3",
         reweight(base, ["임대료", "유동인구", "경쟁밀도"], ranked=False, alpha=0.3))
    show("③ 선택 없음  → base 그대로",
         reweight(base, [], alpha=0.3))
