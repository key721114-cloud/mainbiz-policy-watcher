"""모든 API 어댑터/크롤러가 따르는 공통 인터페이스.

오케스트레이터(5단계)는 이 인터페이스만 보고 소스를 순차 호출하며,
개별 fetch()가 예외를 던져도 다른 소스 수집에 영향이 없도록
호출하는 쪽(orchestrator)에서 소스 단위로 try/except 한다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from common.schema import Announcement


class Adapter(ABC):
    source: str
    source_name: str

    @abstractmethod
    def fetch(self) -> list[Announcement]:
        """공고 목록을 공통 스키마로 반환한다. 실패 시 예외를 던진다."""
        raise NotImplementedError
