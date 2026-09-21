"""외부 소스를 다시 호출하지 않고, 이미 디스크에 있는
data/raw_api.json + data/raw_crawl.json + data/status/*.json만 보고
data/announcements.json과 data/source_status.json을 처음부터 다시 만든다.

GitHub Actions에서 raw 데이터 커밋 -> git pull --rebase 직후에 실행해,
그 시점 레포의 최신 상태(다른 트랙이 먼저 push했을 수도 있는 상태)를
반영한 최종 결과를 만든다. 순수 로컬 계산이라 push 충돌로 재시도해도
비용이 거의 없다 (.github/workflows/*.yml 참고).

실행:
    python scripts/build.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from common.config import load_keywords  # noqa: E402
from pipeline import build_announcements, rebuild_source_status  # noqa: E402


def main() -> int:
    keywords = load_keywords(ROOT / "keywords.env")
    rebuild_source_status(ROOT)
    matched = build_announcements(ROOT, keywords)
    print(f"재생성 완료: {len(matched)}건 -> data/announcements.json, data/source_status.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
