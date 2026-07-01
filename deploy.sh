#!/bin/bash
#
# Isolated deploy for alertkonsumencki. Every podman-compose command is scoped to
# this project only (COMPOSE_PROJECT_NAME=alertkonsumencki), so it never touches
# newsautomation — and newsautomation's own deploy never touches this one.
#
# Usage:
#   ./deploy.sh            # build + start (detached)
#   ./deploy.sh restart    # recreate the container (no rebuild)
#   ./deploy.sh rebuild    # rebuild image + recreate
#   ./deploy.sh logs       # follow logs
#   ./deploy.sh down       # stop + remove (this project only)
#   ./deploy.sh status     # show this project's container
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# Isolation: unique project + container + image names.
export COMPOSE_PROJECT_NAME=alertkonsumencki
CONTAINER=alertkonsumencki_bot
COMPOSE="podman-compose"

GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${GREEN}[alertkonsumencki]${NC} $1"; }
error() { echo -e "${RED}[error]${NC} $1" >&2; }

if [ ! -f .env ]; then
    error "Brak pliku .env — skopiuj .env.example do .env i uzupełnij (patrz README_BOT_INTEGRATION.md)."
    exit 1
fi

case "${1:-up}" in
    up|deploy)
        log "Building + starting (project: $COMPOSE_PROJECT_NAME)..."
        $COMPOSE build
        $COMPOSE up -d
        log "Running. Container: $CONTAINER. Follow logs: ./deploy.sh logs"
        ;;
    rebuild)
        log "Rebuilding image (no cache) + recreating..."
        $COMPOSE build --no-cache
        $COMPOSE up -d --force-recreate
        log "Rebuilt and running."
        ;;
    restart)
        log "Recreating container (no rebuild)..."
        $COMPOSE up -d --force-recreate
        log "Restarted."
        ;;
    down|stop)
        log "Stopping + removing this project's container only..."
        $COMPOSE down
        log "Stopped."
        ;;
    logs)
        podman logs -f --tail=100 "$CONTAINER"
        ;;
    status)
        podman ps --filter "name=^${CONTAINER}$" --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
        ;;
    *)
        echo "usage: $0 {up|rebuild|restart|down|logs|status}"
        exit 1
        ;;
esac
