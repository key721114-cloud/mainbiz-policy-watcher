"""창업진흥원_K-Startup 지원사업 공고 정보 API 어댑터.

공공데이터포털: https://www.data.go.kr/data/15125364/openapi.do
Base URL: apis.data.go.kr/B552735/kisedKstartupService01 (JSON 응답)
2026-09-21 실제 호출로 검증 완료.

주의: totalCount가 3만건대(창업진흥원 설립 이후 누적)라 매 실행마다 전체를
가져오면 낭비가 크다. 응답이 최신순으로 내려오는 것을 확인했으므로,
접수시작일(pbanc_rcpt_bgng_dt)이 cutoff보다 오래된 페이지를 만나면 조기 종료한다.
"""
from __future__ import annotations

from datetime import date, timedelta

import requests

from adapters.base import Adapter
from common.schema import Announcement
from common.text import strip_html
from common.utils import yyyymmdd_to_dashed

BASE_URL = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"


class KStartupAdapter(Adapter):
    source = "KSTARTUP"
    source_name = "창업진흥원(K-Startup)"

    def __init__(
        self,
        service_key: str,
        per_page: int = 100,
        max_pages: int = 20,
        lookback_days: int = 60,
        timeout: int = 15,
    ):
        self.service_key = service_key
        self.per_page = per_page
        self.max_pages = max_pages
        self.lookback_days = lookback_days
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        cutoff = (date.today() - timedelta(days=self.lookback_days)).strftime("%Y%m%d")
        results: list[Announcement] = []
        page = 1
        while page <= self.max_pages:
            resp = requests.get(
                BASE_URL,
                params={
                    "serviceKey": self.service_key,
                    "page": page,
                    "perPage": self.per_page,
                    "returnType": "json",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            payload = resp.json()

            if "data" not in payload:
                raise RuntimeError(f"[KSTARTUP] 예상치 못한 응답: {payload}")

            rows = payload.get("data") or []
            if not rows:
                break

            oldest_in_page = None
            for row in rows:
                start_raw = row.get("pbanc_rcpt_bgng_dt")
                end_raw = row.get("pbanc_rcpt_end_dt")
                start = yyyymmdd_to_dashed(start_raw)
                end = yyyymmdd_to_dashed(end_raw)
                if start_raw and (oldest_in_page is None or start_raw < oldest_in_page):
                    oldest_in_page = start_raw

                title = (row.get("biz_pbanc_nm") or "").strip()
                org = (row.get("pbanc_ntrp_nm") or row.get("biz_prch_dprt_nm") or "").strip()
                url = (row.get("detl_pg_url") or "").strip()
                pbanc_sn = row.get("pbanc_sn")
                content = strip_html(row.get("pbanc_ctnt"))

                period_text = "~".join(p for p in (start, end) if p)
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
                        external_id=f"KSTARTUP-{pbanc_sn}",
                        content=content,
                    )
                )

            if oldest_in_page is not None and oldest_in_page < cutoff:
                break
            if len(rows) < self.per_page:
                break
            page += 1

        return results
