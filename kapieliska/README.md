# Kąpieliska crawler

Osobny crawler jakości wody z [Serwisu Kąpieliskowego GIS](https://sk.gis.gov.pl/kapieliska/lista).

## Wymagania

```bash
./venv/bin/pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH=./.pw-browsers ./venv/bin/playwright install chromium
```

## Komendy

```bash
export PLAYWRIGHT_BROWSERS_PATH=./.pw-browsers

# 1) Pełna lista (~700 linków) → kapieliska/data/kapieliska_list.csv
./venv/bin/python -m kapieliska bootstrap

# 2) WAŻNE: jednorazowy baseline ocen dla CAŁEJ listy (bez alertów)
#    ~708 × 2 s ≈ 25–40 min; wznawialne (pomija już zapisane)
./venv/bin/python -m kapieliska baseline
./venv/bin/python -m kapieliska baseline --limit 10   # test
./venv/bin/python -m kapieliska baseline --refresh    # od nowa wszystko

# 3) Cykle: tylko porównanie z baseline → alert przy zmianie/zagrożeniu
./venv/bin/python -m kapieliska once
./venv/bin/python -m kapieliska once --batch 5 --interval 2 --force --no-enqueue

# 4) Pętla sezonowa (czerwiec–wrzesień)
./venv/bin/python -m kapieliska loop

# 5) Status CSV / cursor / % baseline
./venv/bin/python -m kapieliska status
```

W Telegramie (internal chat): `/kapieliska` — max 5 ostatnich alertów zmian.

## Jak działa

1. Bootstrap: `GET /ajax/lista/{page}/` (sesja Playwright przez Incapsula).
2. Poller: odwiedza strony `/kapielisko/{id}`, czyta tabelę ocen wody.
3. CSV: `oceny.csv` (aktualna), `oceny_history.csv` (poprzednie), `updates.csv` (alerty).
4. Przy zmianie na niezdatną / przekroczeniu E. coli lub enterokoków → `queue/` jak GIS.

## Facebook — tylko zagrożenie

Post FB powstaje **wyłącznie** przy zagrożeniu (niezdatna / progi bakterii).
Prompt głównego posta (`FB_KAPIELISKA_SYSTEM_PROMPT`):

```
HOOK: 🌴 + ostrzeżenie dla plażowiczów
🌴 Ważna informacja dla plażowiczów + ocena / bakterie / data
📍 Lokalizacja (nazwa, adres, powiat, woj., akwen)
Zalecenie: nie wchodzić do wody
Źródło: GIS — Serwis Kąpieliskowy
```

Aktywny alert trzymany **30 dni** (`active_alerts.json`). Przy zmianie statusu → Telegram:
„Status się zmienił. Wrzucić update do komentarza FB?” (`✅ Update` / `⏭ Pomiń`).

## Env

| Zmienna | Domyślnie |
|---------|-----------|
| `KAPIELISKA_BATCH_SIZE` | 100 |
| `KAPIELISKA_POLL_INTERVAL_SEC` | 36 |
| `KAPIELISKA_CYCLES_PER_DAY` | 3 |
| `KAPIELISKA_ECOLI_LIMIT` | 1000 |
| `KAPIELISKA_ENTEROKOKI_LIMIT` | 400 |
| `KAPIELISKA_ACTIVE_ALERT_DAYS` | 30 |
| `KAPIELISKA_DATA_DIR` | `kapieliska/data` |
| `PLAYWRIGHT_BROWSERS_PATH` | `.pw-browsers` |
