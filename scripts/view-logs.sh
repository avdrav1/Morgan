#!/bin/bash

#######################################
# View Logs Script for Production
#######################################
# This script allows viewing logs from Docker containers
# and the persistent log volume.
#
# Usage: 
#   ./scripts/view-logs.sh [service_name] [options]
#   ./scripts/view-logs.sh backend --tail 100
#   ./scripts/view-logs.sh --volume
#   ./scripts/view-logs.sh --all

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
LOG_VOLUME="accountability-app-logs"
COMPOSE_FILE="docker-compose.prod.yml"

# Function to show usage
show_usage() {
    echo "Usage: $0 [service_name] [options]"
    echo ""
    echo "Services:"
    echo "  backend         - FastAPI backend logs"
    echo "  celery-worker   - Celery worker logs"
    echo "  celery-beat     - Celery beat scheduler logs"
    echo "  discord-bot     - Discord bot logs"
    echo "  postgres        - PostgreSQL logs"
    echo "  redis           - Redis logs"
    echo "  nginx           - Nginx logs"
    echo "  frontend        - Frontend logs"
    echo ""
    echo "Options:"
    echo "  --tail N        - Show last N lines (default: 50)"
    echo "  --follow, -f    - Follow log output"
    echo "  --volume        - View logs from persistent volume"
    echo "  --all           - Show logs from all services"
    echo "  --since TIME    - Show logs since timestamp (e.g., 2023-01-01T00:00:00)"
    echo "  --help, -h      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 backend --tail 100"
    echo "  $0 backend --follow"
    echo "  $0 --all --tail 20"
    echo "  $0 --volume"
    echo "  $0 backend --since 2024-01-01T00:00:00"
}

# Parse arguments
SERVICE=""
TAIL_LINES="50"
FOLLOW=""
VIEW_VOLUME=false
VIEW_ALL=false
SINCE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_usage
            exit 0
            ;;
        --tail)
            TAIL_LINES="$2"
            shift 2
            ;;
        --follow|-f)
            FOLLOW="--follow"
            shift
            ;;
        --volume)
            VIEW_VOLUME=true
            shift
            ;;
        --all)
            VIEW_ALL=true
            shift
            ;;
        --since)
            SINCE="--since $2"
            shift 2
            ;;
        backend|celery-worker|celery-beat|discord-bot|postgres|redis|nginx|frontend)
            SERVICE="$1"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# View logs from persistent volume
if [ "$VIEW_VOLUME" = true ]; then
    echo -e "${BLUE}Viewing logs from persistent volume: $LOG_VOLUME${NC}"
    echo ""
    
    if ! docker volume inspect "$LOG_VOLUME" > /dev/null 2>&1; then
        echo -e "${YELLOW}Warning: Log volume '$LOG_VOLUME' does not exist${NC}"
        exit 1
    fi
    
    # Create temporary container to access volume
    TEMP_CONTAINER="log-viewer-temp-$$"
    docker run --rm \
        --mount source="$LOG_VOLUME",target=/var/log/app \
        alpine:latest \
        sh -c "find /var/log/app -type f \( -name '*.log' -o -name '*.gz' \) -ls && echo '' && echo 'Recent logs:' && find /var/log/app -type f -name '*.log' -exec tail -n 20 {} +"
    
    exit 0
fi

# View all services
if [ "$VIEW_ALL" = true ]; then
    echo -e "${BLUE}Viewing logs from all services${NC}"
    echo ""
    docker-compose -f "$COMPOSE_FILE" logs --tail="$TAIL_LINES" $FOLLOW $SINCE
    exit 0
fi

# View specific service
if [ -z "$SERVICE" ]; then
    echo -e "${RED}Error: No service specified${NC}"
    echo ""
    show_usage
    exit 1
fi

echo -e "${BLUE}Viewing logs for service: $SERVICE${NC}"
echo ""

# Check if service exists
if ! docker-compose -f "$COMPOSE_FILE" ps "$SERVICE" > /dev/null 2>&1; then
    echo -e "${RED}Error: Service '$SERVICE' not found${NC}"
    echo ""
    echo "Available services:"
    docker-compose -f "$COMPOSE_FILE" ps --services
    exit 1
fi

# Show logs
docker-compose -f "$COMPOSE_FILE" logs --tail="$TAIL_LINES" $FOLLOW $SINCE "$SERVICE"
