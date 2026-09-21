"""중소벤처기업부_사업공고 API 어댑터.

공공데이터포털: https://www.data.go.kr/data/15113297/openapi.do
Base URL: apis.data.go.kr/1421000/mssBizService_v2 (XML 응답)
2026-09-21 실제 호출로 검증 완료 (resultCode 00, totalCount 2200대).
"""
from __future__ import annotations

import requests
from xml.etree import ElementTree as ET

from adapters.base import Adapter
from common.schema import Announcement
from common.text import strip_html

BASE_URL = "https://apis.data.go.kr/1421000/mssBizService_v2/getbizList_v2"


class MSSAdapter(Adapter):
    source = "MSS"
    source_name = "중소벤처기업부"

    def __init__(self, service_key: str, num_of_rows: int = 100, max_pages: int = 30, timeout: int = 30):
        self.service_key = service_key
        self.num_of_rows = num_of_rows
        self.max_pages = max_pages
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        results: list[Announcement] = []
        total_count = None
        page = 1
        while page <= self.max_pages:
            resp = requests.get(
                BASE_URL,
                params={
                    "serviceKey": self.service_key,
                    "pageNo": page,
                    "numOfRows": self.num_of_rows,
                    "type": "xml",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            result_code = root.findtext(".//resultCode")
            if result_code != "00":
                result_msg = root.findtext(".//resultMsg")
                raise RuntimeError(f"[MSS] API 오류 resultCode={result_code} resultMsg={result_msg}")

            if total_count is None:
                total_count = int(root.findtext(".//totalCount") or "0")

            items = root.findall(".//item")
            if not items:
                break

            for item in items:
                item_id = (item.findtext("itemId") or "").strip()
                title = (item.findtext("title") or "").strip()
                start = (item.findtext("applicationStartDate") or "").strip() or None
                end = (item.findtext("applicationEndDate") or "").strip() or None
                view_url = (item.findtext("viewUrl") or "").strip()
                writer_position = (item.findtext("writerPosition") or "").strip()
                content = strip_html(item.findtext("dataContents"))

                period_text = "~".join(p for p in (start, end) if p)
                results.append(
                    Announcement(
                        source=self.source,
                        source_name=self.source_name,
                        title=title,
                        org=writer_position or self.source_name,
                        period_text=period_text,
                        period_start=start,
                        period_end=end,
                        url=view_url,
                        collect_method="API",
                        stage="모집공고",
                        external_id=f"MSS-{item_id}",
                        content=content,
                    )
                )

            if self.num_of_rows * page >= total_count:
                break
            page += 1

        return results
