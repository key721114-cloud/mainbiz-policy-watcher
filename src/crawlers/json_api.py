"""순수 REST/JSON 엔드포인트용 범용 크롤러 (Playwright 불필요).

세션/토큰 없이 그냥 requests로 GET·POST하면 JSON을 돌려주는 사이트에 쓴다
(예: TIPA 스마트공장 사업관리시스템). 응답이 세션/CSRF 토큰을 요구하거나
브라우저가 스스로 보내는 요청을 흉내 내기 어려우면 대신 playwright_capture를
쓴다.

list 설정 예시:
    list:
      url: "https://example.go.kr/api/list"
      method: POST
      request_format: json        # json | form  (기본 json)
      warmup_url: "https://example.go.kr/board"  # 먼저 GET해서 세션 쿠키를 받아야 하는 경우(선택)
      body: {key: "list", rcptStts: ""}   # 고정 요청 바디
      items_path: "rcrtPbancList"          # json_extract.py 참고
      fields: { ... json_extract.py 상단 docstring 참고 ... }
      pagination:
        param: pageIndex            # body 안에 페이지 번호를 넣을 키 (선택)
        max_pages: 3

keyword_search 설정이 있으면 "최신 N건"을 훑는 대신 keywords.env의 각
키워드로 사이트 자체 검색을 돌려서 가져온다 (static_html.py와 동일한 설계
의도 - 상단 docstring 참고).
    keyword_search:
      keyword_param: rcrtPbancNm   # 키워드를 넣을 body 키
      extra: {searchG: title}       # 검색모드를 켜기 위한 추가 고정 body 값(선택)
      max_pages: 3
"""
from __future__ import annotations

from adapters.base import Adapter
from common.crawl_config import CrawlTarget
from common.http import get_session
from common.schema import Announcement
from crawlers.json_extract import get_items, items_to_announcements

USER_AGENT = "Mozilla/5.0 (compatible; MainbizPolicyWatcher/1.0)"


class JsonApiCrawler(Adapter):
    def __init__(self, target: CrawlTarget, keywords: list[str] | None = None, timeout: int = 30):
        self.target = target
        self.source = target.id.upper()
        self.source_name = target.name
        self.cfg = target.raw["list"]
        self.keywords = keywords or []
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        session = get_session()
        if warmup_url := self.cfg.get("warmup_url"):
            session.get(warmup_url, headers={"User-Agent": USER_AGENT}, timeout=self.timeout)

        seen_titles: set[str] = set()
        results: list[Announcement] = []

        keyword_search = self.cfg.get("keyword_search")
        if keyword_search and self.keywords:
            for keyword in self.keywords:
                extra = dict(keyword_search.get("extra", {}))
                extra[keyword_search["keyword_param"]] = keyword
                max_pages = keyword_search.get("max_pages", (self.cfg.get("pagination") or {}).get("max_pages", 1))
                self._fetch_pages(session, extra, max_pages, seen_titles, results)
        else:
            max_pages = (self.cfg.get("pagination") or {}).get("max_pages", 1)
            self._fetch_pages(session, {}, max_pages, seen_titles, results)

        return results

    def _fetch_pages(
        self,
        session,
        extra_body: dict,
        max_pages: int,
        seen_titles: set[str],
        results: list[Announcement],
    ) -> None:
        pagination = self.cfg.get("pagination") or {}
        page_param = pagination.get("param")

        method = self.cfg.get("method", "GET").upper()
        is_json_body = self.cfg.get("request_format", "json") == "json"
        base_body = {**dict(self.cfg.get("body", {})), **extra_body}
        headers = {"User-Agent": USER_AGENT, **self.cfg.get("headers", {})}
        if is_json_body:
            headers.setdefault("Content-Type", "application/json;charset=UTF-8")

        for page in range(1, max_pages + 1):
            body = dict(base_body)
            if page_param:
                body[page_param] = page

            if method == "GET":
                resp = session.get(self.cfg["url"], params=body, headers=headers, timeout=self.timeout)
            elif is_json_body:
                resp = session.post(self.cfg["url"], json=body, headers=headers, timeout=self.timeout)
            else:
                resp = session.post(self.cfg["url"], data=body, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            payload = resp.json()

            items = get_items(payload, self.cfg.get("items_path", ""))
            page_items = items_to_announcements(
                items,
                self.cfg,
                source=self.source,
                source_name=self.source_name,
                org=self.target.org,
                stage=self.target.stage,
            )
            if not page_items:
                break

            new_count = 0
            for item in page_items:
                if item.title in seen_titles:
                    continue
                seen_titles.add(item.title)
                results.append(item)
                new_count += 1

            if page_param is None or new_count == 0:
                break
