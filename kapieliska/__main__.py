"""CLI: python -m kapieliska {bootstrap|once|loop|status}."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from . import config
from .bootstrap import run_bootstrap
from .poller import in_season, run_baseline, run_cycle, run_loop
from .store import load_cursor, load_list, load_oceny, recent_updates


def _setup_log() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [kapieliska] %(levelname)s %(message)s",
    )


async def _cmd_bootstrap(_args) -> None:
    n = await run_bootstrap()
    print(f"OK: {n} kąpielisk → {config.LIST_CSV}")
    print("Następny krok: python -m kapieliska baseline   # pełne oceny (bez alertów)")


async def _cmd_baseline(args) -> None:
    stats = await run_baseline(
        interval_sec=args.interval,
        only_missing=not args.refresh,
        limit=args.limit,
    )
    print(stats)
    oceny = load_oceny()
    sites = load_list()
    print(f"oceny: {len(oceny)} / lista: {len(sites)}")
    if len(oceny) < len(sites):
        print("Uwaga: nie wszystkie mają baseline — odpal ponownie `baseline` (wznawia).")


async def _cmd_once(args) -> None:
    sites = load_list()
    oceny = load_oceny()
    if sites and len(oceny) < max(1, int(0.8 * len(sites))):
        print(
            f"UWAGA: oceny {len(oceny)}/{len(sites)} — najpierw "
            "`python -m kapieliska baseline`, inaczej pierwsze odczyty to cichy baseline."
        )
    stats = await run_cycle(
        batch_size=args.batch,
        interval_sec=args.interval,
        force=args.force,
        enqueue=not args.no_enqueue,
    )
    print(stats)


async def _cmd_loop(_args) -> None:
    sites = load_list()
    oceny = load_oceny()
    if sites and len(oceny) < max(1, int(0.8 * len(sites))):
        logging.getLogger("kapieliska").warning(
            "oceny %d/%d — uruchom `python -m kapieliska baseline` przed loop",
            len(oceny), len(sites),
        )
    await run_loop()


def _cmd_status(_args) -> None:
    sites = load_list()
    oceny = load_oceny()
    cur = load_cursor()
    updates = recent_updates(5)
    print(f"lista:     {len(sites)} ({config.LIST_CSV})")
    print(f"oceny:     {len(oceny)} ({config.OCENY_CSV})")
    if sites:
        pct = 100.0 * len(oceny) / len(sites)
        print(f"baseline:  {pct:.0f}% ({'OK' if pct >= 80 else 'URUCHOM: python -m kapieliska baseline'})")
    print(f"cursor:    {cur}")
    print(f"sezon:     {'TAK' if in_season() else 'NIE'} (miesiące {config.SEASON_MONTHS})")
    print(f"batch:     {config.BATCH_SIZE} × {config.POLL_INTERVAL_SEC}s")
    print("ostatnie update'y:")
    if not updates:
        print("  (brak)")
    for u in updates:
        print(
            f"  {u.get('ts','')} | {u.get('name','')} | {u.get('ocena','')} | "
            f"{u.get('reason','')}"
        )


def main(argv=None) -> None:
    _setup_log()
    p = argparse.ArgumentParser(prog="kapieliska", description="Crawler kąpielisk GIS")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("bootstrap", help="Pobierz pełną listę (~718) do CSV")
    base = sub.add_parser(
        "baseline",
        help="Pobierz aktualne oceny dla całej listy (bez alertów) — zrób raz przed loop",
    )
    base.add_argument(
        "--interval", type=float, default=2.0,
        help="sekundy między kąpieliskami (domyślnie 2)",
    )
    base.add_argument(
        "--refresh", action="store_true",
        help="pobierz wszystkie od nowa (nie tylko brakujące)",
    )
    base.add_argument("--limit", type=int, default=None, help="max ile pobrać (test)")
    once = sub.add_parser("once", help="Jeden cykl round-robin (tylko update vs baseline)")
    once.add_argument("--batch", type=int, default=None)
    once.add_argument("--interval", type=float, default=None, help="sekundy między requestami")
    once.add_argument("--force", action="store_true", help="ignoruj poza-sezon")
    once.add_argument("--no-enqueue", action="store_true", help="nie wrzucaj do queue/")
    sub.add_parser("loop", help="Pętla sezonowa")
    sub.add_parser("status", help="Podsumowanie CSV / cursor")

    args = p.parse_args(argv)
    if args.cmd == "bootstrap":
        asyncio.run(_cmd_bootstrap(args))
    elif args.cmd == "baseline":
        asyncio.run(_cmd_baseline(args))
    elif args.cmd == "once":
        asyncio.run(_cmd_once(args))
    elif args.cmd == "loop":
        asyncio.run(_cmd_loop(args))
    elif args.cmd == "status":
        _cmd_status(args)
    else:
        p.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
