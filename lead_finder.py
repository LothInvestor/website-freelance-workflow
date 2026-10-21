"""
Lead finder — local businesses with no website (or a weak one) from Google Maps via Bright Data.

Usage:
  python lead_finder.py --from-file gmaps.json            # parse an existing Bright Data export
  python lead_finder.py --query "plombier Lyon" --limit 20 # run the Bright Data pipeline via `bdata`
Options: --check-sites (agent team audits existing websites + grabs emails), --deep, --visual,
         --min-score, --out leads.csv
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from common import (LEAD_FIELDS, REVIEW_CSV, REVIEW_FIELDS, is_mobile, load_env, normalize_phone,
                    read_csv, write_csv)
from site_audit import audit_site

SOCIAL_DOMAINS = ("facebook.com", "instagram.com", "linktr.ee", "tiktok.com", "linkedin.com")
FREE_BUILDERS = ("wixsite.com", "jimdofree.com", "jimdo.com", "site123.me", "webnode.",
                 "e-monsite.com", "business.site", "godaddysites.com", "weebly.com",
                 "blogspot.", "wordpress.com", "pagesjaunes.fr")

# Higher = hotter lead for a website-building offer. Audited sites use the audit's "need" score.
STATUS_SCORE = {
    "none": 100, "social_only": 90, "dead": 85, "free_builder": 70, "unchecked": 40,
}


def run_bdata(query: str, limit: int) -> list[dict]:
    """Run the Google Maps discover pipeline. IDs come from env (see README: `bdata pipelines info`)."""
    dataset = os.getenv("BRIGHTDATA_DATASET_ID")
    method = os.getenv("BRIGHTDATA_METHOD")
    field = os.getenv("BRIGHTDATA_QUERY_FIELD", "keyword")
    if not dataset or not method:
        raise SystemExit(
            "Set BRIGHTDATA_DATASET_ID and BRIGHTDATA_METHOD in .env "
            "(find them with: bdata pipelines search \"google maps\")."
        )
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "gmaps.json")
        cmd = ["bdata", "pipelines", "run", dataset, method, f"--{field}", query,
               "--limit-per-input", str(limit), "--format", "json", "--timeout", "1800", "-o", out]
        print("  $", " ".join(cmd))
        subprocess.run(cmd, check=True)
        return load_records(out)


def load_records(path: str) -> list[dict]:
    """Accept a JSON array, a single object, or NDJSON."""
    text = open(path, encoding="utf-8").read().strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        records = data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
    good = [r for r in records if isinstance(r, dict) and "error" not in r]
    if len(good) < len(records):
        print(f"  warning: skipped {len(records) - len(good)} record(s) with errors")
    return good


def _pick(rec: dict, *keys) -> str:
    for k in keys:
        v = rec.get(k)
        if isinstance(v, list):
            v = v[0] if v else ""
        if isinstance(v, dict):
            v = v.get("name") or v.get("title") or ""
        if v not in (None, ""):
            return str(v).strip()
    return ""


def _city(address: str) -> str:
    parts = [p.strip() for p in address.split(",") if p.strip()]
    for part in reversed(parts):
        m = re.match(r"^\d{4,5}\s+(.+)$", part)
        if m:
            return m.group(1)
    return parts[-2] if len(parts) >= 2 else ""


def to_lead(rec: dict, query: str, default_cc: str) -> dict:
    name = _pick(rec, "name", "title", "place_name")
    address = _pick(rec, "address", "full_address")
    phone = _pick(rec, "phone_number", "phone", "international_phone_number")
    e164 = normalize_phone(phone, default_cc)
    lead_id = _pick(rec, "place_id", "cid", "fid") or hashlib.sha1(
        f"{name}|{address}".encode()).hexdigest()[:16]
    return {
        "id": lead_id,
        "name": name,
        "category": _pick(rec, "category", "main_category", "categories"),
        "address": address,
        "city": _city(address),
        "phone": phone,
        "phone_e164": e164,
        "is_mobile": "1" if e164 and is_mobile(e164) else "0",
        "email": _pick(rec, "email", "emails"),
        "website": _pick(rec, "open_website", "website", "site"),
        "rating": _pick(rec, "rating"),
        "reviews": _pick(rec, "reviews_count", "review_count"),
        "maps_url": _pick(rec, "url", "place_url", "google_maps_url"),
        "query": query,
    }


def classify_website(url: str) -> str:
    """Static classification, no network."""
    if not url:
        return "none"
    host = urlparse(url if "://" in url else "http://" + url).netloc.lower()
    if any(d in host for d in SOCIAL_DOMAINS):
        return "social_only"
    if any(d in host for d in FREE_BUILDERS):
        return "free_builder"
    return "unchecked"


def apply_audit(lead: dict, deep: bool, use_visual: bool) -> None:
    """Run the site_audit agent team on the lead's website and store the verdict."""
    res = audit_site(lead["website"], lead["name"], deep=deep, use_visual=use_visual)
    lead["website_status"] = "audited" if res["reachable"] else "dead"
    lead["quality"] = res["quality"]
    lead["verdict"] = res["verdict"]
    lead["issues"] = " | ".join(res["issues"])
    lead["pitch"] = res["pitch"]
    lead["email"] = lead["email"] or res["email"]


def score(lead: dict) -> int:
    if lead["website_status"] == "audited":
        s = 100 - int(lead["quality"])
    else:
        s = STATUS_SCORE.get(lead["website_status"], 0)
    if s <= 0:
        return 0
    try:
        s += min(int(float(lead["reviews"] or 0)), 100) // 10  # active business bonus
    except ValueError:
        pass
    if lead["is_mobile"] == "1":
        s += 5
    if lead["email"]:
        s += 5
    return s


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Find businesses that need a website")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-file", help="Bright Data Google Maps export (JSON or NDJSON)")
    src.add_argument("--query", help='Search, e.g. "boulangerie Lyon" (runs bdata)')
    parser.add_argument("--limit", type=int, default=20, help="Max places per query (billed per record)")
    parser.add_argument("--check-sites", action="store_true", help="Audit existing websites with the agent team")
    parser.add_argument("--deep", action="store_true", help="Audit adds Google PageSpeed (~30 s/site)")
    parser.add_argument("--visual", action="store_true", help="Audit adds Claude design review (implies --deep)")
    parser.add_argument("--min-score", type=int, default=50)
    parser.add_argument("--out", default="leads.csv")
    parser.add_argument("--country-code", default=os.getenv("DEFAULT_COUNTRY_CODE", "33"))
    args = parser.parse_args()

    print("[1/3] Loading places...")
    records = load_records(args.from_file) if args.from_file else run_bdata(args.query, args.limit)
    query = args.query or os.path.basename(args.from_file)
    leads = [to_lead(r, query, args.country_code) for r in records]
    leads = [l for l in leads if l["name"]]
    print(f"  {len(leads)} places")

    print("[2/3] Rating websites...")
    for lead in leads:
        lead["website_status"] = classify_website(lead["website"])
    to_audit = [l for l in leads if l["website_status"] == "unchecked"] if args.check_sites else []
    if to_audit:
        deep = args.deep or args.visual
        with ThreadPoolExecutor(max_workers=4) as pool:
            for lead, _ in zip(to_audit, pool.map(lambda l: apply_audit(l, deep, args.visual), to_audit)):
                print(f"  {lead['name'][:40]:40} {lead.get('quality', '-'):>3}/100  {lead.get('verdict', '')}")
    for lead in leads:
        lead["score"] = score(lead)

    print("[3/3] Merging into", args.out)
    existing = {l["id"]: l for l in read_csv(args.out)}
    queue = read_csv(REVIEW_CSV)
    known = set(existing) | {l["id"] for l in queue}
    new = [l for l in leads if l["score"] >= args.min_score and l["id"] not in known]
    merged = list(existing.values()) + new
    merged.sort(key=lambda l: int(l["score"]), reverse=True)
    write_csv(args.out, merged, LEAD_FIELDS)
    print(f"  +{len(new)} new leads (score >= {args.min_score}), {len(merged)} total")

    # Sites that pass the technical checks can still look dated: queue them for a visual review
    # (by Claude via the /prospection-leads skill, or by you — see review.py).
    to_review = [dict(l, review="pending") for l in leads
                 if l["website_status"] == "audited" and l["score"] < args.min_score and l["id"] not in known]
    if to_review:
        write_csv(REVIEW_CSV, queue + to_review, REVIEW_FIELDS)
        print(f"  +{len(to_review)} sites to review visually → python review.py list")


if __name__ == "__main__":
    main()
