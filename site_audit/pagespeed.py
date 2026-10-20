"""Google PageSpeed Insights (Lighthouse, mobile): speed/SEO scores + a homepage screenshot."""

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlencode

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def run(url: str, timeout: float = 90) -> dict:
    """Returns {performance, seo, lcp_seconds, screenshot}, or {"error": ...} if PSI is unavailable."""
    params = [("url", url), ("strategy", "mobile"), ("category", "performance"), ("category", "seo")]
    key = os.getenv("PAGESPEED_API_KEY")
    if key:
        params.append(("key", key))
    try:
        with urllib.request.urlopen(f"{API}?{urlencode(params)}", timeout=timeout) as resp:
            lh = json.load(resp)["lighthouseResult"]
    except urllib.error.HTTPError as e:
        hint = "" if key else " — set PAGESPEED_API_KEY (keyless quota is shared and usually exhausted)"
        return {"error": f"PageSpeed HTTP {e.code}{hint}"}
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, OSError) as e:
        return {"error": f"PageSpeed unavailable: {e}"}

    def score(cat: str):
        s = lh.get("categories", {}).get(cat, {}).get("score")
        return round(s * 100) if s is not None else None

    audits = lh.get("audits", {})
    lcp = audits.get("largest-contentful-paint", {}).get("numericValue")
    shot = audits.get("final-screenshot", {}).get("details", {}).get("data", "")
    return {
        "performance": score("performance"),
        "seo": score("seo"),
        "lcp_seconds": round(lcp / 1000, 1) if lcp else None,
        "screenshot": shot,  # "data:image/jpeg;base64,..."
    }
