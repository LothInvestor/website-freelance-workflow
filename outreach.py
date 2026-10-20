"""
Outreach — personalised email (SMTP, auto-sent) and WhatsApp (pre-filled wa.me links) for leads.csv.

Usage:
  python outreach.py                        # dry run: preview messages, send nothing
  python outreach.py --channel email --send --max 20
  python outreach.py --channel whatsapp --send   # writes whatsapp.html with click-to-send links
"""

import argparse
import html
import os
import smtplib
import ssl
import time
from datetime import datetime
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from urllib.parse import quote

from common import load_env, read_csv, write_csv

LOG_FIELDS = ["id", "channel", "to", "sent_at"]

# Why we are reaching out, per website_status from lead_finder.py.
PROBLEM = {
    "none": "je n'ai pas trouvé de site internet pour {name}",
    "social_only": "{name} n'est présent que sur les réseaux sociaux, sans vrai site",
    "dead": "le site de {name} ne semble plus accessible",
    "free_builder": "le site de {name} est hébergé sur une plateforme gratuite, ce qui nuit à sa visibilité",
    "audited": "le site de {name} mériterait d'être modernisé",
}


def render(template: str, lead: dict) -> str:
    values = {k: (v or "") for k, v in lead.items()}
    # The audit team's pitch is specific to the site; fall back to the generic sentence per status.
    values["problem"] = lead.get("pitch") or PROBLEM.get(lead.get("website_status", ""), "").format(name=lead["name"])
    values["sender_name"] = os.getenv("SENDER_NAME", "")
    values["sender_site"] = os.getenv("SENDER_SITE", "")
    values["sender_phone"] = os.getenv("SENDER_PHONE", "")
    values["city"] = values.get("city") or "votre ville"
    return template.format(**values).strip()


def load_template(name: str) -> tuple[str, str]:
    """Returns (subject, body). First line 'Subject: ...' is optional."""
    text = (Path("templates") / name).read_text(encoding="utf-8")
    first, _, rest = text.partition("\n")
    if first.lower().startswith("subject:"):
        return first.split(":", 1)[1].strip(), rest.lstrip("\n")
    return "", text


def load_optout() -> set[str]:
    p = Path("optout.txt")
    if not p.exists():
        return set()
    return {line.strip().lower() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()}


def smtp_connect() -> smtplib.SMTP:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "465"))
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(host, port)
        server.starttls(context=ssl.create_default_context())
    server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
    return server


def build_email(lead: dict, subject: str, body: str) -> EmailMessage:
    from_email = os.getenv("FROM_EMAIL") or os.getenv("SMTP_USER", "you@example.com")
    msg = EmailMessage()
    msg["From"] = f'{os.getenv("SENDER_NAME", "")} <{from_email}>'
    msg["To"] = lead["email"]
    msg["Subject"] = render(subject, lead)
    msg["Message-ID"] = make_msgid()
    msg["List-Unsubscribe"] = f"<mailto:{from_email}?subject=STOP>"
    msg.set_content(render(body, lead))
    return msg


def whatsapp_page(rows: list[tuple[dict, str]]) -> str:
    items = "\n".join(
        f'<li><a href="https://wa.me/{l["phone_e164"]}?text={quote(text)}" target="_blank">'
        f'{html.escape(l["name"])}</a> <small>{html.escape(l["city"])} · {html.escape(l["phone"])} '
        f'· {html.escape(l["website_status"])}</small></li>'
        for l, text in rows
    )
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>WhatsApp leads</title>
<style>body{{font-family:system-ui;max-width:640px;margin:2rem auto;padding:0 16px}}
li{{margin:.6rem 0}}a{{font-weight:600}}a:visited{{color:#888;text-decoration:line-through}}</style>
</head><body><h1>{len(rows)} leads WhatsApp</h1>
<p>Clique sur un nom : WhatsApp s'ouvre avec le message pré-rempli, relis-le et envoie.</p>
<ol>{items}</ol></body></html>"""


def main():
    load_env()
    parser = argparse.ArgumentParser(description="Send outreach to leads")
    parser.add_argument("--leads", default="leads.csv")
    parser.add_argument("--channel", choices=["email", "whatsapp", "both"], default="both")
    parser.add_argument("--send", action="store_true", help="Actually send / write links (default: dry run)")
    parser.add_argument("--max", type=int, default=20, help="Max messages per channel this run")
    parser.add_argument("--delay", type=float, default=float(os.getenv("EMAIL_DELAY_SECONDS", "45")),
                        help="Seconds between emails (protects your sender reputation)")
    parser.add_argument("--min-score", type=int, default=0)
    args = parser.parse_args()

    leads = [l for l in read_csv(args.leads) if int(l.get("score") or 0) >= args.min_score]
    log = read_csv("sent_log.csv")
    done = {(r["id"], r["channel"]) for r in log}
    optout = load_optout()

    def eligible(channel: str, key: str, mobile_only: bool = False) -> list[dict]:
        return [l for l in leads if l[key] and (l["id"], channel) not in done
                and l[key].lower() not in optout
                and (not mobile_only or l["is_mobile"] == "1")][: args.max]

    now = lambda: datetime.now().isoformat(timespec="seconds")

    if args.channel in ("email", "both"):
        subject, body = load_template("email.txt")
        targets = eligible("email", "email")
        print(f"\n[email] {len(targets)} to send")
        server = smtp_connect() if args.send and targets else None
        for i, lead in enumerate(targets):
            msg = build_email(lead, subject, body)
            if not server:
                print(f"\n--- To: {msg['To']}\nSubject: {msg['Subject']}\n\n{msg.get_content()}")
                continue
            server.send_message(msg)
            log.append({"id": lead["id"], "channel": "email", "to": lead["email"], "sent_at": now()})
            write_csv("sent_log.csv", log, LOG_FIELDS)  # persist after each send
            print(f"  sent {i + 1}/{len(targets)} → {lead['email']}")
            if i < len(targets) - 1:
                time.sleep(args.delay)
        if server:
            server.quit()

    if args.channel in ("whatsapp", "both"):
        _, body = load_template("whatsapp.txt")
        targets = eligible("whatsapp", "phone_e164", mobile_only=True)
        rows = [(l, render(body, l)) for l in targets]
        print(f"\n[whatsapp] {len(rows)} mobile leads")
        if not args.send:
            for lead, text in rows[:3]:
                print(f"\n--- {lead['name']} (+{lead['phone_e164']})\n{text}")
        else:
            Path("whatsapp.html").write_text(whatsapp_page(rows), encoding="utf-8")
            log += [{"id": l["id"], "channel": "whatsapp", "to": l["phone_e164"], "sent_at": now()}
                    for l, _ in rows]
            write_csv("sent_log.csv", log, LOG_FIELDS)
            print("  wrote whatsapp.html — open it and click each lead to send")

    if not args.send:
        print("\nDry run: nothing sent. Add --send to go live.")


if __name__ == "__main__":
    main()
