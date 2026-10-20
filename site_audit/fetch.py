"""Fetch a page once and share it with every agent."""

import gzip
import re
import ssl
import time
import urllib.error
import urllib.request
import zlib
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_BLOCKLIST = ("example.", "exemple.", "sentry", "wixpress", "domain.", "email.com", "votre",
                   "your", "@2x", ".png", ".jpg", ".webp", ".svg", ".gif")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


@dataclass
class Page:
    url: str
    final_url: str = ""
    status: int = 0
    headers: dict = field(default_factory=dict)
    html: str = ""
    elapsed: float = 0.0       # seconds to first full HTML
    transfer_bytes: int = 0    # bytes on the wire
    compressed: bool = False
    cert_invalid: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and 200 <= self.status < 400 and bool(self.html)


def _get(url: str, timeout: float, context=None) -> Page:
    req = urllib.request.Request(url, headers=HEADERS)
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
        raw = resp.read(3_000_000)
        page = Page(url=url, final_url=resp.geturl(), status=resp.status,
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    elapsed=time.monotonic() - t0, transfer_bytes=len(raw))
        charset = resp.headers.get_content_charset() or "utf-8"
    encoding = page.headers.get("content-encoding", "")
    if encoding == "gzip":
        raw, page.compressed = gzip.decompress(raw), True
    elif encoding == "deflate":
        raw, page.compressed = zlib.decompress(raw), True
    page.html = raw.decode(charset, errors="ignore")
    return page


def fetch(url: str, timeout: float = 15) -> Page:
    if "://" not in url:
        url = "https://" + url
    try:
        return _get(url, timeout)
    except urllib.error.URLError as e:
        # Expired / self-signed certificates are common on neglected sites: note it and retry.
        if isinstance(e.reason, ssl.SSLError):
            try:
                page = _get(url, timeout, context=ssl._create_unverified_context())
                page.cert_invalid = True
                return page
            except Exception as e2:  # noqa: BLE001 — any failure means "site unreachable"
                return Page(url=url, error=str(e2))
        if url.startswith("https://"):
            try:
                return _get("http://" + url[len("https://"):], timeout)
            except Exception as e2:  # noqa: BLE001
                return Page(url=url, error=str(e2))
        return Page(url=url, error=str(e))
    except Exception as e:  # noqa: BLE001
        return Page(url=url, error=str(e))


def find_email(html: str) -> str:
    mailtos = re.findall(r'mailto:([^"\'?>\s]+)', html, re.I)
    candidates = mailtos + EMAIL_RE.findall(html)
    for email in candidates:
        if not any(b in email.lower() for b in EMAIL_BLOCKLIST):
            return email
    return ""
