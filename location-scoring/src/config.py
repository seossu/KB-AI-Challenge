"""
환경변수/시크릿 로더 (외부 의존성 없음).

우선순위: 실제 환경변수 > kb/.env > (하위호환) kb/.seoul_key · kb/.datago_key

.env 형식:
    SEOUL_API_KEY=xxxxxxxx
    DATAGO_KEY=yyyyyyyy
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # kb/
ENV_PATH = ROOT / ".env"
_loaded = False

# 환경변수명 → (하위호환용 기존 키파일)
LEGACY_FILES = {
    "SEOUL_API_KEY": ".seoul_key",
    "DATAGO_KEY": ".datago_key",
}


def load_env(path: Path | None = None, override: bool = False) -> None:
    """.env 를 읽어 os.environ 에 주입 (이미 있는 값은 기본적으로 유지)."""
    global _loaded
    path = path or ENV_PATH
    if _loaded and path == ENV_PATH:
        return
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if override or k not in os.environ:
                os.environ[k] = v
    if path == ENV_PATH:
        _loaded = True


def get_key(name: str) -> str:
    """API 키 조회. 없으면 무엇을 설정해야 하는지 알려주며 실패."""
    load_env()
    v = os.environ.get(name)
    if v:
        return v.strip()

    legacy = LEGACY_FILES.get(name)
    if legacy and (ROOT / legacy).exists():          # 예전 방식 지원
        return (ROOT / legacy).read_text().strip()

    raise RuntimeError(
        f"[{name}] 키가 없습니다.\n"
        f"  1) kb/.env 파일에  {name}=발급받은키  형태로 추가하거나\n"
        f"  2) 환경변수로 export {name}=... 하세요.\n"
        f"  (템플릿: kb/.env.example 참고)"
    )
