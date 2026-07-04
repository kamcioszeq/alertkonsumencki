"""Shared, platform-agnostic configuration.

Importing this module loads the .env file, so it must be imported before any
platform config module (e.g. telegram/config.py) reads os.getenv.
"""
import os
from dotenv import load_dotenv

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# ─── Crawler GIS (mini-serwis sprawdzający ostrzeżenia) ──────
# Zmieniaj te wartości tutaj (root) lub przez zmienne środowiskowe / deploy.sh.
GIS_LISTING_URL = os.getenv("GIS_LISTING_URL", "https://www.gov.pl/web/gis/ostrzezenia")
CRAWLER_INTERVAL = int(os.getenv("CRAWLER_INTERVAL", "600"))      # sekundy między sprawdzeniami
CRAWLER_OUTPUT_DIR = os.getenv("CRAWLER_OUTPUT_DIR", "gis_alerts")  # tu lądują pliki .txt
CRAWLER_STATE_FILE = os.getenv("CRAWLER_STATE_FILE", "crawler_state.json")  # ostatnie widziane ostrzeżenie

# ─── Handoff crawler → bot Telegram ─────────────────────────
# Crawler zapisuje nowe ostrzeżenia do QUEUE_DIR, bot je stamtąd odbiera i pyta o wygenerowanie.
QUEUE_DIR = os.getenv("QUEUE_DIR", "queue")
QUEUE_POLL_INTERVAL = int(os.getenv("QUEUE_POLL_INTERVAL", "15"))   # jak często bot sprawdza kolejkę (s)
# Statyczny obrazek dołączany do ostrzeżeń i publikowanych postów.
ALERT_IMAGE = os.getenv("ALERT_IMAGE", "assets/alert.png")
