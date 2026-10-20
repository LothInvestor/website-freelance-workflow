"""Shared helpers: .env loading, phone normalisation, CSV I/O."""

import csv
import os
import re
import sys
from pathlib import Path

LEAD_FIELDS = [
    "id", "name", "category", "address", "city", "phone", "phone_e164",
    "is_mobile", "email", "website", "website_status", "quality", "verdict", "issues",
    "pitch", "score", "rating", "reviews", "maps_url", "query",
]


def load_env(path: str = ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines) so we need no extra dependency."""
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console otherwise mangles accents
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize_phone(raw: str, default_cc: str = "33") -> str:
    """Return digits-only international number (no +), or '' if unusable."""
    if not raw:
        return ""
    raw = raw.strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        return digits
    if digits.startswith("00"):
        return digits[2:]
    if digits.startswith("0") and len(digits) == 10:
        return default_cc + digits[1:]
    if digits.startswith(default_cc):
        return digits
    return ""


def is_mobile(e164: str) -> bool:
    """WhatsApp only makes sense on mobiles. Rules for FR/BE/CH; unknown → True."""
    if e164.startswith("33"):
        return e164[2:3] in ("6", "7")
    if e164.startswith("32"):
        return e164[2:3] == "4"
    if e164.startswith("41"):
        return e164[2:4] in ("75", "76", "77", "78", "79")
    return True


def read_csv(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
