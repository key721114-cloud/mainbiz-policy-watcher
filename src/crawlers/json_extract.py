"""JSON(dict) 기반 공통 필드 추출 로직.

playwright_capture 드라이버(AJAX 응답을 가로채서 얻은 JSON)와, 필요하면
향후 만들 수 있는 순수 REST 크롤러가 이 모듈을 공유한다.

list.items_path: 응답 JSON에서 공고 배열이 있는 위치 (점 표기, 예: "data" 또는
    "response.body.items"). 최상위가 이미 배열이면 빈 문자열("")로 둔다.
list.fields 필드 스펙:
    {"key": "biz_pbanc_nm"}                       - item[key] 그대로 사용
    {"path": "a.b.c"}                              - item 안에서 점 표기로 중첩 탐색
    {"template": "https://x.go.kr/{seq}", ...}      - 템플릿의 {필드명}을 item에서 채움
"""
from __future__ import annotations

from common.schema import Announcement
from common.utils import extract_period


def _get_path(obj: dict, path: str):
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _extract(item: dict, spec: dict) -> str:
    # template이 있으면 item의 여러 필드를 조합해야 하는 경우이므로 최우선 처리
    # (예: detail_url을 id 필드로부터 조립). key/path는 template 없이 단일
    # 필드를 그대로 쓸 때만 쓰인다.
    if "template" in spec:
        try:
            return spec["template"].format(**item)
        except (KeyError, IndexError):
            return ""
    elif "key" in spec:
        val = item.get(spec["key"])
    elif "path" in spec:
        val = _get_path(item, spec["path"])
    else:
        return ""
    return "" if val is None else str(val).strip()


def get_items(payload, items_path: str) -> list[dict]:
    if not items_path:
        return payload if isinstance(payload, list) else []
    val = _get_path(payload, items_path) if isinstance(payload, dict) else None
    if isinstance(val, dict):
        val = [val]
    return val or []


def items_to_announcements(items: list[dict], cfg: dict, source: str, source_name: str, org: str, stage: str) -> list[Announcement]:
    fields = cfg["fields"]
    results: list[Announcement] = []

    for item in items:
        title = _extract(item, fields["title"])
        if not title:
            continue

        url = _extract(item, fields["detail_url"]) if "detail_url" in fields else ""

        period_text = _extract(item, fields["period"]) if "period" in fields else ""
        start = _extract(item, fields["period_start"]) if "period_start" in fields else None
        end = _extract(item, fields["period_end"]) if "period_end" in fields else None
        if not start and not end and period_text:
            start, end = extract_period(period_text)
        if not period_text and (start or end):
            period_text = "~".join(p for p in (start, end) if p)

        row_org = _extract(item, fields["org"]) if "org" in fields else org
        row_org = row_org or org

        external_id = _extract(item, fields["external_id"]) if "external_id" in fields else title

        results.append(
            Announcement(
                source=source,
                source_name=source_name,
                title=title,
                org=row_org,
                period_text=period_text,
                period_start=start or None,
                period_end=end or None,
                url=url,
                collect_method="CRAWL",
                stage=stage,
                external_id=f"{source}-{external_id}",
            )
        )
    return results
