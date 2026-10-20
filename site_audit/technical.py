"""Technical agent — security, mobile, speed and weight."""

import re

from .fetch import Page
from .report import Report


def run(page: Page, pagespeed: dict | None = None) -> Report:
    r = Report("technical")
    html, low = page.html, page.html.lower()

    # Security
    if not page.final_url.startswith("https://"):
        r.add(25, "n'est pas sécurisé (pas de HTTPS) : Chrome l'affiche « Non sécurisé »")
    elif page.cert_invalid:
        r.add(25, "a un certificat de sécurité expiré ou invalide, les visiteurs voient une alerte")
    elif re.search(r'(?:src|href)=["\']http://(?!localhost)', low):
        r.add(5, "charge des éléments non sécurisés (contenu mixte)")

    # Mobile
    viewport = re.search(r'<meta[^>]+name=["\']viewport["\']', low)
    r.data["viewport"] = bool(viewport)
    if not viewport:
        r.add(25, "n'est pas adapté aux téléphones")

    # Speed & weight (from our own request)
    r.data["html_seconds"] = round(page.elapsed, 2)
    r.data["html_kb"] = round(len(html.encode()) / 1024)
    if page.elapsed > 3:
        r.add(10, f"met {page.elapsed:.1f} s rien qu'à répondre".replace(".", ","))
    if not page.compressed and len(html) > 30_000:
        r.add(5, "n'active pas la compression, ce qui le ralentit")
    scripts = len(re.findall(r"<script[^>]+src=", low))
    styles = len(re.findall(r'<link[^>]+rel=["\']stylesheet', low))
    r.data["scripts"], r.data["stylesheets"] = scripts, styles
    if scripts + styles > 40:
        r.add(5, f"charge {scripts + styles} fichiers JS/CSS, ce qui l'alourdit")

    imgs = re.findall(r"<img\b[^>]*>", low)
    r.data["images"] = len(imgs)
    if imgs:
        modern = sum(1 for i in imgs if ".webp" in i or ".avif" in i) + low.count('type="image/webp"')
        lazy = sum(1 for i in imgs if 'loading="lazy"' in i or "data-src" in i)
        if len(imgs) >= 8 and modern == 0:
            r.add(5, "n'utilise aucun format d'image optimisé (WebP/AVIF)")
        if len(imgs) >= 10 and lazy == 0:
            r.add(3, "charge toutes ses images d'un coup")

    # Google Lighthouse (mobile), when available — the most reliable speed signal.
    if pagespeed:
        perf = pagespeed.get("performance")
        r.data["lighthouse_performance"] = perf
        if lcp := pagespeed.get("lcp_seconds"):
            r.data["lcp_seconds"] = lcp
        if perf is not None:
            if perf < 30:
                r.add(25, f"est très lent sur mobile (score Google {perf}/100)")
            elif perf < 50:
                r.add(15, f"est lent sur mobile (score Google {perf}/100)")
            elif perf < 70:
                r.add(5, f"pourrait être plus rapide sur mobile (score Google {perf}/100)")
    return r
