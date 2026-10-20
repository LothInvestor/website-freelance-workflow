"""
Audit one or more websites with the agent team and print the verdict.

Usage:
  python audit.py https://boulangerie-exemple.fr
  python audit.py https://site.fr --name "Boulangerie Exemple" --deep --visual
  python audit.py https://site.fr --json
"""

import argparse
import json

from common import load_env
from site_audit import audit_site


def print_report(res: dict) -> None:
    print(f"\n{res['url']}")
    if not res["reachable"]:
        print(f"  INACCESSIBLE — {res.get('error', '')}")
        return
    print(f"  Qualité {res['quality']}/100 → {res['verdict'].upper()}  (besoin {res['need']}/100)")
    for name, agent in res["agents"].items():
        if agent["skipped"]:
            print(f"  · {name:<10} ignoré ({agent['skipped']})")
            continue
        print(f"  · {name:<10} {agent['quality']:>3}/100")
        for issue in agent["issues"]:
            print(f"      - {issue}")
    if err := res.get("pagespeed", {}).get("error"):
        print(f"  ! {err}")
    if res["email"]:
        print(f"  Email trouvé : {res['email']}")
    if res["pitch"]:
        print(f"  Accroche : « {res['pitch']} »")


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Website quality audit")
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--name", default="", help="Business name (used in the pitch)")
    parser.add_argument("--deep", action="store_true", help="Add Google PageSpeed (slow, ~30 s/site)")
    parser.add_argument("--visual", action="store_true", help="Add Claude design review (implies --deep)")
    parser.add_argument("--json", action="store_true", help="Print raw JSON")
    args = parser.parse_args()

    for url in args.urls:
        res = audit_site(url, args.name, deep=args.deep or args.visual, use_visual=args.visual)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print_report(res)


if __name__ == "__main__":
    main()
