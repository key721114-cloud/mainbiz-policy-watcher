"""로컬에서 API 트랙 + 크롤링 트랙을 한 번에 전부 돌려보는 편의 스크립트.

실제 운영에서는 이 스크립트를 쓰지 않는다 - GitHub Actions에서
run_api_adapters.py(하루 2~3회)와 run_crawlers.py(하루 1회)를 각자 주기로
따로 실행한다(scripts/README나 .github/workflows 참고). 이 스크립트는
"전체가 다 잘 도나" 로컬 점검용이며, 두 스크립트를 순서대로 호출해
data/raw_api.json과 data/raw_crawl.json을 둘 다 최신 상태로 만든다.

실행:
    python scripts/run_pipeline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import run_api_adapters  # noqa: E402
import run_crawlers  # noqa: E402


def main() -> int:
    print("=== API 트랙 ===")
    api_exit = run_api_adapters.main()
    print("\n=== 크롤링 트랙 ===")
    crawl_exit = run_crawlers.main()
    return api_exit or crawl_exit


if __name__ == "__main__":
    raise SystemExit(main())
