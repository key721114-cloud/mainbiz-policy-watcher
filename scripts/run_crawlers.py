"""크롤링 트랙(crawl_targets.yaml에 등록된 사이트) 실행 스크립트.

data/raw_crawl.json을 덮어쓰고, 기존 data/raw_api.json과 합쳐
data/announcements.json(키워드 매칭 + 중복표시 완료)까지 갱신한다.
GitHub Actions에서 하루 1회 실행하는 것을 기본값으로 한다(상대 서버 부담 고려).

실행:
    python scripts/run_crawlers.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from common.crawl_config import load_crawl_targets  # noqa: E402
from common.config import load_keywords  # noqa: E402
from common.schema import now_kst_iso  # noqa: E402
from crawlers.registry import build_crawler  # noqa: E402
from pipeline import RAW_CRAWL_PATH, build_announcements, save_raw, update_source_status  # noqa: E402


def main() -> int:
    keywords = load_keywords(ROOT / "keywords.env")
    targets = load_crawl_targets(ROOT / "crawl_targets.yaml")

    all_results = []
    summary = []
    exit_code = 0

    for target in targets:
        label = f"{target.id}({target.name})"
        if not target.enabled:
            print(f"[SKIP] {label}: enabled=false")
            summary.append((label, "SKIP", 0, "비활성화"))
            continue
        try:
            crawler = build_crawler(target)
            items = crawler.fetch()
            all_results.extend(items)
            print(f"[OK]   {label}: {len(items)}건")
            summary.append((label, "OK", len(items), ""))
        except Exception as exc:  # noqa: BLE001 - 소스 하나 실패해도 계속 진행
            print(f"[FAIL] {label}: {exc}")
            traceback.print_exc()
            summary.append((label, "FAIL", 0, str(exc)))
            exit_code = 1

    save_raw(all_results, ROOT / RAW_CRAWL_PATH)
    update_source_status(ROOT, "crawl", summary)
    matched = build_announcements(ROOT, keywords)

    print("\n=== 요약 ===")
    for label, status, count, err in summary:
        print(f"{status:4} {label:40} {count:5}건  {err}")
    print(f"크롤링 수집 {len(all_results)}건 -> {RAW_CRAWL_PATH}")
    print(f"최종 매칭 결과(API+크롤링 합산) {len(matched)}건 -> data/announcements.json")
    print(f"수집 시각(KST): {now_kst_iso()}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
