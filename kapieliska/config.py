"""Konfiguracja modułu kąpielisk (env + domyślne)."""
import os
from pathlib import Path

BASE_URL = os.getenv("KAPIELISKA_BASE_URL", "https://sk.gis.gov.pl")
LIST_URL = f"{BASE_URL}/kapieliska/lista"
AJAX_LIST_TMPL = f"{BASE_URL}/ajax/lista/{{page}}/"
DETAIL_TMPL = f"{BASE_URL}/kapielisko/{{id}}"

DATA_DIR = Path(os.getenv("KAPIELISKA_DATA_DIR", "kapieliska/data"))
LIST_CSV = DATA_DIR / "kapieliska_list.csv"
OCENY_CSV = DATA_DIR / "oceny.csv"
HISTORY_CSV = DATA_DIR / "oceny_history.csv"
UPDATES_CSV = DATA_DIR / "updates.csv"
CURSOR_JSON = DATA_DIR / "cursor.json"
ACTIVE_ALERTS_JSON = DATA_DIR / "active_alerts.json"

# Round-robin: ~100 na cykl, ~36 s odstępu (okno ~1 h)
BATCH_SIZE = int(os.getenv("KAPIELISKA_BATCH_SIZE", "100"))
POLL_INTERVAL_SEC = float(os.getenv("KAPIELISKA_POLL_INTERVAL_SEC", "36"))
# Ile cykli dziennie (domyślnie 3 ≈ pełne pokrycie ~1×/dzień przy 718 pozycjach)
CYCLES_PER_DAY = int(os.getenv("KAPIELISKA_CYCLES_PER_DAY", "3"))

# Progi GIS (jtk/100 ml)
ECOLI_LIMIT = int(os.getenv("KAPIELISKA_ECOLI_LIMIT", "1000"))
ENTEROKOKI_LIMIT = int(os.getenv("KAPIELISKA_ENTEROKOKI_LIMIT", "400"))

# Jak długo trzymać aktywny alert (pod update statusu / komentarza FB)
ACTIVE_ALERT_DAYS = int(os.getenv("KAPIELISKA_ACTIVE_ALERT_DAYS", "30"))

# Sezon (miesiące 6–9)
SEASON_MONTHS = tuple(
    int(x) for x in os.getenv("KAPIELISKA_SEASON_MONTHS", "6,7,8,9").split(",")
)

PLAYWRIGHT_BROWSERS_PATH = os.getenv(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(Path(__file__).resolve().parent.parent / ".pw-browsers"),
)
