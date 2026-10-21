"""
Compact helpers for the human/Claude review steps (used by the /prospection-leads, /prospection-envoi
and /prospection-maquette skills). Prints one short line per lead so a review costs few tokens.

  python review.py list                          # sites waiting for a visual check
  python review.py promote <id> --pitch "..."    # site looks dated → move it into leads.csv
  python review.py dismiss <id> [<id> ...]       # site looks fine → never queue it again
  python review.py pitches [--limit 30]          # leads not contacted yet, with their pitch
  python review.py set-pitch <id> "..."          # rewrite a lead's pitch
  python review.py show <id|nom>                 # one lead's details (for a mockup)
"""

import argparse

from common import LEAD_FIELDS, REVIEW_CSV, REVIEW_FIELDS, load_env, read_csv, slugify, write_csv
from lead_finder import score

LEADS_CSV = "leads.csv"


def cmd_list(_args) -> None:
    pending = [l for l in read_csv(REVIEW_CSV) if l["review"] == "pending"]
    for l in pending:
        print(f"{l['id']} | {l['name'][:35]} | {l['quality']}/100 | {l['website']}")
    print(f"({len(pending)} to review)")


def cmd_promote(args) -> None:
    queue = read_csv(REVIEW_CSV)
    lead = next((l for l in queue if l["id"] == args.id), None)
    if not lead:
        raise SystemExit(f"{args.id} not in {REVIEW_CSV}")
    lead["review"] = "promoted"
    promoted = {k: lead[k] for k in LEAD_FIELDS}
    promoted["quality"] = str(min(int(lead["quality"] or 100), args.quality))
    promoted["verdict"] = "à moderniser (design daté)"
    promoted["issues"] = " | ".join(filter(None, ["design daté (revue visuelle)", lead["issues"]]))
    promoted["pitch"] = args.pitch
    promoted["score"] = score(promoted)
    leads = [l for l in read_csv(LEADS_CSV) if l["id"] != args.id] + [promoted]
    leads.sort(key=lambda l: int(l["score"]), reverse=True)
    write_csv(LEADS_CSV, leads, LEAD_FIELDS)
    write_csv(REVIEW_CSV, queue, REVIEW_FIELDS)
    print(f"promoted {lead['name']} (score {promoted['score']})")


def cmd_dismiss(args) -> None:
    queue = read_csv(REVIEW_CSV)
    for l in queue:
        if l["id"] in args.ids:
            l["review"] = "dismissed"
    write_csv(REVIEW_CSV, queue, REVIEW_FIELDS)
    print(f"dismissed {len(args.ids)}")


def cmd_pitches(args) -> None:
    done = {(r["id"], r["channel"]) for r in read_csv("sent_log.csv")}
    shown = 0
    for l in read_csv(LEADS_CSV):
        email = l["email"] and (l["id"], "email") not in done
        wa = l["is_mobile"] == "1" and (l["id"], "whatsapp") not in done
        if not (email or wa):
            continue
        channels = "+".join(c for c, ok in (("email", email), ("wa", wa)) if ok)
        pitch = l.get("pitch") or f"(phrase générique: {l['website_status']})"
        print(f"{l['id']} | {l['name'][:30]} | {l['score']} | {channels} | {pitch}")
        shown += 1
        if shown >= args.limit:
            break
    print(f"({shown} shown)")


def cmd_set_pitch(args) -> None:
    leads = read_csv(LEADS_CSV)
    for l in leads:
        if l["id"] == args.id:
            l["pitch"] = args.pitch
            write_csv(LEADS_CSV, leads, LEAD_FIELDS)
            print(f"updated {l['name']}")
            return
    raise SystemExit(f"{args.id} not in {LEADS_CSV}")


def cmd_show(args) -> None:
    """One lead's non-empty fields, matched by id or by a piece of its name."""
    needle = args.lead.lower()
    matches = [l for l in read_csv(LEADS_CSV) if l["id"] == args.lead or needle in l["name"].lower()]
    if len(matches) != 1:
        for l in matches:
            print(f"{l['id']} | {l['name']}")
        raise SystemExit(f"{len(matches)} leads match {args.lead!r}: use the id")
    for k, v in matches[0].items():
        if v:
            print(f"{k}: {v}")
    print(f"slug: {slugify(matches[0]['name'])}  (mockup folder: maquettes/<slug>/)")


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Lead review helpers")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(func=cmd_list)
    p = sub.add_parser("promote")
    p.add_argument("id")
    p.add_argument("--pitch", required=True, help='Clause that follows "j\'ai remarqué que …"')
    p.add_argument("--quality", type=int, default=45, help="Overall quality after visual review (0-100)")
    p.set_defaults(func=cmd_promote)
    p = sub.add_parser("dismiss")
    p.add_argument("ids", nargs="+")
    p.set_defaults(func=cmd_dismiss)
    p = sub.add_parser("pitches")
    p.add_argument("--limit", type=int, default=30)
    p.set_defaults(func=cmd_pitches)
    p = sub.add_parser("set-pitch")
    p.add_argument("id")
    p.add_argument("pitch")
    p.set_defaults(func=cmd_set_pitch)
    p = sub.add_parser("show")
    p.add_argument("lead", help="Lead id or part of its name")
    p.set_defaults(func=cmd_show)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
