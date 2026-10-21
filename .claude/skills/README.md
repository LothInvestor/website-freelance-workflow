# Claude Code skills

Two families, named `<famille>-<rôle>` in French:

- `prospection-*` — find and contact businesses (written for this project).
- `site-*` — the website creation team (third-party skills, vendored unchanged except for their
  `name:` field and references to each other's new names).

| Skill | Rôle | Origine | Nom d'origine | Licence |
|---|---|---|---|---|
| `prospection-leads` | Recherche, audit, revue visuelle des sites | Ce projet | `leads` | — |
| `prospection-envoi` | Relecture des accroches, envoi après confirmation | Ce projet | `prospecter` | — |
| `prospection-maquette` | Chef d'orchestre des `site-*` : maquette d'une page pour un lead | Ce projet | — | — |
| `site-contenu` | Capturer le style et le contenu d'un site existant (Bright Data Web Unlocker) | Bright Data plugin | `design-mirror` | MIT — `_licenses/brightdata-MIT.txt` |
| `site-identite` | Identité de marque, positionnement | ECC (affaan-m) | `brand-discovery` | MIT — `_licenses/ecc-MIT.txt` |
| `site-ton` | Ton et style d'écriture | ECC | `brand-voice` | MIT — `_licenses/ecc-MIT.txt` |
| `site-direction-artistique` | Direction visuelle | ECC | `frontend-design-direction` | MIT — `_licenses/ecc-MIT.txt` |
| `site-structure` | Choix et structure des pages | VectorLab UX skills | `page-patterns` | MIT — `_licenses/vectorlab-MIT.txt` |
| `site-typographie` | Échelle et choix typographiques | VectorLab | `typography` | MIT — `_licenses/vectorlab-MIT.txt` |
| `site-couleurs` | Palette et élévation | VectorLab | `colour-palette` | MIT — `_licenses/vectorlab-MIT.txt` |
| `site-anti-generique` | Éviter le look « généré par IA » | VectorLab | `anti-slop` | MIT — `_licenses/vectorlab-MIT.txt` |
| `site-responsive` | Mobile / desktop | VectorLab | `viewports` | MIT — `_licenses/vectorlab-MIT.txt` |
| `site-seo` | Référencement | ECC | `seo` | MIT — `_licenses/ecc-MIT.txt` |
| `site-accessibilite` | Accessibilité (WCAG) | ECC | `accessibility` | MIT — `_licenses/ecc-MIT.txt` |

Notes:

- Some `site-*` skills mention skills that are not vendored here (`surfaces`, `spacing`, `forms`,
  `seo-specialist`, `frontend-patterns`, `market-research`, `competitive-platform-analysis`). They come
  from the same upstream plugins (VectorLab UX skills, ECC); install those plugins if you want them.
- `site-contenu` needs `BRIGHTDATA_API_KEY` and `BRIGHTDATA_UNLOCKER_ZONE`. Its scripts call the
  Bright Data API with `curl -k` (upstream code, TLS verification disabled).
- To update a vendored skill, copy the new upstream version over it and re-apply the `name:` field.
