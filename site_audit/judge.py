"""Judge — merges the agents' reports into one verdict, the top issues and a pitch."""

from .report import Report

WEIGHTS = {"freshness": 0.30, "technical": 0.25, "seo": 0.15, "visual": 0.30}
CRITICAL = 25  # an issue this severe (no mobile, copyright 5+ years old, Flash…) caps the overall score
CAPS = {1: 55, 2: 35}  # 3+ critical issues → 25


def verdict(quality: int) -> str:
    if quality < 40:
        return "refonte urgente"
    if quality < 65:
        return "à moderniser"
    return "correct"


def run(reports: list[Report], business: str) -> dict:
    active = [r for r in reports if not r.skipped]
    total_w = sum(WEIGHTS[r.agent] for r in active)
    quality = round(sum(r.quality * WEIGHTS[r.agent] for r in active) / total_w) if total_w else 0

    # A weighted average hides deal-breakers: a 1996 site with good SEO is still a 1996 site.
    all_issues = sorted((i for r in active for i in r.issues), key=lambda i: -i[0])
    critical = sum(1 for p, _ in all_issues if p >= CRITICAL)
    if critical:
        quality = min(quality, CAPS.get(critical, 25))

    seen, issues = set(), []
    for _, clause in all_issues:
        if clause not in seen:
            seen.add(clause)
            issues.append(clause)

    visual = next((r for r in active if r.agent == "visual"), None)
    subject = f"le site de {business}" if business else "votre site"
    if visual and visual.data.get("pitch"):
        pitch = visual.data["pitch"]
        if not pitch.lower().startswith("le site"):
            pitch = f"{subject} {pitch}"
    elif issues:
        pitch = f"{subject} {issues[0]}"
        if len(issues) > 1:
            pitch += (", et " if "," in issues[0] else " et ") + issues[1]
    else:
        pitch = ""

    return {
        "quality": quality,
        "need": 100 - quality,
        "verdict": verdict(quality),
        "issues": issues[:6],
        "pitch": pitch,
        "agents": {
            r.agent: {"quality": r.quality if not r.skipped else None, "skipped": r.skipped,
                      "issues": [c for _, c in r.issues], "data": r.data}
            for r in reports
        },
    }
