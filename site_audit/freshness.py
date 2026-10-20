"""Freshness agent — is the site abandoned or built on dated tech?"""

import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime

from .fetch import Page
from .report import Report

COPYRIGHT_RE = re.compile(
    r"(?:©|&copy;|&#169;|copyright)\s*(?:[^<\d]{0,40})?((?:19|20)\d{2})(?:\s*[-–/à]\s*((?:19|20)\d{2}))?",
    re.I,
)
YEAR_RE = re.compile(r"\b(20[0-3]\d)\b")
GENERATOR_RE = re.compile(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', re.I)
JQUERY_RE = re.compile(r"jquery[.-]?(\d)\.(\d+)(?:\.\d+)?(?:\.min)?\.js", re.I)
BOOTSTRAP_RE = re.compile(r"bootstrap[/@.-]?(\d)\.\d+(?:\.\d+)?", re.I)
# Builders whose presence alone signals a 2000s/early-2010s site.
LEGACY_GENERATORS = ("frontpage", "dreamweaver", "website x5", "web acappella", "iweb",
                     "netobjects", "homestead", "namo", "wysiwyg web builder")


def _visible_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"<[^>]+>", " ", html)


def run(page: Page) -> Report:
    r = Report("freshness")
    html, this_year = page.html, date.today().year

    # 1. Copyright year (the end of a range wins: "© 2012-2019" → 2019).
    years = [int(m.group(2) or m.group(1)) for m in COPYRIGHT_RE.finditer(html)]
    years = [y for y in years if 1995 <= y <= this_year]
    if years:
        cy = max(years)
        r.data["copyright_year"] = cy
        age = this_year - cy
        if age >= 5:
            r.add(30, f"affiche encore un copyright de {cy}")  # critical (judge.CRITICAL)
        elif age >= 2:
            r.add(15, f"affiche un copyright de {cy}, signe qu'il n'est plus mis à jour")
    elif "{year}" not in html and "new Date().getFullYear" not in html:
        r.data["copyright_year"] = None

    # 2. Most recent year mentioned anywhere in the visible text (news, events, prices…).
    text_years = [int(y) for y in YEAR_RE.findall(_visible_text(html)) if int(y) <= this_year]
    if text_years:
        latest = max(text_years)
        r.data["latest_year_in_text"] = latest
        if this_year - latest >= 3 and not years:
            r.add(15, f"ne mentionne aucune actualité plus récente que {latest}")

    # 3. Last-Modified header (often missing, only penalise when clearly old).
    if lm := page.headers.get("last-modified"):
        try:
            modified = parsedate_to_datetime(lm)
            r.data["last_modified"] = modified.date().isoformat()
            if (datetime.now(modified.tzinfo) - modified).days > 3 * 365:
                r.add(10, f"n'a pas été modifié depuis {modified.year}")
        except (TypeError, ValueError):
            pass

    # 4. Generator / CMS version.
    if m := GENERATOR_RE.search(html):
        gen = m.group(1)
        r.data["generator"] = gen
        low = gen.lower()
        if any(g in low for g in LEGACY_GENERATORS):
            r.add(25, f"a été construit avec {gen}, un outil des années 2000")
        elif wp := re.search(r"wordpress\s*(\d+)\.(\d+)", low):
            if int(wp.group(1)) < 6:
                r.add(15, f"tourne sur une version obsolète de WordPress ({wp.group(1)}.{wp.group(2)}), risque de sécurité")
        elif "joomla! 1." in low or "joomla! 2." in low or re.search(r"drupal [67]\b", low):
            r.add(15, f"tourne sur un CMS en fin de vie ({gen})")

    # 5. Dated front-end libraries.
    if m := JQUERY_RE.search(html):
        major = int(m.group(1))
        r.data["jquery"] = f"{m.group(1)}.{m.group(2)}"
        if major < 3:
            r.add(10, f"utilise jQuery {m.group(1)}.{m.group(2)}, une librairie de plus de 10 ans")
    if m := BOOTSTRAP_RE.search(html):
        r.data["bootstrap"] = m.group(1)
        if int(m.group(1)) < 4:
            r.add(5, "repose sur un framework CSS ancien (Bootstrap 2/3)")

    # 6. Markup that screams 2005.
    low = html.lower()
    if ".swf" in low or "shockwave-flash" in low:
        r.add(25, "contient encore du Flash, illisible sur tous les navigateurs actuels")
    if "<frameset" in low or "<frame " in low:
        r.add(25, "utilise des cadres (frames), une technique abandonnée")
    if "<marquee" in low or "<blink" in low:
        r.add(10, "utilise des textes défilants façon années 2000")
    if low.count("<font") >= 3 or low.count("<center") >= 2:
        r.add(10, "est codé avec des balises HTML obsolètes")
    tables = low.count("<table")
    if tables >= 4 and "display:flex" not in low.replace(" ", "") and "display:grid" not in low.replace(" ", ""):
        r.add(10, "est mis en page avec des tableaux, comme dans les années 2000")
    if not low.lstrip().startswith("<!doctype html>") and "<!doctype html public" in low[:300]:
        r.add(5, "n'est pas en HTML5")
    r.data["tables"] = tables
    return r
