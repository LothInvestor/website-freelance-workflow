"""Visual agent — Claude looks at the homepage screenshot and judges how dated the design is.

Also writes the outreach pitch, since it is the only agent that sees the whole picture.
Needs `pip install anthropic` and credentials (ANTHROPIC_API_KEY or `ant auth login`).
"""

import json

from .report import Report

MODEL = "claude-opus-5-5"
SEVERITY_PENALTY = {"high": 20, "medium": 10, "low": 5}

SYSTEM = """You are a senior web designer helping a freelance web developer prospect local \
businesses (shops, restaurants, tradespeople) whose website needs a redesign.

You receive a mobile screenshot of the homepage (above the fold) plus findings from automated \
checks. Judge the visual design the way a potential customer would in the first five seconds: \
does it look modern and trustworthy, or dated and neglected? Look at typography, layout, \
colours, image quality, spacing, visual hierarchy, how it fits a phone screen, and cues that \
date the design (skeuomorphic buttons, gradients/bevels from the 2000s, clip-art, tiny text, \
cramped layouts, stock template look).

Score fairly: a clean, simple site that works on mobile scores well even if it is not fancy. \
Only report issues you can actually see or that the findings support.

Write every text field in French. Each issue "clause" and the "pitch" must read naturally \
after "le site de <business>" — e.g. "a un design daté des années 2010, avec un texte trop petit \
sur mobile". The pitch is one courteous, concrete sentence (max 35 words) combining the two \
most convincing problems for the business owner, no technical jargon, no exaggeration."""

SCHEMA = {
    "type": "object",
    "properties": {
        "visual_quality": {"type": "integer", "description": "0 = very dated/broken, 100 = modern and polished"},
        "design_era": {"type": "string", "description": "Estimated period the design comes from, e.g. '2008-2012'"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "clause": {"type": "string"},
                },
                "required": ["severity", "clause"],
                "additionalProperties": False,
            },
        },
        "pitch": {"type": "string"},
    },
    "required": ["visual_quality", "design_era", "issues", "pitch"],
    "additionalProperties": False,
}


def run(screenshot: str, business: str, findings: dict, no_shot_reason: str = "") -> Report:
    r = Report("visual")
    try:
        import anthropic
    except ImportError:
        r.skipped = "anthropic not installed (pip install anthropic)"
        return r
    if not screenshot.startswith("data:image/"):
        r.skipped = f"no screenshot ({no_shot_reason or 'PageSpeed returned none'})"
        return r

    media_type, _, b64 = screenshot[5:].partition(";base64,")
    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            system=SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": f"Business: {business or 'unknown'}\n\n"
                                             f"Automated findings:\n{json.dumps(findings, ensure_ascii=False, indent=2)}"},
                ],
            }],
        )
    except anthropic.APIConnectionError as e:
        r.skipped = f"network error: {e}"
        return r
    except anthropic.APIStatusError as e:
        r.skipped = f"API error {e.status_code}: {e.message}"
        return r

    if response.stop_reason == "refusal":
        r.skipped = "model declined"
        return r
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        r.skipped = f"unparseable output (stop_reason={response.stop_reason})"
        return r

    r.quality_override = max(0, min(100, int(out["visual_quality"])))
    for issue in out["issues"][:4]:
        r.add(SEVERITY_PENALTY.get(issue["severity"], 5), issue["clause"])
    r.data = {"design_era": out["design_era"], "pitch": out["pitch"]}
    return r
