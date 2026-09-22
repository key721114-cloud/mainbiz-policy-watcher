"""정적 HTML 게시판용 범용 크롤러.

requests로 목록 페이지를 그대로 받아 CSS 선택자로 파싱한다. JS 실행이
필요 없는 서버사이드 렌더링 게시판(예: 산업통상부, KEIT/SROME, KETEP,
소진공, KOSMES 등 1단계 검증 완료 사이트 대부분)에 사용한다.

새 사이트를 추가할 때는 이 파일을 건드릴 필요 없이 crawl_targets.yaml에
설정 블록만 추가하면 된다 - 선택자 문법은 crawlers/html_extract.py 상단
docstring 참고.

keyword_search 설정이 있으면 "최신 N건"을 훑는 대신 keywords.env의 각
키워드로 사이트 자체 검색을 돌려서 가져온다 - 그래야 게시판 전체가
수천 건이어도(예: KIAT 2,600여 건) 오래된 공고까지 놓치지 않는다.
(실제로 "최신 30건"만 보다가 몇 달 전에 올라온 키워드 매칭 공고를
통째로 놓치는 사고가 있었음 - crawl_targets.yaml 참고)
    keyword_search:
      keyword_param: searchKeyword   # 키워드를 넣을 파라미터명
      extra: {searchCondition: 1}     # 검색모드를 켜기 위한 추가 고정 파라미터(선택)
      max_pages: 3                    # 키워드 1개당 최대 페이지 수(선택, 기본은 pagination.max_pages)
"""
from __future__ import annotations

from adapters.base import Adapter
from common.crawl_config import CrawlTarget
from common.http import get_session
from common.schema import Announcement
from crawlers.html_extract import rows_to_announcements

USER_AGENT = "Mozilla/5.0 (compatible; MainbizPolicyWatcher/1.0)"


class StaticHtmlCrawler(Adapter):
    def __init__(self, target: CrawlTarget, keywords: list[str] | None = None, timeout: int = 30):
        self.target = target
        self.source = target.id.upper()
        self.source_name = target.name
        self.cfg = target.raw["list"]
        self.keywords = keywords or []
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        seen_titles: set[str] = set()
        results: list[Announcement] = []

        keyword_search = self.cfg.get("keyword_search")
        if keyword_search and self.keywords:
            for keyword in self.keywords:
                extra = dict(keyword_search.get("extra", {}))
                extra[keyword_search["keyword_param"]] = keyword
                max_pages = keyword_search.get("max_pages", (self.cfg.get("pagination") or {}).get("max_pages", 1))
                self._fetch_pages(extra, max_pages, seen_titles, results)
        else:
            max_pages = (self.cfg.get("pagination") or {}).get("max_pages", 1)
            self._fetch_pages({}, max_pages, seen_titles, results)

        return results

    def _fetch_pages(
        self,
        extra_params: dict,
        max_pages: int,
        seen_titles: set[str],
        results: list[Announcement],
    ) -> None:
        pagination = self.cfg.get("pagination") or {}
        page_params = pagination.get("params")
        if page_params is None:
            single = pagination.get("param")
            page_params = [single] if single else []

        method = self.cfg.get("method", "GET").upper()
        base_params = {**dict(self.cfg.get("params", {})), **extra_params}
        headers = {"User-Agent": USER_AGENT, **self.cfg.get("headers", {})}
        session = get_session()

        for page in range(1, max_pages + 1):
            params = dict(base_params)
            for p in page_params:
                params[p] = page

            if method == "GET":
                resp = session.get(self.cfg["url"], params=params, headers=headers, timeout=self.timeout)
            else:
                resp = session.post(self.cfg["url"], data=params, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = resp.apparent_encoding

            page_items = rows_to_announcements(
                resp.text,
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

            # 페이지네이션 파라미터가 없거나, 페이지를 넘겨도 새 항목이 없으면 종료
            if not page_params or new_count == 0:
                break
