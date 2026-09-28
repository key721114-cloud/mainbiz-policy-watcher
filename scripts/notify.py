"""새 공고 메일 알림 발송 스크립트.

GitHub Actions에서 최종 결과(data/announcements.json) 커밋 직후 실행한다.
대시보드의 "메일 알림" 폼(api/subscribe.js)으로 등록된 구독자 목록을 Upstash Redis에서
읽어, 이번에 처음 보는 공고 중 구독 키워드에 맞는 것만 모아 구독자별로 메일 1통씩 보낸다.

"처음 보는 공고" 판별은 Redis 집합(notified)에 SADD해서 새로 들어간 것만 고른다.
SADD가 원자적이라 API/크롤링 두 트랙이 거의 동시에 돌아도 같은 공고를 두 번 보내지 않는다.
맨 처음 실행 때는 이미 쌓여 있는 공고 전체를 "본 것"으로 등록만 하고 메일은 보내지 않는다
(안 그러면 첫 메일에 수백 건이 몰림).

필요한 환경변수 (GitHub Secrets) - 하나라도 없으면 아무것도 안 하고 정상 종료:
    KV_REST_API_URL / KV_REST_API_TOKEN   Upstash Redis REST (Vercel 연동 시 발급)
    GMAIL_USER / GMAIL_APP_PASSWORD        발신용 Gmail 계정과 앱 비밀번호

실행:
    python scripts/notify.py
    python scripts/notify.py --test someone@example.com   # 발송 확인용: 유효 공고 5건을 테스트 메일로
                                                           # 1통 보냄 (발송 기록/구독자 목록은 안 건드림)
"""
from __future__ import annotations

import html
import json
import os
import re
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from common.schema import KST  # noqa: E402

DASHBOARD_URL = "https://policy-watcher-key721114-6031s-projects.vercel.app/"
SENDER_NAME = "정책사업팀 공고 모니터링"
SUBSCRIBERS_KEY = "subscribers"
NOTIFIED_KEY = "notified"
SEEDED_KEY = "notified:seeded"


class Redis:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}

    def call(self, *command):
        r = requests.post(self.url, headers=self.headers, json=list(command), timeout=30)
        r.raise_for_status()
        return r.json()["result"]

    def pipeline(self, commands: list[list]) -> list:
        results = []
        for i in range(0, len(commands), 500):
            r = requests.post(f"{self.url}/pipeline", headers=self.headers, json=commands[i:i + 500], timeout=60)
            r.raise_for_status()
            results.extend(x.get("result") for x in r.json())
        return results


def item_key(item: dict) -> str:
    return f"{item.get('source')}:{item.get('external_id') or item.get('url')}"


def title_year(title: str) -> int | None:
    """제목에 적힌 연도 중 가장 늦은 해 (index.html의 titleYear()와 같은 규칙)."""
    years = [int(y) for y in re.findall(r"(?:^|\D)(20\d{2})(?!\d)", title)]
    for yy in re.findall(r"(?:^|\D)(\d{2})\s*년(?!\s*(?:이상|이내|미만|초과|간|차|째|만))", title):
        if int(yy) >= 15:
            years.append(2000 + int(yy))
    return max(years) if years else None


def is_open(item: dict, today: str) -> bool:
    """대시보드 기준으로 '마감'이 아닌 공고인지."""
    end = (item.get("period_end") or "")[:10]
    if not end and re.match(r"^\d{4}-\d{2}-\d{2}", item.get("period_text") or ""):
        end = item["period_text"][:10]
    if end:
        return end >= today
    year = title_year(item.get("title") or "")
    return not (year and year < int(today[:4]))


def deadline_label(item: dict, today: str) -> str:
    end = (item.get("period_end") or "")[:10]
    if not end:
        return item.get("period_text") or "상시/미상"
    days = (datetime.fromisoformat(end) - datetime.fromisoformat(today)).days
    return "오늘마감" if days == 0 else f"D-{days} ({end})"


def build_mail(items: list[dict], today: str) -> tuple[str, str]:
    kw_counts: dict[str, int] = {}
    for it in items:
        for k in it.get("matched_keywords") or []:
            kw_counts[k] = kw_counts.get(k, 0) + 1
    kw_summary = ", ".join(k for k, _ in sorted(kw_counts.items(), key=lambda x: -x[1])[:3])
    subject = f"[공고알림] 새 공고 {len(items)}건" + (f" — {kw_summary}" if kw_summary else "")

    rows = []
    for it in items:
        rows.append(
            '<tr><td style="padding:12px 0;border-bottom:1px solid #e3e3df">'
            f'<a href="{html.escape(it.get("url") or DASHBOARD_URL)}" style="color:#2f5c4a;font-weight:600;'
            f'text-decoration:none;font-size:15px">{html.escape(it.get("title") or "")}</a>'
            f'<div style="color:#68675f;font-size:13px;margin-top:4px">'
            f'{html.escape(it.get("source_name") or "")}'
            f'{" · " + html.escape(it["org"]) if it.get("org") else ""}'
            f' · <b style="color:#b3432f">{html.escape(deadline_label(it, today))}</b></div>'
            f'<div style="color:#9b9a90;font-size:12px;margin-top:2px">키워드: '
            f'{html.escape(", ".join(it.get("matched_keywords") or []))}</div></td></tr>'
        )
    body = (
        '<div style="font-family:\'Malgun Gothic\',sans-serif;max-width:640px;color:#1c1c1a">'
        f'<h2 style="font-size:18px;margin:0 0 4px">구독하신 키워드의 새 공고 {len(items)}건</h2>'
        '<p style="color:#68675f;font-size:13px;margin:0 0 8px">정책사업팀 사업공고 모니터링웹에서 '
        '방금 새로 수집된 공고입니다.</p>'
        f'<table style="width:100%;border-collapse:collapse">{"".join(rows)}</table>'
        '<p style="color:#9b9a90;font-size:12px;margin-top:20px">'
        f'<a href="{DASHBOARD_URL}" style="color:#2f5c4a">대시보드 열기</a> · '
        '구독 키워드 변경이나 해지는 대시보드 상단의 "메일 알림" 버튼에서 할 수 있습니다.</p></div>'
    )
    return subject, body


def send_mail(smtp: smtplib.SMTP, sender: str, to: str, subject: str, body: str) -> None:
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((SENDER_NAME, sender))
    msg["To"] = to
    smtp.sendmail(sender, [to], msg.as_string())


def send_test(to: str, gmail_user: str, gmail_pw: str, items: list[dict], today: str) -> int:
    sample = sorted((it for it in items if is_open(it, today)), key=lambda it: it.get("period_end") or "9999-99-99")[:5]
    subject, body = build_mail(sample, today)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(gmail_user, gmail_pw)
        send_mail(smtp, gmail_user, to, "[테스트] " + subject, body)
    print(f"테스트 메일 발송: {to} ({len(sample)}건)")
    return 0


def main() -> int:
    redis_url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    redis_token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not (redis_url and redis_token and gmail_user and gmail_pw):
        print("메일 알림 설정(Redis/Gmail Secrets)이 없어 건너뜀")
        return 0

    items = json.loads((ROOT / "data" / "announcements.json").read_text(encoding="utf-8"))["items"]
    items = [it for it in items if not it.get("is_duplicate")]
    today = datetime.now(KST).strftime("%Y-%m-%d")
    if len(sys.argv) == 3 and sys.argv[1] == "--test":
        return send_test(sys.argv[2], gmail_user, gmail_pw, items, today)

    db = Redis(redis_url, redis_token)

    if not db.call("EXISTS", SEEDED_KEY):
        db.pipeline([["SADD", NOTIFIED_KEY, item_key(it)] for it in items])
        db.call("SET", SEEDED_KEY, datetime.now(KST).isoformat(timespec="seconds"))
        print(f"첫 실행: 기존 공고 {len(items)}건을 발송 완료로 등록만 하고 메일은 보내지 않음")
        return 0

    added = db.pipeline([["SADD", NOTIFIED_KEY, item_key(it)] for it in items])
    new_items = [it for it, r in zip(items, added) if r == 1 and is_open(it, today)]
    print(f"새 공고 {sum(1 for r in added if r == 1)}건 (그중 유효 공고 {len(new_items)}건)")
    if not new_items:
        return 0

    flat = db.call("HGETALL", SUBSCRIBERS_KEY) or []
    subscribers = [json.loads(v) for v in flat[1::2]]
    new_items.sort(key=lambda it: (it.get("period_end") or "9999-99-99"))

    failures = 0
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(gmail_user, gmail_pw)
        for sub in subscribers:
            wanted = set(sub.get("keywords") or [])
            mine = [it for it in new_items if not wanted or wanted & set(it.get("matched_keywords") or [])]
            if not mine:
                continue
            subject, body = build_mail(mine, today)
            try:
                send_mail(smtp, gmail_user, sub["email"], subject, body)
                print(f"발송: {sub['email']} ({len(mine)}건)")
            except smtplib.SMTPException as e:
                failures += 1
                print(f"발송 실패: {sub['email']} - {e}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
