"""
Website quality audit team.

  fetch      → downloads the homepage once
  freshness  → copyright year, last update, dated CMS / libraries / markup
  technical  → HTTPS, certificate, mobile, speed, weight (+ Lighthouse if deep)
  seo        → title, description, H1, structured data, sharing previews
  visual     → Claude judges the screenshot's design (deep + visual only)
  judge      → weighted quality score, verdict, top issues, outreach pitch
"""

from concurrent.futures import ThreadPoolExecutor

from . import freshness, judge, pagespeed, seo, technical, visual
from .fetch import fetch, find_email


def audit_site(url: str, business: str = "", deep: bool = False, use_visual: bool = False) -> dict:
    """deep: also run Google PageSpeed (slow, ~30 s). use_visual: Claude design review (needs deep)."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        page_f = pool.submit(fetch, url)
        psi_f = pool.submit(pagespeed.run, url) if deep else None
        page = page_f.result()
        psi = psi_f.result() if psi_f else {}

    if not page.ok:
        return {"url": url, "reachable": False, "quality": 0, "need": 100,
                "verdict": "site inaccessible", "issues": ["ne s'affiche plus"],
                "pitch": f"le site de {business} ne s'affiche plus" if business else "",
                "email": "", "error": page.error or f"HTTP {page.status}", "agents": {}}

    reports = [freshness.run(page), technical.run(page, psi), seo.run(page, psi)]
    if use_visual:
        findings = {r.agent: [c for _, c in r.issues] for r in reports}
        reports.append(visual.run(psi.get("screenshot", ""), business, findings, psi.get("error", "")))

    result = judge.run(reports, business)
    result.update({"url": page.final_url or url, "reachable": True, "email": find_email(page.html),
                   "pagespeed": {k: v for k, v in psi.items() if k != "screenshot"}})
    return result
