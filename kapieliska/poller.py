"""Parsowanie oceny wody ze strony szczegółów + round-robin poller."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Optional

from . import config
from .browser import browser_page, warm_session
from .detect import evaluate_change
from .store import (
    append_update,
    get_active_alert,
    load_cursor,
    load_list,
    load_oceny,
    purge_expired_alerts,
    register_active_alert,
    save_cursor,
    upsert_ocena,
)

log = logging.getLogger("kapieliska.poller")

_SEZON_RE = re.compile(
    r"Sezon kąpielowy[:\s]*(\d{2}/\d{2}/\d{4})\s*[-–]\s*(\d{2}/\d{2}/\d{4})",
    re.I,
)


def _parse_int(val: str) -> str:
    s = (val or "").strip().replace("\xa0", " ")
    m = re.search(r"\d+", s.replace(" ", ""))
    return m.group(0) if m else ""


def _split_ocena_przyczyna(raw: str) -> tuple[str, str]:
    """Rozdziel 'Woda nieprzydatna… Przyczyna: Zakwit sinic'."""
    text = (raw or "").strip()
    if not text:
        return "", ""
    m = re.search(r"(?is)przyczyna\s*:\s*(.+)$", text)
    if not m:
        return text, ""
    przyczyna = re.split(r"[\n\r]", m.group(1).strip())[0].strip()
    ocena = re.split(r"(?i)przyczyna\s*:", text, maxsplit=1)[0].strip(" \n\r-–|")
    return ocena, przyczyna


async def parse_detail(page, url: str) -> Optional[dict[str, str]]:
    """Wejdź na stronę kąpieliska i wyciągnij najnowszą ocenę wody + lokalizację."""
    await page.goto(url, wait_until="networkidle", timeout=60_000)
    await page.wait_for_timeout(800)
    data = await page.evaluate(
        """() => {
          const name = (document.querySelector('h1') || {}).innerText || '';
          const body = document.body.innerText || '';
          const tables = [...document.querySelectorAll('table')].map(t =>
            [...t.querySelectorAll('tr')].map(tr =>
              [...tr.querySelectorAll('th,td')].map(td =>
                td.innerText.trim().replace(/\\s+/g, ' ')
              )
            )
          );
          let ocena = '', dataOc = '', nast = '', przyczyna = '', powodFlagi = '';
          const m1 = body.match(/Ocena wody\\s*\\n\\s*(.+)/);
          if (m1) ocena = m1[1].trim();
          const m2 = body.match(/Data oceny:\\s*(\\d{2}\\/\\d{2}\\/\\d{4})/);
          if (m2) dataOc = m2[1];
          const m3 = body.match(/Następne badanie:\\s*(\\d{2}\\/\\d{2}\\/\\d{4})/);
          if (m3) nast = m3[1];
          const sezon = (body.match(/Sezon kąpielowy[^\\n]{0,80}/) || [''])[0];
          const flagM = body.match(/Powód wywieszenia czerwonej flagi:\\s*\\n?\\s*([^\\n]+)/i);
          if (flagM) powodFlagi = flagM[1].trim();

          // Przyczyna z tabeli ocen (HTML: ...<hr>Przyczyna:<br>Zakwit sinic)
          for (const t of document.querySelectorAll('table')) {
            const rows = [...t.querySelectorAll('tr')];
            if (rows.length < 2) continue;
            const head = (rows[0].innerText || '').toLowerCase();
            if (!head.includes('ocena') && !head.includes('coli')) continue;
            const cells = [...rows[1].querySelectorAll('th,td')];
            if (cells.length < 2) continue;
            const ocHtml = cells[1].innerHTML || '';
            const ocText = (cells[1].innerText || '').replace(/\\s+/g, ' ').trim();
            const pHtml = ocHtml.match(/Przyczyna:\\s*(?:<br\\s*\\/?>)?\\s*([^<]+)/i);
            const pText = ocText.match(/Przyczyna:\\s*(.+)$/i);
            if (pHtml) przyczyna = pHtml[1].trim();
            else if (pText) przyczyna = pText[1].trim();
            if (!przyczyna && powodFlagi) przyczyna = powodFlagi;
            // ocena z komórki bez bloku Przyczyna
            const ocClean = ocText.replace(/Przyczyna:\\s*.+$/i, '').trim();
            if (ocClean) ocena = ocClean;
            break;
          }

          const grab = (label) => {
            const re = new RegExp(label + '\\\\s*\\\\n\\\\s*([^\\\\n]+)', 'i');
            const m = body.match(re);
            return m ? m[1].trim() : '';
          };
          let adres = grab('Adres:');
          if (!adres) adres = grab('Adres');
          let akwen = grab('Akwen:');
          if (!akwen) akwen = grab('Akwen');
          let woj = '';
          let pow = '';
          const wojM = body.match(/woj\\.\\s*([^,\\n]+)/i);
          if (wojM) woj = wojM[1].trim();
          const powM = body.match(/pow\\.\\s*([^,\\n]+)/i);
          if (powM) pow = powM[1].trim();
          // czasem w linii adresu: "Kruklanki\\nwoj.warmińsko-mazurskie, pow.giżycki"
          if (!woj || !pow) {
            const line = body.match(/woj\\.([^\\n]+)/i);
            if (line) {
              const bits = line[1].split(',');
              if (!woj && bits[0]) woj = bits[0].replace(/^\\s*/, '').trim();
              if (!pow) {
                const p2 = line[1].match(/pow\\.\\s*([^,\\n]+)/i);
                if (p2) pow = p2[1].trim();
              }
            }
          }
          return { name, ocena, dataOc, nast, sezon, tables, adres, akwen, woj, pow, przyczyna, powodFlagi };
        }"""
    )
    if not data:
        return None

    ocena = (data.get("ocena") or "").strip()
    data_oceny = (data.get("dataOc") or "").strip()
    nastepne = (data.get("nast") or "").strip()
    przyczyna = (data.get("przyczyna") or data.get("powodFlagi") or "").strip()
    ecoli = enterokoki = ""

    tables = data.get("tables") or []
    for table in tables:
        if not table or len(table) < 2:
            continue
        header = " ".join(table[0]).lower()
        if "ocena" not in header and "coli" not in header:
            continue
        row = table[1]
        if len(row) >= 2:
            cell_ocena, cell_przyczyna = _split_ocena_przyczyna(row[1])
            data_oceny = data_oceny or (row[0] if row else "")
            if cell_ocena:
                ocena = ocena or cell_ocena
            if cell_przyczyna and not przyczyna:
                przyczyna = cell_przyczyna
        if len(row) >= 5:
            ecoli = _parse_int(row[2])
            enterokoki = _parse_int(row[3])
            nastepne = nastepne or row[4]
            break
        if len(row) >= 2:
            break

    if not przyczyna:
        przyczyna = (data.get("powodFlagi") or "").strip()
    # sprzątanie oceny, gdy scrap wcześniej skleił Przyczyna:
    ocena, przyczyna2 = _split_ocena_przyczyna(ocena)
    if przyczyna2 and not przyczyna:
        przyczyna = przyczyna2

    sezon_od = sezon_do = ""
    sm = _SEZON_RE.search(data.get("sezon") or "")
    if not sm:
        sm = _SEZON_RE.search(await page.inner_text("body"))
    if sm:
        sezon_od, sezon_do = sm.group(1), sm.group(2)

    if not ocena and not data_oceny:
        return None

    adres = (data.get("adres") or "").strip()
    powiat = (data.get("pow") or "").strip()
    wojewodztwo = (data.get("woj") or "").strip()
    akwen = (data.get("akwen") or "").strip()
    loc_parts = []
    if adres:
        loc_parts.append(adres.replace("\n", ", "))
    if powiat:
        loc_parts.append(f"pow. {powiat}" if not powiat.lower().startswith("pow") else powiat)
    if wojewodztwo:
        loc_parts.append(
            f"woj. {wojewodztwo}" if not wojewodztwo.lower().startswith("woj") else wojewodztwo
        )
    if akwen:
        loc_parts.append(akwen)
    lokalizacja = ", ".join(loc_parts)

    kid = url.rstrip("/").rsplit("/", 1)[-1]
    return {
        "id": kid,
        "name": (data.get("name") or "").strip() or f"Kąpielisko {kid}",
        "url": url,
        "ocena": ocena,
        "data_oceny": data_oceny,
        "nastepne_badanie": nastepne,
        "ecoli": ecoli,
        "enterokoki": enterokoki,
        "przyczyna": przyczyna,
        "sezon_od": sezon_od,
        "sezon_do": sezon_do,
        "adres": adres,
        "powiat": powiat,
        "wojewodztwo": wojewodztwo,
        "akwen": akwen,
        "lokalizacja": lokalizacja,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def in_season(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    return now.month in config.SEASON_MONTHS


async def run_baseline(
    *,
    interval_sec: float = 2.0,
    only_missing: bool = True,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """Jednorazowo pobierz aktualne oceny dla całej listy (bez alertów / queue).

    Potem poller tylko porównuje i aktualizuje. Przy `only_missing=True` pomija
    kąpieliska, które już mają wiersz w oceny.csv (da się wznawiać).
    """
    sites = load_list()
    if not sites:
        raise RuntimeError("Brak listy — uruchom najpierw: python -m kapieliska bootstrap")

    current = load_oceny()
    already = sum(1 for s in sites if s["id"] in current)
    todo = []
    for s in sites:
        if only_missing and s["id"] in current:
            continue
        todo.append(s)
    if limit is not None:
        todo = todo[:limit]

    log.info(
        "Baseline: do pobrania %d / %d (już mamy %d, interval=%.1fs)",
        len(todo), len(sites), already, interval_sec,
    )
    stats = {
        "checked": 0,
        "saved": 0,
        "already_had": already,
        "errors": 0,
        "total_list": len(sites),
    }

    if not todo:
        log.info("Baseline: nic do zrobienia — wszystkie mają oceny.")
        return stats

    async with browser_page() as (_browser, page):
        await warm_session(page)
        for i, site in enumerate(todo):
            url = site["url"]
            try:
                row = await parse_detail(page, url)
                stats["checked"] += 1
                if not row:
                    log.warning("Baseline brak oceny: %s", url)
                    stats["errors"] += 1
                else:
                    # Użyj nazwy z listy jeśli lepsza
                    if site.get("name") and not row.get("name"):
                        row["name"] = site["name"]
                    upsert_ocena(row, prev=None)
                    current[row["id"]] = row
                    stats["saved"] += 1
                    if (i + 1) % 25 == 0 or i == 0:
                        log.info(
                            "Baseline progress %d/%d — %s: %s",
                            i + 1, len(todo), row.get("name", ""), row.get("ocena", ""),
                        )
            except Exception as e:
                stats["errors"] += 1
                log.exception("Baseline błąd %s: %s", url, e)

            if i < len(todo) - 1 and interval_sec > 0:
                await asyncio.sleep(interval_sec)

    log.info("Baseline done: %s (oceny łącznie: %d)", stats, len(load_oceny()))
    return stats


async def run_cycle(
    *,
    batch_size: Optional[int] = None,
    interval_sec: Optional[float] = None,
    force: bool = False,
    enqueue: bool = True,
) -> dict[str, Any]:
    """Jeden cykl round-robin: batch_size kąpielisk."""
    if not force and not in_season():
        log.info("Poza sezonem (miesiące %s) — pomijam cykl.", config.SEASON_MONTHS)
        return {"skipped": True, "reason": "off_season"}

    sites = load_list()
    if not sites:
        raise RuntimeError("Brak listy — uruchom najpierw: python -m kapieliska bootstrap")

    batch = batch_size if batch_size is not None else config.BATCH_SIZE
    interval = interval_sec if interval_sec is not None else config.POLL_INTERVAL_SEC
    cursor = load_cursor()
    start = int(cursor.get("next_index") or 0) % len(sites)
    slice_sites = []
    for i in range(batch):
        slice_sites.append(sites[(start + i) % len(sites)])
    next_index = (start + batch) % len(sites)

    log.info(
        "Cykl: index %d→%d, batch=%d, interval=%.0fs",
        start, next_index, len(slice_sites), interval,
    )

    current = load_oceny()
    purge_expired_alerts()
    stats = {"checked": 0, "changed": 0, "alerts": 0, "status_updates": 0, "errors": 0}

    async with browser_page() as (_browser, page):
        await warm_session(page)
        for i, site in enumerate(slice_sites):
            url = site["url"]
            try:
                row = await parse_detail(page, url)
                stats["checked"] += 1
                if not row:
                    log.warning("Brak oceny: %s", url)
                    stats["errors"] += 1
                else:
                    prev = current.get(row["id"])
                    decision = evaluate_change(prev, row)
                    if decision.get("is_new_assessment"):
                        upsert_ocena(row, prev=prev)
                        current[row["id"]] = row
                        stats["changed"] += 1
                        log.info(
                            "Nowa ocena %s: %s → %s (%s)",
                            row["name"],
                            (prev or {}).get("data_oceny", "—"),
                            row["data_oceny"],
                            row["ocena"],
                        )
                        active = get_active_alert(row["id"])

                        # 1) Zagrożenie → propozycja posta FB (tylko threat)
                        if decision.get("should_alert"):
                            stats["alerts"] += 1
                            append_update({
                                "id": row["id"],
                                "name": row["name"],
                                "url": row["url"],
                                "ocena": row["ocena"],
                                "data_oceny": row["data_oceny"],
                                "ecoli": row.get("ecoli", ""),
                                "enterokoki": row.get("enterokoki", ""),
                                "przyczyna": row.get("przyczyna", ""),
                                "reason": decision.get("reason", ""),
                                "prev_ocena": (prev or {}).get("ocena", ""),
                                "prev_data_oceny": (prev or {}).get("data_oceny", ""),
                                "lokalizacja": row.get("lokalizacja", ""),
                                "kind": "threat",
                            })
                            register_active_alert(row)
                            if enqueue:
                                _enqueue_alert(row, decision, prev)

                        # 2) Zmiana statusu przy aktywnym alercie (30 dni) → TG + update komentarza?
                        elif (
                            decision.get("should_status_notify")
                            and active
                            and prev
                        ):
                            stats["status_updates"] += 1
                            append_update({
                                "id": row["id"],
                                "name": row["name"],
                                "url": row["url"],
                                "ocena": row["ocena"],
                                "data_oceny": row["data_oceny"],
                                "ecoli": row.get("ecoli", ""),
                                "enterokoki": row.get("enterokoki", ""),
                                "przyczyna": row.get("przyczyna", ""),
                                "reason": decision.get("reason", ""),
                                "prev_ocena": prev.get("ocena", ""),
                                "prev_data_oceny": prev.get("data_oceny", ""),
                                "lokalizacja": row.get("lokalizacja", ""),
                                "kind": "status_change",
                            })
                            register_active_alert(row, fb_post_id=active.get("fb_post_id", ""))
                            if enqueue:
                                _enqueue_status_change(row, decision, prev, active)

                    elif not prev:
                        upsert_ocena(row, prev=None)
                        current[row["id"]] = row
                        log.info("Baseline %s: %s", row["name"], row["ocena"])
            except Exception as e:
                stats["errors"] += 1
                log.exception("Błąd %s: %s", url, e)

            if i < len(slice_sites) - 1 and interval > 0:
                await asyncio.sleep(interval)

    save_cursor(next_index)
    log.info("Cykl done: %s", stats)
    return stats


def _enqueue_alert(row: dict, decision: dict, prev: Optional[dict]) -> None:
    try:
        from core import queue as handoff
        from .prompts import build_alert_text

        text = build_alert_text(row, decision, prev)
        handoff.enqueue({
            "source": "KĄPIELISKA",
            "kind": "threat",
            "kapielisko_id": row["id"],
            "title": f"Kąpielisko: {row['name']} — {row['ocena']}",
            "date": row.get("data_oceny", ""),
            "url": row["url"],
            "text": text,
            "lokalizacja": row.get("lokalizacja", ""),
        })
        log.info("Enqueue threat alert: %s (%s)", row["name"], row.get("lokalizacja", ""))
    except Exception as e:
        log.error("Enqueue failed: %s", e)


def _enqueue_status_change(
    row: dict, decision: dict, prev: dict, active: dict,
) -> None:
    try:
        from core import queue as handoff
        from .prompts import build_status_update_text

        text = build_status_update_text(row, prev, decision)
        handoff.enqueue({
            "source": "KĄPIELISKA_STATUS",
            "kind": "status_change",
            "kapielisko_id": row["id"],
            "fb_post_id": active.get("fb_post_id", ""),
            "title": f"Update statusu: {row['name']}",
            "date": row.get("data_oceny", ""),
            "url": row["url"],
            "text": text,
            "lokalizacja": row.get("lokalizacja", ""),
            "ocena": row.get("ocena", ""),
            "prev_ocena": prev.get("ocena", ""),
        })
        log.info("Enqueue status change: %s", row["name"])
    except Exception as e:
        log.error("Enqueue status failed: %s", e)


async def run_loop() -> None:
    """Pętla sezonowa: CYCLES_PER_DAY cykli rozłożonych w ciągu dnia."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [kapieliska] %(levelname)s %(message)s",
    )
    while True:
        if not in_season():
            log.info("Poza sezonem — sleep 6h")
            await asyncio.sleep(6 * 3600)
            continue
        try:
            await run_cycle()
        except Exception:
            log.exception("Cykl failed")
        # rozłóż cykle w ciągu ~14h dnia aktywności
        sleep_h = max(2.0, 14.0 / max(1, config.CYCLES_PER_DAY))
        log.info("Następny cykl za %.1fh", sleep_h)
        await asyncio.sleep(sleep_h * 3600)
