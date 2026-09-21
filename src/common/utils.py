from __future__ import annotations

import re

_YYYYMMDD = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
# 날짜 뒤에 "09:00" 같은 시각이 붙어도(KEIT 등) 날짜만 뽑아낸다.
_PERIOD_DASHED = re.compile(r"(\d{4}-\d{2}-\d{2})(?:\s+\d{2}:\d{2})?\s*~\s*(\d{4}-\d{2}-\d{2})(?:\s+\d{2}:\d{2})?")


def yyyymmdd_to_dashed(raw: str | None) -> str | None:
    """"20260921" -> "2026-09-21". 이미 형식이 다르면 원본을 그대로 반환."""
    if not raw:
        return None
    m = _YYYYMMDD.match(raw.strip())
    if not m:
        return raw.strip() or None
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def extract_period(period_text: str | None) -> tuple[str | None, str | None]:
    """"2026-09-16 ~ 2026-12-31" 같은 자유 텍스트에서 시작/종료일을 뽑는다.
    매칭 실패 시 (None, None)."""
    if not period_text:
        return None, None
    m = _PERIOD_DASHED.search(period_text)
    if not m:
        return None, None
    return m.group(1), m.group(2)
