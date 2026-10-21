---
name: prospection-envoi
description: Relit les accroches des leads, montre un aperçu des messages, puis envoie les emails (SMTP) et prépare les liens WhatsApp après confirmation explicite de l'utilisateur. Utiliser quand l'utilisateur veut contacter ses prospects, par ex. "/prospection-envoi 20".
argument-hint: "[nombre max, défaut 20] [email|whatsapp|both]"
---

# /prospection-envoi — relire puis envoyer

Tout se lance depuis la racine du projet. Réponds à l'utilisateur en français.
**Rien n'est envoyé sans un « oui » explicite de l'utilisateur dans le chat, pour cet envoi-là.**

## 1. Relire les accroches

`python review.py pitches --limit <n>` donne une ligne par lead : `id | nom | score | canaux | accroche`.

Corrige uniquement les accroches maladroites (grammaire, jargon technique, ton agressif, phrase trop longue)
avec `python review.py set-pitch <id> "<phrase>"`. La phrase suit « j'ai remarqué que … » et commence
par « le site de <nom> ». N'invente aucun fait : reformule seulement ce qui est déjà dans l'accroche.
Les « phrase générique » sont normales (commerces sans site) : laisse-les.

## 2. Aperçu

- `python outreach.py --channel email --max 1` : montre l'email complet du premier lead.
- `python outreach.py --channel whatsapp --max 1` : montre un message WhatsApp.
- Donne les chiffres : N emails prêts, M WhatsApp prêts (mobiles uniquement).

Si `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` manquent dans `.env`, dis-le : seul WhatsApp est possible.
Tu ne lis jamais `.env` à voix haute et ne demandes jamais le mot de passe dans le chat.

## 3. Confirmation puis envoi

Demande : « J'envoie N emails (un toutes les ~45 s) et je prépare M liens WhatsApp ? » et attends le oui.

- Emails : `python outreach.py --channel email --send --max <N>` **en arrière-plan** (45 s entre chaque
  envoi, donc plusieurs minutes). Le script journalise chaque envoi dans `sent_log.csv` : personne ne
  reçoit deux fois le même message.
- WhatsApp : `python outreach.py --channel whatsapp --send --max <M>` écrit `whatsapp.html`. Dis à
  l'utilisateur de l'ouvrir et de cliquer sur chaque nom : c'est lui qui envoie depuis son WhatsApp.
  Ne clique jamais toi-même sur ces liens.

## 4. Après

- Si quelqu'un répond STOP, ajoute son email ou son numéro (format `33612345678`) dans `optout.txt`.
- Rappelle de garder un volume raisonnable (20–50 emails par jour).
