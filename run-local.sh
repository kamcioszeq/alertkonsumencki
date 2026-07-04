#!/usr/bin/env bash
# Lokalne uruchomienie bota + crawlera (bez podmana).
#  - wyszukuje i ubija stare procesy tego projektu (venv),
#  - sprawdza, CO trzyma sesję/bazę SQLite (session/bot.session) i ją zwalnia,
#  - ostrzega, jeśli działa kontener podmana montujący ./session,
#  - Ctrl+C czysto zamyka oba procesy.
#
# Użycie:
#   ./run-local.sh          # sprawdź + zwolnij + uruchom bota i crawlera
#   ./run-local.sh --check  # tylko pokaż, co trzyma sesję (nic nie ubija, nie startuje)
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

PY="$REPO_DIR/venv/bin/python"
SESSION="session/bot.session"
SESSION_FILES="$SESSION ${SESSION}-journal ${SESSION}-wal ${SESSION}-shm"

G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; N='\033[0m'
log()  { printf "${G}[run-local]${N} %s\n" "$*"; }
warn() { printf "${Y}[run-local]${N} %s\n" "$*"; }
err()  { printf "${R}[run-local]${N} %s\n" "$*" >&2; }

show_procs() { for pid in "$@"; do printf "   PID %-7s %s\n" "$pid" "$(ps -p "$pid" -o command= 2>/dev/null)"; done; }

session_holders() { lsof -t $SESSION_FILES 2>/dev/null | sort -u | tr '\n' ' '; }

project_pythons() { pgrep -f "$PY" 2>/dev/null | sort -u | tr '\n' ' '; }

podman_running() {
    command -v podman >/dev/null 2>&1 &&
        podman ps --format '{{.Names}}' 2>/dev/null | grep -q '^alertkonsumencki_bot$'
}

kill_pids() {  # $1=opis, reszta=PID-y
    local desc="$1"; shift
    [ "$#" -eq 0 ] && return 0
    warn "$desc:"; show_procs "$@"
    kill "$@" 2>/dev/null
    sleep 1
    local alive=""
    for pid in "$@"; do kill -0 "$pid" 2>/dev/null && alive="$alive $pid"; done
    if [ -n "${alive// }" ]; then warn "Wymuszam kill -9:$alive"; kill -9 $alive 2>/dev/null; sleep 1; fi
}

# ── Tryb --check: tylko raport ───────────────────────────────
if [ "${1:-}" = "--check" ]; then
    log "Procesy z venv tego projektu:"
    OLD="$(project_pythons)"; [ -n "${OLD// }" ] && show_procs $OLD || echo "   (brak)"
    log "Procesy trzymające sesję ($SESSION):"
    HOLD="$(session_holders)"; [ -n "${HOLD// }" ] && show_procs $HOLD || echo "   (brak — czysto)"
    podman_running && warn "Kontener 'alertkonsumencki_bot' działa (montuje ./session)."
    exit 0
fi

# ── Preconditions ────────────────────────────────────────────
[ -x "$PY" ] || { err "Brak $PY — utwórz venv: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"; exit 1; }
[ -f .env ]  || { err "Brak .env — skopiuj .env.example do .env i uzupełnij."; exit 1; }

# ── 1) Stare procesy z venv tego projektu (bot + crawler) ────
OLD="$(project_pythons)"
if [ -n "${OLD// }" ]; then kill_pids "Stare procesy tego projektu (venv)" $OLD; else log "Brak starych procesów z venv."; fi

# ── 2) Cokolwiek innego trzyma sesję/bazę SQLite ─────────────
HOLD="$(session_holders)"
if [ -n "${HOLD// }" ]; then kill_pids "Procesy trzymające sesję ($SESSION)" $HOLD; else log "Nic nie trzyma sesji ($SESSION) — czysto."; fi

# ── 3) Ostrzeżenie o kontenerze podmana ──────────────────────
if podman_running; then
    warn "Kontener 'alertkonsumencki_bot' działa i montuje ./session — zatrzymaj go: ./deploy.sh down"
fi

# ── 4) Finalna weryfikacja ───────────────────────────────────
STILL="$(session_holders)"
if [ -n "${STILL// }" ]; then
    err "Sesję NADAL coś trzyma (PID:$STILL). Podejrzyj: lsof $SESSION"
    err "Jeśli to bezpieczne, usuń pliki pomocnicze: rm -f ${SESSION}-journal ${SESSION}-wal ${SESSION}-shm"
    exit 1
fi

# ── 5) Start ─────────────────────────────────────────────────
log "Startuję bota i crawlera…  (Ctrl+C zamyka oba)"
"$PY" main.py &     BOT=$!
"$PY" -m crawler &  CRAWLER=$!

cleanup() {
    echo
    log "Zatrzymuję (PID $BOT, $CRAWLER)…"
    kill "$BOT" "$CRAWLER" 2>/dev/null
    wait "$BOT" "$CRAWLER" 2>/dev/null
    exit 0
}
trap cleanup INT TERM
wait
