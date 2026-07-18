"""Telegram: /kapieliska, /kapielisko_ostatnie — status i test posta."""
import html

from telethon import events

from . import config


def register_kapieliska_commands(bot):
    @bot.on(events.NewMessage(pattern=r"^/kapieliska(?:\s+(\d+))?$"))
    async def on_kapieliska(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return

        limit = 5
        raw = event.pattern_match.group(1)
        if raw:
            try:
                limit = min(20, max(1, int(raw)))
            except ValueError:
                limit = 5

        try:
            from kapieliska.store import (
                load_cursor, load_list, load_oceny, recent_updates, list_active_alerts,
            )
            from kapieliska.poller import in_season
            from kapieliska import config as kcfg
        except ImportError as e:
            await event.reply(f"Moduł kąpielisk niedostępny: {e}")
            return

        updates = recent_updates(limit)
        sites = load_list()
        oceny = load_oceny()
        cur = load_cursor()
        active = list_active_alerts()

        header = (
            "🏖️ <b>Kąpieliska</b>\n"
            f"Lista: {len(sites)} · oceny: {len(oceny)} · "
            f"sezon: {'tak' if in_season() else 'nie'}\n"
            f"Aktywne alerty (30 dni): {len(active)}\n"
            f"Cursor: {cur.get('next_index', 0)} · last_run: {html.escape(str(cur.get('last_run') or '—'))}\n"
            f"Batch: {kcfg.BATCH_SIZE} co {int(kcfg.POLL_INTERVAL_SEC)}s\n\n"
        )

        if not updates:
            body = (
                "Brak zapisanych zmian ocen.\n"
                "Test posta: <code>/kapielisko_ostatnie</code>"
            )
            await event.reply(header + body, parse_mode="html")
            return

        lines = [f"<b>Ostatnie {len(updates)} update’ów</b> (max {limit}):\n"]
        for i, u in enumerate(updates, 1):
            name = html.escape(u.get("name") or "?")
            ocena = html.escape(u.get("ocena") or "—")
            data = html.escape(u.get("data_oceny") or "—")
            reason = html.escape(u.get("reason") or "")
            url = html.escape(u.get("url") or "")
            ts = html.escape(u.get("ts") or "")
            loc = html.escape(u.get("lokalizacja") or "")
            kind = html.escape(u.get("kind") or "threat")
            ecoli = html.escape(u.get("ecoli") or "—")
            enter = html.escape(u.get("enterokoki") or "—")
            lines.append(
                f"{i}. <b>{name}</b> <i>({kind})</i>\n"
                f"   {ocena} · {data}\n"
                + (f"   📍 {loc}\n" if loc else "")
                + f"   E.coli {ecoli} · enterokoki {enter}\n"
                + (f"   Powód: {reason}\n" if reason else "")
                + (f"   {ts}\n" if ts else "")
                + (f"   {url}\n" if url else "")
            )
        await event.reply(header + "\n".join(lines), parse_mode="html", link_preview=False)

    @bot.on(events.NewMessage(pattern=r"^/kapielisko_ostatnie$"))
    async def on_kapielisko_ostatnie(event):
        """Test: najświeższa ocena → pełny flow Generuj FB (jak prawdziwy alert)."""
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return

        try:
            from kapieliska.store import freshest_ocena, load_oceny, load_list
            from kapieliska.detect import is_threat
            from kapieliska.prompts import build_alert_text
            from .ingest import ingest_warning
        except ImportError as e:
            await event.reply(f"Moduł kąpielisk niedostępny: {e}")
            return

        row = freshest_ocena()
        if not row:
            n_list = len(load_list())
            n_oc = len(load_oceny())
            await event.reply(
                "Brak ocen w CSV.\n"
                f"Lista: {n_list}, oceny: {n_oc}.\n"
                "Poczekaj na baseline (pobieram w tle).",
                parse_mode="html",
            )
            return

        threat = is_threat(row)
        decision = {
            "reason": "test /kapielisko_ostatnie",
            "is_threat": threat,
            "should_alert": True,
        }
        text = build_alert_text(row, decision, prev=None)
        text = (
            "[TEST /kapielisko_ostatnie — pełny flow posta FB]\n"
            + ("" if threat else "[Uwaga: ocena NIE jest zagrożeniem — test promptu mimo to]\n")
            + text
        )
        title = f"[TEST] Kąpielisko: {row.get('name', '')} — {row.get('ocena', '')}"
        await event.reply(
            "🏖️ Biorę najświeższą ocenę: "
            f"<b>{html.escape(row.get('name') or '?')}</b> "
            f"({html.escape(row.get('data_oceny') or '—')})\n"
            f"{'⚠️ zagrożenie' if threat else 'ℹ️ bez zagrożenia (test promptu)'}\n"
            "Zaraz wrzucę kartę z 📘 Generuj FB…",
            parse_mode="html",
        )
        await ingest_warning(
            bot,
            title=title,
            url=row.get("url", ""),
            text=text,
            date_str=row.get("data_oceny", ""),
            source="KĄPIELISKA",
            kind="threat",
            kapielisko_id=row.get("id", ""),
            lokalizacja=row.get("lokalizacja", ""),
        )
