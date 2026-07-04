# alertkonsumencki

Telegram bot for producing Polish consumer-safety alerts (GIS / product recalls). A reviewer
drops a link (or text) into an **internal chat**, the bot fetches the page, Claude drafts a
consumer alert, the reviewer tweaks the wording, and publishes it to a public **broadcast channel**.

## Quick start

```bash
python -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env        # then fill it in — see README_BOT_INTEGRATION.md
./venv/bin/python main.py
```

In the internal chat: send `/test` (seeds a sample alert) or paste a GIS/gov.pl URL → click
**🔍 Generuj post** → adjust → **Publikuj**.

## How it works

Drop link → 🔍 Generuj → Claude draft → ✅ OK / **Dostosuj** (Bardziej formalny · Mniej formalny ·
Techniczny · Sugestia) / Edytuj → **Publikuj** → broadcast channel. See
[README_WHY.md](README_WHY.md) for diagrams and rationale.

## Project layout

```
config.py            shared config (.env, Claude key/model)
main.py              entrypoint: build bot, register telegram, run
core/                shared, platform-agnostic
  claude.py          ask_claude()
  state.py           persistent pending_adoption / pending_posts
  article.py         URL parse + trafilatura fetch
telegram/            Telegram platform (self-contained)
  config.py client.py prompts.py format.py buttons.py publish.py
  ingest.py          on_direct_url, /new, /test, ingest_alert()
  url_handlers.py    url_read / url_ok / url_adjust
  handlers.py        rephrase / publish / reject / edit-reply
crawler/             GIS mini-service (runs separately from the bot)
  gis.py             parse the GIS ostrzeżenia listing
  service.py         interval loop: startup dump + poll for new warnings
  state.py           last-seen warning marker (no skips / no dupes)
```

Each future platform (e.g. `facebook/`) becomes its own sibling directory reusing `core/`.

## GIS crawler (mini-service) → Telegram handoff

A separate service polls the GIS warnings page on an interval and downloads details of new
warnings. Each new warning is (a) dumped to a `.txt` in `gis_alerts/` and (b) **handed off to
the bot** via a file queue (`queue/`). The bot then DMs you the alert image (`assets/alert.png`)
+ a summary and asks **"Wygenerować post?"** (🔍). Clicking it generates an editable draft (the
usual OK / Dostosuj / Skróć / Edytuj flow); publishing sends **image + text** to the broadcast
channel. On startup the crawler **always** pushes the latest warning straight to Telegram (a
visible proof-of-life), in addition to dumping it to `.txt`.

Config lives in root [config.py](config.py) (`GIS_LISTING_URL`, `CRAWLER_INTERVAL`,
`CRAWLER_OUTPUT_DIR`, `CRAWLER_STATE_FILE`, `QUEUE_DIR`, `QUEUE_POLL_INTERVAL`, `ALERT_IMAGE`),
overridable via env / `deploy.sh` (`CRAWLER_INTERVAL`). Replace `assets/alert.png` with your own
branded graphic.

Run it standalone (parallel to the bot):

```bash
./venv/bin/python -m crawler
```

Under podman it runs as its own container (`alertkonsumencki_crawler`) alongside the bot;
follow its logs with `./deploy.sh logs-crawler`.

## Setup & bot creation

See **[README_BOT_INTEGRATION.md](README_BOT_INTEGRATION.md)** for step-by-step BotFather /
`my.telegram.org` / channel-admin / `.env` instructions.

## Out of scope (for now)

Automatic GIS crawler (will call `ingest_alert()`), article images/media, X/Facebook cross-posting.
