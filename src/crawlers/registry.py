"""crawl_targets.yaml의 driver 값 -> 크롤러 클래스 매핑.

새 드라이버 종류를 추가하지 않는 한(즉 기존 3종으로 충분한 한),
새 크롤링 대상 추가는 이 파일도 건드릴 필요가 없다.
"""
from __future__ import annotations

from adapters.base import Adapter
from common.crawl_config import CrawlTarget

_DRIVERS = {}


def _lazy_import():
    if _DRIVERS:
        return
    from crawlers.static_html import StaticHtmlCrawler
    from crawlers.json_api import JsonApiCrawler
    from crawlers.playwright_dom import PlaywrightDomCrawler
    from crawlers.playwright_capture import PlaywrightCaptureCrawler

    _DRIVERS.update(
        {
            "static_html": StaticHtmlCrawler,
            "json_api": JsonApiCrawler,
            "playwright_dom": PlaywrightDomCrawler,
            "playwright_capture": PlaywrightCaptureCrawler,
        }
    )


def build_crawler(target: CrawlTarget, keywords: list[str] | None = None) -> Adapter:
    _lazy_import()
    cls = _DRIVERS.get(target.driver)
    if cls is None:
        raise ValueError(f"알 수 없는 driver: {target.driver} (target={target.id})")
    return cls(target, keywords=keywords)
