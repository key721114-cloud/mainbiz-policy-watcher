"""HTML(BeautifulSoup) 기반 공통 필드 추출 로직.

static_html 드라이버(requests로 받은 원본 HTML)와 playwright_dom 드라이버
(Playwright가 렌더링을 끝낸 뒤의 HTML)가 이 모듈을 공유한다 - 둘 다 결국
'파싱된 HTML + CSS 선택자 설정'만 있으면 되기 때문에, 페이지를 어떻게
가져왔는지와 무관하게 같은 추출 로직을 쓸 수 있다.

list 설정 예시 (crawl_targets.yaml):
    list:
      url: "https://example.go.kr/board"
      method: GET                 # GET | POST
      params: {bCd: 2001}         # 고정 쿼리 파라미터
      row_selector: "table tbody tr"
      pagination:
        param: pageIndex          # 페이지 번호를 담는 쿼리 파라미터명
        max_pages: 5
      fields:
        title:       {selector: "td.title a", attr: text}
        detail_url:  {selector: "td.title a", attr: href, base_url: "https://example.go.kr"}
        period:      {selector: "td.period",  attr: text}   # "2026-01-01 ~ 2026-01-31" 형태 텍스트
        org:         {selector: "td.dept",    attr: text}   # 생략 가능 (생략 시 target.org 사용)
        external_id: {selector: "td.no",      attr: text}   # 생략 가능 (생략 시 title 사용)
"""
from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from common.schema import Announcement
from common.utils import extract_period


def _select(row: Tag, selector: str | None) -> Tag | None:
    """selector가 없거나 'self'면 row 자체를 대상으로 한다.
    (예: 소진공처럼 한 행 전체가 <a>인 경우, detail_url의 attr=href를
    row 자기 자신에서 뽑아야 함 - select_one은 자손만 찾으므로 별도 처리)"""
    if not selector or selector == "self":
        return row
    return row.select_one(selector)


def _extract(el: Tag | None, spec: dict) -> str:
    if el is None:
        return ""
    attr = spec.get("attr", "text")
    if attr == "text":
        raw = el.get_text(strip=True)
    else:
        raw = (el.get(attr) or "").strip()

    if "regex" in spec:
        m = re.search(spec["regex"], raw)
        if not m:
            return ""
        if "template" in spec:
            return spec["template"].format(*m.groups())
        return m.group(1) if m.groups() else m.group(0)

    return raw


def rows_to_announcements(html: str, cfg: dict, source: str, source_name: str, org: str, stage: str) -> list[Announcement]:
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select(cfg["row_selector"])
    fields = cfg["fields"]

    results: list[Announcement] = []
    for row in rows:
        title_spec = fields["title"]
        title = _extract(_select(row, title_spec.get("selector")), title_spec)
        if not title:
            continue

        url = ""
        if "detail_url" in fields:
            link_spec = fields["detail_url"]
            url = _extract(_select(row, link_spec.get("selector")), link_spec)
            if url and link_spec.get("base_url") and not url.startswith("http"):
                url = urljoin(link_spec["base_url"], url)

        period_text = ""
        if "period" in fields:
            period_text = _extract(_select(row, fields["period"].get("selector")), fields["period"])
        start, end = extract_period(period_text)

        row_org = org
        if "org" in fields:
            row_org = _extract(_select(row, fields["org"].get("selector")), fields["org"]) or org

        external_id = title
        if "external_id" in fields:
            external_id = _extract(_select(row, fields["external_id"].get("selector")), fields["external_id"]) or title

        results.append(
            Announcement(
                source=source,
                source_name=source_name,
                title=title,
                org=row_org,
                period_text=period_text,
                period_start=start,
                period_end=end,
                url=url,
                collect_method="CRAWL",
                stage=stage,
                external_id=f"{source}-{external_id}",
            )
        )
    return results
