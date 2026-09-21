"""정적 HTML 게시판용 범용 크롤러.

requests로 목록 페이지를 그대로 받아 CSS 선택자로 파싱한다. JS 실행이
필요 없는 서버사이드 렌더링 게시판(예: 산업통상부, KEIT/SROME, KETEP,
소진공, KOSMES 등 1단계 검증 완료 사이트 대부분)에 사용한다.

새 사이트를 추가할 때는 이 파일을 건드릴 필요 없이 crawl_targets.yaml에
설정 블록만 추가하면 된다 - 선택자 문법은 crawlers/html_extract.py 상단
docstring 참고.
"""
from __future__ import annotations

from adapters.base import Adapter
from common.crawl_config import CrawlTarget
from common.http import get_session
from common.schema import Announcement
from crawlers.html_extract import rows_to_announcements

USER_AGENT = "Mozilla/5.0 (compatible; MainbizPolicyWatcher/1.0)"


class StaticHtmlCrawler(Adapter):
    def __init__(self, target: CrawlTarget, timeout: int = 20):
        self.target = target
        self.source = target.id.upper()
        self.source_name = target.name
        self.cfg = target.raw["list"]
        self.timeout = timeout

    def fetch(self) -> list[Announcement]:
        results: list[Announcement] = []
        pagination = self.cfg.get("pagination") or {}
        max_pages = pagination.get("max_pages", 1)
        # 페이지 번호를 담는 파라미터명. 사이트에 따라 여러 파라미터를 동시에
        # 같은 값으로 채워야 하는 경우(KOTRA의 pageNo/pageNo2/pageNoA 등)가
        # 있어 문자열 하나(param) 또는 리스트(params)를 모두 지원한다.
        page_params = pagination.get("params")
        if page_params is None:
            single = pagination.get("param")
            page_params = [single] if single else []

        method = self.cfg.get("method", "GET").upper()
        base_params = dict(self.cfg.get("params", {}))
        headers = {"User-Agent": USER_AGENT, **self.cfg.get("headers", {})}

        seen_titles: set[str] = set()

        for page in range(1, max_pages + 1):
            params = dict(base_params)
            for p in page_params:
                params[p] = page

            session = get_session()
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

        return results
