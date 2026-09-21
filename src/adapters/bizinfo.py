"""기업마당(bizinfo) 지원사업공고 API 어댑터.

API 안내: https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do (crtfcKey 필요, JSON/RSS)
2026-09-21 실제 호출로 검증 완료 (totCnt 1500대).

주의: 중소벤처24(TIPA)의 "공고정보 API"는 이 기업마당 데이터를 그대로
재제공하는 구조로 확인되어(포털 안내 문구 기준), 두 소스 사이에 중복이
발생할 수 있다 - 4단계 중복 제거에서 처리.
"""
from __future__ import annotations

import requests

from adapters.base import Adapter
from common.schema import Announcement
from common.text import strip_html
from common.utils import extract_period

BASE_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"


class BizinfoAdapter(Adapter):
    source = "BIZINFO"
    source_name = "기업마당"

    def __init__(self, crtfc_key: str, page_unit: int = 100, max_pages: int = 30, timeout: int = 15):
        self.crtfc_key = crtfc_key
        self.page_unit = page_unit
        self.max_pages = max_pages
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        results: list[Announcement] = []
        page_index = 1
        while page_index <= self.max_pages:
            resp = requests.get(
                BASE_URL,
                params={
                    "crtfcKey": self.crtfc_key,
                    "dataType": "json",
                    "pageUnit": self.page_unit,
                    "pageIndex": page_index,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            payload = resp.json()

            if "jsonArray" not in payload:
                raise RuntimeError(f"[BIZINFO] 예상치 못한 응답: {payload}")

            rows = payload.get("jsonArray") or []
            if not rows:
                break

            for row in rows:
                title = (row.get("pblancNm") or "").strip()
                org = (row.get("jrsdInsttNm") or row.get("excInsttNm") or "").strip()
                period_text = (row.get("reqstBeginEndDe") or "").strip()
                start, end = extract_period(period_text)
                url = (row.get("pblancUrl") or "").strip()
                pblanc_id = row.get("pblancId")
                content = strip_html(row.get("bsnsSumryCn"))

                results.append(
                    Announcement(
                        source=self.source,
                        source_name=self.source_name,
                        title=title,
                        org=org or self.source_name,
                        period_text=period_text,
                        period_start=start,
                        period_end=end,
                        url=url,
                        collect_method="API",
                        stage="모집공고",
                        external_id=f"BIZINFO-{pblanc_id}",
                        content=content,
                    )
                )

            if len(rows) < self.page_unit:
                break
            page_index += 1

        return results
