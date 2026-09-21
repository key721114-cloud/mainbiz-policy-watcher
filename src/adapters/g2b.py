"""조달청_나라장터 입찰공고정보서비스 어댑터.

공공데이터포털: https://www.data.go.kr/data/15129394/openapi.do
Base URL: apis.data.go.kr/1230000/ad/BidPublicInfoService (JSON/XML)
2026-09-21 실제 호출로 검증 완료 (resultCode 00).

PRD 상 나라장터는 '모집공고'가 아니라 이미 선정된 사업자가 지원금을
집행(장비·용역 구매)하는 '조달 계약' 단계 정보다. 따라서:
  - stage="집행단계" 로 명확히 표시해 다른 소스(모집공고)와 구분한다.
  - 신규 공고 조기포착용이 아니라 선정 사업 후속 추적용 보조 소스이므로,
    API 자체가 bidNtceNm(공고명) 키워드 검색을 지원하는 점을 활용해
    keywords.env 키워드로 직접 필터링해서 불필요한 대량 수집을 피한다.
  - 한 번의 날짜범위 조회는 약 1개월을 넘기면 "입력범위값 초과 에러"가
    나는 것을 확인했다 - lookback_days 기본값을 21일로 보수적으로 잡는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import requests

from adapters.base import Adapter
from common.schema import Announcement

BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"

# 업무구분별 오퍼레이션. 지원사업 집행에서 흔한 물품·용역만 우선 대상으로 한다.
OPERATIONS = {
    "THNG": "getBidPblancListInfoThngPPSSrch",  # 물품
    "SERVC": "getBidPblancListInfoServcPPSSrch",  # 용역
}

DETAIL_URL_TMPL = "https://www.g2b.go.kr/ep/invitation/publicity/bidPublicityDtl.do?bidno={no}&bidseq={ord}"


class G2BAdapter(Adapter):
    source = "G2B"
    source_name = "나라장터(조달청)"

    def __init__(
        self,
        service_key: str,
        keywords: list[str],
        lookback_days: int = 21,
        num_of_rows: int = 100,
        max_pages_per_call: int = 10,
        timeout: int = 30,
    ):
        self.service_key = service_key
        self.keywords = keywords
        self.lookback_days = lookback_days
        self.num_of_rows = num_of_rows
        self.max_pages_per_call = max_pages_per_call
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        if not self.keywords:
            return []

        now = datetime.now()
        begin = (now - timedelta(days=self.lookback_days)).strftime("%Y%m%d0000")
        end = now.strftime("%Y%m%d2359")

        seen_ids: set[str] = set()
        results: list[Announcement] = []

        for op_key, operation in OPERATIONS.items():
            for keyword in self.keywords:
                for row in self._fetch_operation(operation, keyword, begin, end):
                    bid_no = row.get("bidNtceNo") or ""
                    bid_ord = row.get("bidNtceOrd") or "000"
                    uid = f"{bid_no}-{bid_ord}"
                    if not bid_no or uid in seen_ids:
                        continue
                    seen_ids.add(uid)

                    title = (row.get("bidNtceNm") or "").strip()
                    org = (row.get("ntceInsttNm") or row.get("dminsttNm") or "").strip()
                    start = (row.get("bidBeginDt") or "").strip() or None
                    end_dt = (row.get("bidClseDt") or "").strip() or None
                    url = (row.get("bidNtceDtlUrl") or row.get("bidNtceUrl") or "").strip()
                    if not url:
                        url = DETAIL_URL_TMPL.format(no=bid_no, ord=bid_ord)

                    period_text = "~".join(p for p in (start, end_dt) if p)
                    results.append(
                        Announcement(
                            source=self.source,
                            source_name=self.source_name,
                            title=title,
                            org=org or self.source_name,
                            period_text=period_text,
                            period_start=start,
                            period_end=end_dt,
                            url=url,
                            collect_method="API",
                            stage="집행단계",
                            external_id=f"G2B-{uid}",
                        )
                    )

        return results

    def _fetch_operation(self, operation: str, keyword: str, begin: str, end: str) -> list[dict]:
        rows: list[dict] = []
        page = 1
        while page <= self.max_pages_per_call:
            resp = requests.get(
                f"{BASE_URL}/{operation}",
                params={
                    "serviceKey": self.service_key,
                    "pageNo": page,
                    "numOfRows": self.num_of_rows,
                    "inqryDiv": 1,
                    "inqryBgnDt": begin,
                    "inqryEndDt": end,
                    "bidNtceNm": keyword,
                    "type": "json",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
            response = payload.get("response", {})
            header = response.get("header", {})
            if header.get("resultCode") != "00":
                # 결과 없음(코드 04 등) 포함 - 예외로 전체를 죽이지 않고 조용히 스킵
                break

            body = response.get("body", {})
            items = body.get("items") or []
            if isinstance(items, dict):
                items = [items]
            if not items:
                break

            rows.extend(items)
            if len(items) < self.num_of_rows:
                break
            page += 1

        return rows
