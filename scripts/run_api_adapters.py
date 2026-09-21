"""API 트랙(중기부·K-Startup·기업마당·나라장터) 실행 스크립트.

data/raw_api.json을 덮어쓰고, 기존 data/raw_crawl.json과 합쳐
data/announcements.json(키워드 매칭 + 중복표시 완료)까지 갱신한다.
GitHub Actions에서 하루 2~3회 실행하는 것을 기본값으로 한다.

실행:
    python scripts/run_api_adapters.py

api_keys.env는 프로젝트 루트에 있어야 하며(.gitignore 처리됨),
GitHub Actions 등 CI 환경에서는 같은 이름의 환경변수(Repository Secrets)를
그대로 사용한다 (common.config.get_setting 참고).
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from adapters.bizinfo import BizinfoAdapter  # noqa: E402
from adapters.g2b import G2BAdapter  # noqa: E402
from adapters.kstartup import KStartupAdapter  # noqa: E402
from adapters.mss import MSSAdapter  # noqa: E402
from common.config import get_setting, load_env_file, load_keywords  # noqa: E402
from common.schema import now_kst_iso  # noqa: E402
from pipeline import RAW_API_PATH, build_announcements, save_raw, update_source_status  # noqa: E402


def build_adapters(api_keys: dict[str, str], keywords: list[str]):
    adapters = []
    if key := get_setting("MSS_API_KEY", api_keys):
        adapters.append(MSSAdapter(service_key=key))
    if key := get_setting("KSTARTUP_API_KEY", api_keys):
        adapters.append(KStartupAdapter(service_key=key))
    if key := get_setting("BIZINFO_API_KEY", api_keys):
        adapters.append(BizinfoAdapter(crtfc_key=key))
    if key := get_setting("G2B_API_KEY", api_keys):
        adapters.append(G2BAdapter(service_key=key, keywords=keywords))
    return adapters


def main() -> int:
    api_keys = load_env_file(ROOT / "api_keys.env")
    keywords = load_keywords(ROOT / "keywords.env")

    adapters = build_adapters(api_keys, keywords)

    all_results = []
    summary = []
    exit_code = 0

    for adapter in adapters:
        label = f"{adapter.source}({adapter.source_name})"
        try:
            items = adapter.fetch()
            all_results.extend(items)
            print(f"[OK]   {label}: {len(items)}건")
            summary.append((label, "OK", len(items), ""))
        except Exception as exc:  # noqa: BLE001 - 소스 하나 실패해도 계속 진행
            print(f"[FAIL] {label}: {exc}")
            traceback.print_exc()
            summary.append((label, "FAIL", 0, str(exc)))
            exit_code = 1

    save_raw(all_results, ROOT / RAW_API_PATH)
    update_source_status(ROOT, "api", summary)
    matched = build_announcements(ROOT, keywords)

    print("\n=== 요약 ===")
    for label, status, count, err in summary:
        print(f"{status:4} {label:30} {count:5}건  {err}")
    print(f"API 수집 {len(all_results)}건 -> {RAW_API_PATH}")
    print(f"최종 매칭 결과(API+크롤링 합산) {len(matched)}건 -> data/announcements.json")
    print(f"수집 시각(KST): {now_kst_iso()}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
