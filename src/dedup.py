"""중복 판별 (4단계).

PRD 기준: "공고명 유사도 + 원문 링크"로 판별하고, 중복이어도 지우지 않고
is_duplicate 플래그만 표시한다(PRD 데이터 스키마: "중복 여부 - 타 소스와
중복 수집된 경우 표시"). 먼저 나온 항목(리스트 순서상 앞)을 대표로 남긴다.

주의: 접수기간이 다르면 "같은 사업의 1차/2차 공고"처럼 실제로는 다른
공고인 경우가 많다(예: "수출바우처사업 1차 공고" vs "2차 공고"는 제목이
90% 이상 비슷하다). 그래서 양쪽 다 접수시작일이 있는데 서로 다르면
제목이 아무리 비슷해도 중복으로 보지 않는다.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from common.schema import Announcement

_BRACKET_PREFIX = re.compile(r"^(\[[^\]]+\]|\([^)]+\))\s*")
_NON_WORD = re.compile(r"[^\w가-힣]")

SIMILARITY_WITH_DATE = 0.85  # 접수시작일이 같을 때 적용하는 완화된 기준
SIMILARITY_STRICT = 0.95  # 접수시작일 정보가 없을 때 적용하는 엄격한 기준
BUCKET_LEN = 12  # 정규화된 제목 앞부분으로 버킷을 나눠 비교량을 줄인다


def normalize_title(title: str) -> str:
    t = _BRACKET_PREFIX.sub("", title)  # "[전북] ..." 같은 지역/기관 태그 제거
    t = _NON_WORD.sub("", t)
    return t.lower()


def _is_same_announcement(a: Announcement, b: Announcement) -> bool:
    if a.url and b.url and a.url == b.url:
        return True

    norm_a, norm_b = normalize_title(a.title), normalize_title(b.title)
    if not norm_a or not norm_b:
        return False

    if a.period_start and b.period_start:
        if a.period_start != b.period_start:
            return False
        threshold = SIMILARITY_WITH_DATE
    else:
        threshold = SIMILARITY_STRICT

    if norm_a == norm_b:
        return True
    return SequenceMatcher(None, norm_a, norm_b).ratio() >= threshold


def mark_duplicates(items: list[Announcement]) -> None:
    """items를 in-place로 갱신해 중복 항목에 is_duplicate=True를 표시한다.
    같은 source 내부 중복은 각 어댑터/크롤러가 이미 걸러내므로, 여기서는
    서로 다른 source 간 중복만 신경 쓰면 된다."""
    buckets: dict[str, list[Announcement]] = {}
    for item in items:
        if item.is_duplicate:
            continue
        key = normalize_title(item.title)[:BUCKET_LEN]
        bucket = buckets.setdefault(key, [])
        for prior in bucket:
            if prior.source != item.source and _is_same_announcement(prior, item):
                item.is_duplicate = True
                break
        bucket.append(item)
