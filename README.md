# Prospect Pilot

> Find local businesses that need a website, then reach them by email or WhatsApp.

## How it works

1. **Find** — `lead_finder.py` pulls places from Google Maps through Bright Data (e.g. "boulangerie Lyon").
2. **Qualify** — each place gets a website status and a score:

   | Status | Meaning | Score |
   |---|---|---|
   | `none` | no website on Google Maps | 100 |
   | `social_only` | only Facebook / Instagram / Linktree | 90 |
   | `dead` | website doesn't load | 85 |
   | `free_builder` | Wix free, Jimdo, business.site… | 70 |
   | `audited` | real site, scored by the audit team below | 100 − quality |

   Bonuses: number of reviews (active business), mobile number, email found.
3. **Reach out** — `outreach.py` sends personalised emails over SMTP (throttled) and builds a
   `whatsapp.html` page of pre-filled `wa.me` links you click to send from your own WhatsApp.

Everything is plain Python 3.10+ standard library. Only the optional Claude design review needs `pip install anthropic`.

## Website audit team

`site_audit/` is a team of agents that each inspect one side of an existing website, then a judge
merges their reports:

| Agent | Looks at | Needs |
|---|---|---|
| **freshness** | copyright year, most recent year in the text, `Last-Modified`, CMS/builder version (FrontPage, old WordPress, Joomla 1.x…), jQuery < 3, Bootstrap 2/3, Flash, frames, `<font>`, table layouts | nothing |
| **technical** | HTTPS, expired certificate, mixed content, mobile viewport, response time, compression, JS/CSS count, image formats, lazy-loading, Lighthouse mobile performance | nothing (Lighthouse with `--deep`) |
| **seo** | title, meta description, H1, image alts, structured data, Open Graph, `lang`, `noindex`, Lighthouse SEO | nothing (Lighthouse with `--deep`) |
| **visual** | Claude (`claude-opus-5-5`) looks at the mobile screenshot: dated design, typography, layout, trust — and writes the pitch | `--visual`, `PAGESPEED_API_KEY`, `anthropic` + API key |
| **judge** | weighted score (freshness 30 %, visual 30 %, technical 25 %, SEO 15 %), capped by deal-breakers (no mobile, copyright 5+ years old, no HTTPS, Flash…), verdict `refonte urgente` / `à moderniser` / `correct`, top issues, pitch | — |

Every issue is written as a French clause that follows "le site de X …", so the judge's pitch drops
straight into your message's `{problem}` placeholder:

```
python audit.py https://www.spacejam.com/1996/ --name "Space Jam"

  Qualité 35/100 → REFONTE URGENTE  (besoin 65/100)
  · freshness   50/100
      - affiche encore un copyright de 1996
      - est mis en page avec des tableaux, comme dans les années 2000
  · technical   62/100
      - n'est pas adapté aux téléphones
  ...
  Accroche : « le site de Space Jam affiche encore un copyright de 1996 et n'est pas adapté aux téléphones »
```

Only the visual agent catches sites that are technically fine but look terrible. Without `--visual`,
those score as "correct".

Costs: the basic audit is free and takes ~1–3 s per site. `--deep` adds ~30 s per site (Google's
free quota is 25k requests/day with a key). `--visual` adds one Claude call per site with an image —
use it on leads that already passed the basic filter.

## Using it with Claude Code (recommended)

The project ships three `prospection-*` Claude Code skills that split the work 50/50: the scripts do the repetitive part
(free, fast), Claude only steps in where judgment matters.

| Command | Scripts do | Claude does |
|---|---|---|
| `/prospection-leads boulangerie Lyon` | Google Maps search, basic audit, scoring, dedup | Opens the sites that passed the technical checks in its browser (one small screenshot each), promotes the ones that *look* dated with a specific pitch |
| `/prospection-envoi 20` | Renders messages, sends emails over SMTP, logs every send, builds `whatsapp.html` | Proofreads the pitches, shows you a preview, **sends nothing until you say yes** |
| `/prospection-maquette Le Pain des Jacobins` | `review.py show` fetches the lead | Runs the `site-*` team step by step (brief, structure, type, colour, build, quality checks) and checks the page at 375 and 1280 px. Writes `maquettes/<slug>/` (git-ignored), using only real facts — the rest is marked « à confirmer » |

Sites that score "correct" in the basic audit go to `review.csv` instead of being dropped. `review.py`
prints them one line each, so the review stays cheap:

```bash
python review.py list                         # sites waiting for a visual check
python review.py promote <id> --pitch "..."   # looks dated → into leads.csv
python review.py dismiss <id> ...             # looks fine → never queued again
python review.py pitches                      # leads not contacted yet + their pitch
python review.py set-pitch <id> "..."         # rewrite a pitch
python review.py show <id|nom>                # one lead's details
```

You can do the review yourself with the same commands. The scripts work without Claude.

## Setup

```bash
cp .env.example .env   # then fill it in
```

**Bright Data** (only needed for `--query`): install the `bdata` CLI, run `bdata login`, then find the Google Maps scraper and its discover method:

```bash
bdata pipelines search "google maps"
bdata pipelines info <dataset_id>
bdata pipelines info <dataset_id> <discover_method>
```

Put the dataset id, method name and keyword field name in `.env`
(`BRIGHTDATA_DATASET_ID`, `BRIGHTDATA_METHOD`, `BRIGHTDATA_QUERY_FIELD`).

**SMTP**: Gmail → `smtp.gmail.com:465` with an [App Password](https://myaccount.google.com/apppasswords); OVH → `ssl0.ovh.net:465`.
Use a dedicated sending address/domain, not your main one.

## Usage

```bash
# 1. Find leads (each Google Maps record is billed — start small)
python lead_finder.py --query "boulangerie Lyon" --limit 20 --check-sites
python lead_finder.py --from-file gmaps.json --check-sites   # or reuse an export
python lead_finder.py --from-file gmaps.json --check-sites --visual   # + Lighthouse + Claude design review

# Audit a single site by hand
python audit.py https://site-du-client.fr --name "Boulangerie X" [--deep] [--visual] [--json]

# 2. Preview messages (dry run, nothing is sent)
python outreach.py

# 3. Go live
python outreach.py --channel email --send --max 20
python outreach.py --channel whatsapp --send   # then open whatsapp.html
```

Re-running is safe: leads are deduplicated by id in `leads.csv`, and every contact is logged in
`sent_log.csv` so nobody gets the same message twice. Put any email or phone (`33612345678`)
that replied STOP in `optout.txt`.

Edit the messages in `templates/email.txt` and `templates/whatsapp.txt`. Placeholders:
`{name} {category} {city} {problem} {website} {sender_name} {sender_site} {sender_phone}`.

## Files

```
prospect-pilot/
├── lead_finder.py      # Bright Data → scored leads.csv
├── audit.py            # audit one website from the command line
├── review.py           # review queue + pitch helpers (used by the skills)
├── .claude/skills/     # prospection-* and site-* skills (see .claude/skills/README.md)
├── outreach.py         # leads.csv → SMTP emails + whatsapp.html
├── common.py           # .env, phone normalisation, CSV helpers
├── site_audit/         # audit team: fetch, freshness, technical, seo, pagespeed, visual, judge
├── templates/
│   ├── email.txt
│   └── whatsapp.txt
└── .env.example
```

## Staying legal (France / EU)

- B2B cold email to a business's **professional** address is allowed (CNIL), provided you identify
  yourself, the message relates to their activity, and there is an easy opt-out (already in the template).
  Honour every STOP via `optout.txt`.
- For sole traders (artisans, auto-entrepreneurs) the address is often personal. Keep volumes low and messages relevant.
- WhatsApp: automated cold messages break Meta's terms and get numbers banned. That's why this tool only
  pre-fills messages and you send each one by hand.
- Keep email volume modest (≈20–50/day, delay between sends) to protect your domain's reputation.

## Next steps

- Publish mockups (e.g. Netlify) and link them in the message
- Follow-up email after N days without a reply
- Track replies (IMAP) and update lead status
