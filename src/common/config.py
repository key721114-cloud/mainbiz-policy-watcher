"""api_keys.env / keywords.env 같은 단순 KEY=VALUE 설정 파일 로더.

GitHub Actions에서는 같은 이름의 값을 환경변수(Repository Secrets)로 주입하므로,
파일이 없으면 os.environ을 그대로 사용한다.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE 형식의 파일을 dict로 읽는다. '#'으로 시작하는 줄과 빈 줄은 무시."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def get_setting(key: str, env_file_values: dict[str, str]) -> str | None:
    """환경변수(os.environ)를 우선 확인하고, 없으면 파일에서 읽은 값을 사용한다."""
    return os.environ.get(key) or env_file_values.get(key) or None


def load_keywords(path: Path) -> list[str]:
    """keywords.env의 KEYWORDS=a,b,c 값을 리스트로 반환."""
    env = load_env_file(path)
    raw = get_setting("KEYWORDS", env) or ""
    return [kw.strip() for kw in raw.split(",") if kw.strip()]
