"""공통 공고 스키마.

PRD의 데이터 스키마(공고명·소관기관·접수기간·원문링크·수집일시 등)를 따른다.
모든 어댑터/크롤러는 이 Announcement 형태로 결과를 반환해야 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


@dataclass
class Announcement:
    source: str  # 소스 코드 (예: MSS, KSTARTUP, BIZINFO, G2B)
    source_name: str  # 소스 한글명 (예: 중소벤처기업부)
    title: str  # 공고명
    org: str  # 소관·수행기관
    period_text: str  # 접수기간 원문 (파싱 실패 시에도 보존)
    period_start: str | None  # 접수 시작일 YYYY-MM-DD (파싱 가능한 경우)
    period_end: str | None  # 접수 종료일 YYYY-MM-DD (파싱 가능한 경우)
    url: str  # 원문 링크
    collect_method: str  # "API" | "CRAWL"
    stage: str  # "모집공고" | "집행단계" (나라장터는 집행단계)
    external_id: str  # 소스 내 원본 ID (중복 판별용 1차 키)
    content: str = ""  # 본문 요약 (목록 조회 시 같이 오는 경우만 채움 - 키워드 매칭에 함께 사용)
    matched_keywords: list[str] = field(default_factory=list)  # 4단계에서 채움
    is_duplicate: bool = False  # 4단계에서 채움
    collected_at: str = field(default_factory=now_kst_iso)

    def to_dict(self) -> dict:
        return asdict(self)
