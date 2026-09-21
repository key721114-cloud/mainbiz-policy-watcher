"""API 트랙과 크롤링 트랙을 하나로 합쳐 최종 결과를 만드는 공용 로직.

API(하루 2~3회)와 크롤링(하루 1회)은 서로 다른 주기로 GitHub Actions에서
실행되므로, 각 트랙은 자기 몫의 파일만 덮어쓴다:
  - data/raw_api.json / data/raw_crawl.json        (원본 수집 결과)
  - data/status/api_last_run.json / crawl_last_run.json  (이번 실행 요약)

announcements.json과 source_status.json은 절대 git으로 merge/rebase하지
않는다 - 두 트랙이 거의 동시에 실행되면 통째로 다시 쓰는 이 두 파일은
git이 자동으로 합칠 수 없는 충돌을 일으키기 때문이다(실제로 겪은 문제).
대신 build_announcements()/rebuild_source_status()를 "git pull 직후"에
다시 호출해서, 그 시점 레포 상태(두 raw 파일 + 두 last_run 파일)만 보고
매번 처음부터 새로 만든다 - 외부 API를 다시 호출하지 않는 순수 로컬 계산이라
충돌 시 재시도해도 비용이 거의 없다 (scripts/build.py, .github/workflows 참고).
"""
from __future__ import annotations

import json
from pathlib import Path

from common.schema import Announcement, now_kst_iso
from dedup import mark_duplicates
from matching import apply_keyword_matching, filter_matched

RAW_API_PATH = "data/raw_api.json"
RAW_CRAWL_PATH = "data/raw_crawl.json"
ANNOUNCEMENTS_PATH = "data/announcements.json"
SOURCE_STATUS_PATH = "data/source_status.json"
API_RUN_SUMMARY_PATH = "data/status/api_last_run.json"
CRAWL_RUN_SUMMARY_PATH = "data/status/crawl_last_run.json"

Summary = list[tuple[str, str, int, str]]  # (label, "OK"|"FAIL"|"SKIP", count, error)


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


def save_run_summary(path: Path, summary: Summary) -> None:
    """이번 실행의 소스별 결과를 자기 트랙 전용 파일에 통째로 덮어쓴다.
    이 파일은 이 트랙만 쓰므로 git rebase 충돌이 사실상 발생하지 않는다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = now_kst_iso()
    rows = [
        {"label": label, "status": status, "count": count, "error": error, "run_at": now}
        for label, status, count, error in summary
    ]
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def load_run_summary(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def build_announcements(root: Path, keywords: list[str]) -> list[Announcement]:
    """raw_api.json + raw_crawl.json을 합쳐 매칭·중복표시된 최종 리스트를 만들고
    data/announcements.json에 저장한다. 순수하게 로컬 파일만 읽는 함수라
    몇 번을 다시 불러도(rebuild) 안전하고 저렴하다."""
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


def rebuild_source_status(root: Path) -> None:
    """data/status/{api,crawl}_last_run.json 두 파일만 보고 source_status.json을
    처음부터 다시 만든다 (누적 병합이 아니라 매번 전체 재생성 - 이래야
    git으로 절대 merge/rebase하지 않고 그냥 덮어써도 항상 정확하다)."""
    status: dict = {}
    for track, path in (("api", root / API_RUN_SUMMARY_PATH), ("crawl", root / CRAWL_RUN_SUMMARY_PATH)):
        for row in load_run_summary(path):
            entry = status.setdefault(row["label"], {"track": track})
            entry["track"] = track
            entry["last_run_at"] = row["run_at"]
            entry["last_status"] = row["status"]
            entry["last_count"] = row["count"]
            if row["status"] == "OK":
                entry["last_success_at"] = row["run_at"]
                entry["last_error"] = ""
            else:
                entry["last_error"] = row["error"]

    out_path = root / SOURCE_STATUS_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
