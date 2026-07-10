#!/bin/bash
#
# Isolated deploy for alertkonsumencki. Every podman-compose command is scoped to
# this project only (COMPOSE_PROJECT_NAME=alertkonsumencki), so it never touches
# newsautomation — and newsautomation's own deploy never touches this one.
#
# Usage:
#   ./deploy.sh            # build + start + watch for local/git changes
#   ./deploy.sh restart    # recreate the container (no rebuild)
#   ./deploy.sh rebuild    # rebuild image + recreate
#   ./deploy.sh down       # stop + remove this project only
#   ./deploy.sh logs       # follow bot logs
#   ./deploy.sh logs-crawler # follow GIS crawler logs
#   ./deploy.sh status     # show this project's containers
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# Isolation: unique project + container + image names.
export COMPOSE_PROJECT_NAME=alertkonsumencki
CONTAINER=alertkonsumencki_bot
COMPOSE="podman-compose"

# ── Tweakables ──────────────────────────────────────────────────
POLL_INTERVAL=5
export CRAWLER_INTERVAL="${CRAWLER_INTERVAL:-600}"

# Dropped by the bot's /redeploy and /restart Telegram commands (bot runs in a
# container with no podman access, so it can't call this script directly).
REDEPLOY_TRIGGER_FILE="session/.redeploy_trigger"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
info()  { echo -e "${YELLOW}[INFO]${NC} $1"; }

notify_telegram() {
    local text="$1"
    local bot_token chat_id
    bot_token=$(grep -E '^BOT_TOKEN=' .env | head -1 | cut -d= -f2-)
    chat_id=$(grep -E '^INTERNAL_CHAT_ID=' .env | head -1 | cut -d= -f2-)
    if [ -z "$chat_id" ]; then
        chat_id=$(grep -E '^REVIEWER_IDS=' .env | head -1 | cut -d= -f2- | cut -d, -f1 | tr -d ' ')
    fi
    if [ -z "$bot_token" ] || [ -z "$chat_id" ]; then
        info "Telegram notification skipped (brak BOT_TOKEN/chat id w .env)."
        return 0
    fi
    curl -s -X POST "https://api.telegram.org/bot${bot_token}/sendMessage" \
        -d chat_id="${chat_id}" -d text="${text}" >/dev/null 2>&1 || true
}

LOG_PIDS=()
start_logs() {
    stop_logs
    for svc in "$CONTAINER" alertkonsumencki_crawler; do
        if podman container exists "$svc" >/dev/null 2>&1; then
            podman logs -f --tail=100 "$svc" 2>&1 | sed "s/^/[$svc] /" &
            LOG_PIDS+=("$!")
        else
            info "Container $svc is not present, skipping log tail."
        fi
    done
}

stop_logs() {
    for pid in "${LOG_PIDS[@]}"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    LOG_PIDS=()
}

follow_logs() {
    start_logs
}

cleanup() {
    stop_logs
    exit 0
}
trap cleanup INT TERM

get_mtime() {
    find "$REPO_DIR" \( -name '*.py' -o -name '*.txt' -o -name 'Containerfile' -o -name '*.yml' -o -name '.env' \) \
        -not -path '*/__pycache__/*' \
        -not -path '*/queue/*' \
        -not -path '*/session/*' \
        -not -path '*/gis_alerts/*' \
        -exec stat -c %Y {} + 2>/dev/null | sort -n | tail -1 || echo 0
}

if [ ! -f .env ]; then
    error "Brak pliku .env — skopiuj .env.example do .env i uzupełnij (patrz README_BOT_INTEGRATION.md)."
    exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    error "Ten katalog nie jest repozytorium git. Nie można włączyć watch/redeploy."
    exit 1
fi

REMOTE_URL=$(git remote get-url origin 2>/dev/null || true)
if [[ "$REMOTE_URL" == https://github.com/* ]]; then
    SSH_URL="git@github.com:${REMOTE_URL#https://github.com/}"
    git remote set-url origin "$SSH_URL" 2>/dev/null || true
    info "Switched remote to SSH: $SSH_URL"
fi

# Pull latest origin/main before manual /restart (Telegram trigger).
sync_from_main() {
    log "Syncing repo with origin/main..."
    if ! git fetch origin main 2>&1; then
        error "git fetch origin main failed."
        notify_telegram "⚠️ git fetch origin/main failed — rebuild z lokalnego kodu"
        return 1
    fi
    if ! git rev-parse origin/main >/dev/null 2>&1; then
        error "Brak gałęzi origin/main."
        notify_telegram "⚠️ Brak origin/main — rebuild z lokalnego kodu"
        return 1
    fi
    REMOTE_REV=$(git rev-parse origin/main)
    LOCAL_REV=$(git rev-parse HEAD)
    if [ "$REMOTE_REV" = "$LOCAL_REV" ]; then
        info "Już na origin/main ($(git log -1 --oneline))."
        return 0
    fi
    log "Reset do origin/main ($(git log -1 --oneline origin/main))..."
    if ! git reset --hard origin/main; then
        error "git reset --hard origin/main failed."
        notify_telegram "⚠️ git reset origin/main failed — rebuild z lokalnego kodu"
        return 1
    fi
    log "Git sync OK: $(git log -1 --oneline)"
    notify_telegram "📥 Git: $(git log -1 --format='%h %s')"
    return 0
}

deploy() {
    stop_logs
    log "Building images and starting containers..."
    if ! $COMPOSE build; then
        error "Build failed."
        start_logs
        return 1
    fi
    if ! $COMPOSE up -d --force-recreate; then
        error "Deploy failed."
        start_logs
        return 1
    fi
    log "Deployed. Streaming logs..."
    start_logs
}

rebuild() {
    stop_logs
    log "Rebuilding image (no cache) + recreating..."
    $COMPOSE build --no-cache
    $COMPOSE up -d --force-recreate
    log "Rebuilt and running."
    start_logs
}

restart_only() {
    stop_logs
    log "Restarting container (no build)..."
    if ! $COMPOSE up -d --force-recreate; then
        error "Restart failed."
        start_logs
        return 1
    fi
    log "Restart complete. Streaming logs..."
    start_logs
}

if [ "${1:-up}" = "restart" ]; then
    restart_only
    exit $?
fi

if [ "${1:-up}" = "rebuild" ]; then
    rebuild
    exit 0
fi

if [ "${1:-up}" = "down" ] || [ "${1:-up}" = "stop" ]; then
    stop_logs
    log "Stopping + removing this project's containers..."
    $COMPOSE down
    log "Stopped."
    exit 0
fi

if [ "${1:-up}" = "logs" ]; then
    follow_logs
    exit 0
fi

if [ "${1:-up}" = "logs-crawler" ]; then
    podman logs -f --tail=100 alertkonsumencki_crawler
    exit 0
fi

if [ "${1:-up}" = "status" ]; then
    podman ps --filter "name=^alertkonsumencki_" --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
    exit 0
fi

if [ "${1:-up}" != "up" ] && [ "${1:-up}" != "deploy" ]; then
    echo "usage: $0 {up|deploy|rebuild|restart|down|logs|logs-crawler|status}"
    exit 1
fi

deploy

LAST_MTIME=$(get_mtime)
LAST_GIT_REV=$(git rev-parse HEAD 2>/dev/null || true)

log "Watching local files and origin/main for changes..."
while true; do
    sleep "$POLL_INTERVAL"

    if [ -f "$REDEPLOY_TRIGGER_FILE" ]; then
        TRIGGER_MODE=$(tr -d '[:space:]' < "$REDEPLOY_TRIGGER_FILE")
        rm -f "$REDEPLOY_TRIGGER_FILE"
        notify_telegram "🔄 System initiated redeployment"
        if [ "$TRIGGER_MODE" = "rebuild" ]; then
            log "Manual /restart trigger detected. git pull + rebuild..."
            sync_from_main || info "Git sync failed — rebuild z obecnego drzewa."
            rebuild
        else
            log "Manual /redeploy trigger detected. Redeploying..."
            deploy
        fi
        notify_telegram "✅ System redeployment done"
        LAST_MTIME=$(get_mtime)
        LAST_GIT_REV=$(git rev-parse HEAD 2>/dev/null || true)
        continue
    fi

    CURRENT_MTIME=$(get_mtime)
    if [ "$CURRENT_MTIME" != "$LAST_MTIME" ]; then
        log "Local files changed. Redeploying..."
        LAST_MTIME="$CURRENT_MTIME"
        deploy
        LAST_GIT_REV=$(git rev-parse HEAD 2>/dev/null || true)
        continue
    fi

    if git fetch origin main >/dev/null 2>&1; then
        REMOTE_REV=$(git rev-parse origin/main 2>/dev/null || true)
        if [ -n "$REMOTE_REV" ] && [ "$LAST_GIT_REV" != "$REMOTE_REV" ]; then
            if git merge-base --is-ancestor origin/main HEAD >/dev/null 2>&1; then
                log "New origin/main commit detected. Resetting to origin/main and redeploying..."
                notify_telegram "🔄 System initiated redeployment"
                git reset --hard origin/main
                LAST_GIT_REV="$REMOTE_REV"
                LAST_MTIME=$(get_mtime)
                deploy
                notify_telegram "✅ System redeployment done"
            else
                log "Origin/main advanced, but local HEAD is ahead. Skipping reset until local changes are pushed."
                LAST_GIT_REV=$(git rev-parse HEAD 2>/dev/null || true)
            fi
        fi
    fi
done
