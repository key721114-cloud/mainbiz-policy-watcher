"""크롤러/어댑터가 공유하는 requests 세션.

일부 국내 공공기관 사이트(예: 소진공)는 구식 SSL 설정을 쓰고 있어
파이썬 최신 OpenSSL 기본값으로는 handshake가 실패한다
(SSLV3_ALERT_HANDSHAKE_FAILURE). 이를 완화한 세션을 공용으로 둔다.
"""
from __future__ import annotations

import ssl

import requests
from requests.adapters import HTTPAdapter


class _LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        try:
            ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT  # Python 3.12+/OpenSSL 3.x
        except AttributeError:
            pass
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.mount("https://", _LegacySSLAdapter())
    return _session
