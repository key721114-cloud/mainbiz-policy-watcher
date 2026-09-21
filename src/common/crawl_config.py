"""crawl_targets.yaml 로더.

새 크롤링 대상을 늘릴 때 코드를 새로 짜지 않고 이 YAML에 설정 블록만
추가하면 되도록 하는 것이 목적이다 (config-driven 크롤러).

각 항목은 다음 형태를 따른다:

    - id: motie                      # source 코드로 쓰임 (대문자로 변환)
      name: 산업통상부(본체)          # source_name
      org: 산업통상부                 # Announcement.org 기본값
      stage: 모집공고                 # 모집공고 | 집행단계
      driver: static_html             # static_html | playwright_capture | playwright_dom
      list: { ... 드라이버별 세부 설정 ... }

driver별 list 설정은 각 크롤러 구현(src/crawlers/*)의 docstring을 참고.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class CrawlTarget:
    id: str
    name: str
    org: str
    stage: str = "모집공고"
    driver: str = "static_html"
    enabled: bool = True
    raw: dict = field(default_factory=dict)  # 드라이버가 참조하는 원본 설정 전체


def load_crawl_targets(path: Path) -> list[CrawlTarget]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    targets: list[CrawlTarget] = []
    for entry in data:
        targets.append(
            CrawlTarget(
                id=entry["id"],
                name=entry.get("name", entry["id"]),
                org=entry.get("org", entry.get("name", entry["id"])),
                stage=entry.get("stage", "모집공고"),
                driver=entry.get("driver", "static_html"),
                enabled=entry.get("enabled", True),
                raw=entry,
            )
        )
    return targets
