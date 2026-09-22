"""AJAX(JSON) 응답을 가로채는 크롤러.

KIAT·KOTRA·스마트공장(TIPA)처럼 목록이 페이지 최초 로딩 후 별도
POST/GET 요청(JSON 응답)으로 채워지는 사이트용. 이 요청 파라미터를
직접 흉내 내는 대신, Playwright로 실제 페이지를 열어 브라우저가 스스로
보내는 요청을 가로채기만 한다 - 그래서 서버가 요구하는 세션/토큰 값을
몰라도 되고, 사이트가 파라미터를 바꿔도 응답 URL 패턴만 맞으면 계속
동작한다.

list 설정 예시:
    list:
      url: "https://example.go.kr/board"          # 브라우저로 열 페이지
      capture_url_contains: "selectListAjax.do"     # 가로챌 응답의 URL에 포함될 문자열
      items_path: "data"                            # json_extract 참고
      fields: { ... json_extract.py 상단 docstring 참고 ... }
      pagination:
        click_selector: "a.next-page"                # 다음 페이지 버튼 (선택)
        max_pages: 5
"""
from __future__ import annotations

from adapters.base import Adapter
from common.crawl_config import CrawlTarget
from common.schema import Announcement
from crawlers.json_extract import get_items, items_to_announcements


class PlaywrightCaptureCrawler(Adapter):
    def __init__(self, target: CrawlTarget, keywords: list[str] | None = None):
        self.target = target
        self.source = target.id.upper()
        self.source_name = target.name
        self.cfg = target.raw["list"]
        self.keywords = keywords or []

    def fetch(self) -> list[Announcement]:
        from playwright.sync_api import sync_playwright

        results: list[Announcement] = []
        pagination = self.cfg.get("pagination") or {}
        max_pages = pagination.get("max_pages", 1)
        click_selector = pagination.get("click_selector")
        capture_marker = self.cfg["capture_url_contains"]

        seen_titles: set[str] = set()
        captured: list[dict] = []

        def on_response(response):
            if capture_marker in response.url and response.request.method in ("GET", "POST"):
                try:
                    captured.append(response.json())
                except Exception:  # noqa: BLE001 - 응답이 JSON이 아니면 무시
                    pass

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("response", on_response)
            page.goto(self.cfg["url"], timeout=30000)
            page.wait_for_timeout(self.cfg.get("wait_ms", 1500))

            for _ in range(max_pages):
                new_count = 0
                for payload in captured:
                    items = get_items(payload, self.cfg.get("items_path", ""))
                    page_items = items_to_announcements(
                        items,
                        self.cfg,
                        source=self.source,
                        source_name=self.source_name,
                        org=self.target.org,
                        stage=self.target.stage,
                    )
                    for item in page_items:
                        if item.title in seen_titles:
                            continue
                        seen_titles.add(item.title)
                        results.append(item)
                        new_count += 1
                captured.clear()

                if not click_selector:
                    break
                next_btn = page.query_selector(click_selector)
                if not next_btn:
                    break
                next_btn.click()
                page.wait_for_timeout(self.cfg.get("wait_ms", 1500))
                if new_count == 0:
                    break

            browser.close()

        return results
