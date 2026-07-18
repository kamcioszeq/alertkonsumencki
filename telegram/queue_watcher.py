"""Background task: watch the handoff queue and ingest GIS warnings into the review flow."""
import asyncio

import config  # root config: QUEUE_DIR, QUEUE_POLL_INTERVAL
from core import queue as handoff
from .ingest import ingest_warning


async def watch_queue(bot):
    print(f"[QUEUE] Obserwuję kolejkę {config.QUEUE_DIR} co {config.QUEUE_POLL_INTERVAL}s")
    while True:
        try:
            for path in handoff.pending_files():
                item = handoff.read(path)
                await ingest_warning(
                    bot,
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    text=item.get("text", ""),
                    date_str=item.get("date", ""),
                    source=item.get("source", "GIS"),
                    kind=item.get("kind", ""),
                    kapielisko_id=item.get("kapielisko_id", ""),
                    fb_post_id=item.get("fb_post_id", ""),
                    lokalizacja=item.get("lokalizacja", ""),
                )
                handoff.remove(path)
                print(f"[QUEUE] Odebrano ostrzeżenie: {item.get('title', '')[:60]}")
        except Exception as e:
            print(f"[QUEUE] Błąd: {e}")
        await asyncio.sleep(config.QUEUE_POLL_INTERVAL)
