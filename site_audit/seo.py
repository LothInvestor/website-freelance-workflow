"""SEO agent — can Google (and Google Maps) understand the site?"""

import re

from .fetch import Page
from .report import Report


def _meta(low: str, name: str) -> str:
    m = (re.search(rf'<meta[^>]+(?:name|property)=["\']{name}["\'][^>]+content=["\']([^"\']*)', low)
         or re.search(rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name|property)=["\']{name}["\']', low))
    return m.group(1).strip() if m else ""


def run(page: Page, pagespeed: dict | None = None) -> Report:
    r = Report("seo")
    low = page.html.lower()

    title = re.search(r"<title[^>]*>(.*?)</title>", low, re.S)
    title = title.group(1).strip() if title else ""
    r.data["title"] = title[:120]
    if not title:
        r.add(15, "n'a pas de titre de page pour Google")
    elif len(title) < 15 or title in ("accueil", "home", "index", "untitled", "sans titre"):
        r.add(10, f"a un titre de page trop vague (« {title} ») pour être trouvé sur Google")

    if not _meta(low, "description"):
        r.add(10, "n'a pas de description pour Google")

    h1 = len(re.findall(r"<h1\b", low))
    r.data["h1"] = h1
    if h1 == 0:
        r.add(5, "n'a pas de titre principal (H1)")

    imgs = re.findall(r"<img\b[^>]*>", low)
    if len(imgs) >= 5:
        missing_alt = sum(1 for i in imgs if not re.search(r'alt=["\'][^"\']+', i))
        r.data["img_missing_alt"] = missing_alt
        if missing_alt / len(imgs) > 0.5:
            r.add(5, "a des images sans description, invisibles pour Google")

    if "application/ld+json" not in low and "itemtype=" not in low:
        r.add(5, "ne fournit pas ses infos (horaires, adresse) à Google sous forme structurée")
    if not _meta(low, "og:title") and not _meta(low, "og:image"):
        r.add(3, "s'affiche mal quand on le partage sur Facebook ou WhatsApp")
    if "<html" in low and not re.search(r"<html[^>]+lang=", low):
        r.add(2, "ne déclare pas sa langue")
    if "noindex" in _meta(low, "robots"):
        r.add(20, "est bloqué pour Google (noindex)")

    if pagespeed and (seo := pagespeed.get("seo")) is not None:
        r.data["lighthouse_seo"] = seo
        if seo < 70:
            r.add(10, f"a un référencement faible (score Google SEO {seo}/100)")
    return r
