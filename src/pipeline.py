"""API 트랙과 크롤링 트랙을 하나로 합쳐 최종 결과를 만드는 공용 로직.

API(하루 2~3회)와 크롤링(하루 1회)은 서로 다른 주기로 GitHub Actions에서
실행되므로, 각 트랙은 자기 몫의 raw 스냅샷 파일만 덮어쓰고(data/raw_api.json,
data/raw_crawl.json), 두 파일을 합쳐 키워드 매칭·중복 표시까지 마친 결과를
data/announcements.json에 쓴다 - 한쪽 트랙만 실행돼도 다른 쪽의 최신 데이터를
잃지 않는다.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from common.schema import Announcement, now_kst_iso
from dedup import mark_duplicates
from matching import apply_keyword_matching, filter_matched

RAW_API_PATH = "data/raw_api.json"
RAW_CRAWL_PATH = "data/raw_crawl.json"
ANNOUNCEMENTS_PATH = "data/announcements.json"
SOURCE_STATUS_PATH = "data/source_status.json"


def save_raw(items: list[Announcement], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([i.to_dict() for i in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_raw(path: Path) -> list[Announcement]:
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [Announcement(**row) for row in rows]


def build_announcements(root: Path, keywords: list[str]) -> list[Announcement]:
    """raw_api.json + raw_crawl.json을 합쳐 매칭·중복표시된 최종 리스트를 만들고
    data/announcements.json에 저장한다."""
    items = load_raw(root / RAW_API_PATH) + load_raw(root / RAW_CRAWL_PATH)

    apply_keyword_matching(items, keywords)
    matched = filter_matched(items)
    mark_duplicates(matched)

    out_path = root / ANNOUNCEMENTS_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "generated_at": now_kst_iso(),
                "count": len(matched),
                "items": [m.to_dict() for m in matched],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return matched


def update_source_status(root: Path, track: str, summary: list[tuple[str, str, int, str]]) -> None:
    """소스별 마지막 실행 결과(성공/실패, 시각, 건수)를 누적 기록한다.
    담당 소스가 일정 기간 이상 계속 실패하면(4단계 모니터링 요구사항) 이 파일을
    보고 판단할 수 있다 - 알림 발송 자체는 아직 구현하지 않음."""
    path = root / SOURCE_STATUS_PATH
    status: dict = {}
    if path.exists():
        status = json.loads(path.read_text(encoding="utf-8"))

    now = now_kst_iso()
    for label, result, count, err in summary:
        entry = status.setdefault(label, {"track": track})
        entry["track"] = track
        entry["last_run_at"] = now
        entry["last_status"] = result
        entry["last_count"] = count
        if result == "OK":
            entry["last_success_at"] = now
            entry["last_error"] = ""
        else:
            entry["last_error"] = err

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
