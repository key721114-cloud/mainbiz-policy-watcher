"""키워드 매칭 (4단계).

keywords.env의 키워드 목록으로 공고 제목/본문을 매칭한다. 본문(content)은
목록 조회 시점에 이미 받아온 데이터만 쓴다(개별 상세페이지를 추가로
불러오지 않음 - 상대 서버 부담을 늘리지 않기 위함). 어떤 소스가 본문을
제공하는지는 각 어댑터의 content 필드 채움 여부를 참고.
"""
from __future__ import annotations

from common.schema import Announcement


def match_keywords(item: Announcement, keywords: list[str]) -> list[str]:
    haystack = f"{item.title} {item.content}"
    return [kw for kw in keywords if kw in haystack]


def apply_keyword_matching(items: list[Announcement], keywords: list[str]) -> None:
    """items를 in-place로 갱신해 matched_keywords를 채운다."""
    for item in items:
        item.matched_keywords = match_keywords(item, keywords)


def filter_matched(items: list[Announcement]) -> list[Announcement]:
    """키워드가 하나라도 매칭된 항목만 남긴다."""
    return [item for item in items if item.matched_keywords]
