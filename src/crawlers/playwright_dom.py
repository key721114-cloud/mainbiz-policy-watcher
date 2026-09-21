"""JS 렌더링 후 DOM에서 CSS 선택자로 뽑아내는 크롤러.

static_html과 설정 스키마(list.fields, row_selector 등)는 완전히 동일하다 -
차이는 requests 대신 Playwright로 페이지를 렌더링한 뒤의 최종 HTML을
쓴다는 점뿐이다. 목록이 AJAX로 채워지긴 하지만 결과가 실제 DOM 테이블로
남는 사이트(예: 최초 로딩 후 목록이 표로 그려지는 SPA)에 적합하다.

list 설정 예시 (static_html과 공통 + 추가 키):
    list:
      url: "https://example.go.kr/board"
      wait_selector: "table tbody tr"   # 이 요소가 나타날 때까지 대기
      wait_ms: 1000                      # 추가로 더 기다릴 시간(ms), 선택
      row_selector: "table tbody tr"
      fields: { ... static_html과 동일 ... }

여러 페이지가 '다음' 버튼 클릭으로만 넘어가는 경우 pagination.click_selector에
다음 페이지 버튼의 선택자를 지정한다 (기본은 페이지네이션 없이 1페이지만).
"""
from __future__ import annotations

from adapters.base import Adapter
from common.crawl_config import CrawlTarget
from common.schema import Announcement
from crawlers.html_extract import rows_to_announcements


class PlaywrightDomCrawler(Adapter):
    def __init__(self, target: CrawlTarget):
        self.target = target
        self.source = target.id.upper()
        self.source_name = target.name
        self.cfg = target.raw["list"]

    def fetch(self) -> list[Announcement]:
        from playwright.sync_api import sync_playwright  # 지연 임포트: 이 드라이버를 안 쓰면 설치 불필요

        results: list[Announcement] = []
        pagination = self.cfg.get("pagination") or {}
        max_pages = pagination.get("max_pages", 1)
        click_selector = pagination.get("click_selector")
        wait_selector = self.cfg.get("wait_selector", self.cfg["row_selector"])
        wait_ms = self.cfg.get("wait_ms", 500)

        seen_titles: set[str] = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.cfg["url"], timeout=30000)

            for _ in range(max_pages):
                page.wait_for_selector(wait_selector, timeout=15000)
                page.wait_for_timeout(wait_ms)

                html = page.content()
                page_items = rows_to_announcements(
                    html,
                    self.cfg,
                    source=self.source,
                    source_name=self.source_name,
                    org=self.target.org,
                    stage=self.target.stage,
                )
                new_count = 0
                for item in page_items:
                    if item.title in seen_titles:
                        continue
                    seen_titles.add(item.title)
                    results.append(item)
                    new_count += 1

                if not click_selector or new_count == 0:
                    break
                next_btn = page.query_selector(click_selector)
                if not next_btn:
                    break
                next_btn.click()

            browser.close()

        return results
