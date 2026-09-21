"""텍스트 정제 유틸 (HTML 태그 제거 등)."""
from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(raw: str | None) -> str:
    """본문 필드에 섞여 오는 HTML 태그를 제거하고 엔티티를 풀어 평문으로 만든다."""
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()
