#!/bin/bash

################################################################################
# Production Deployment Script
# 
# This script automates the deployment of the Proactive Accountability Assistant
# to a production environment with comprehensive checks and rollback capability.
#
# Features:
# - Pre-deployment validation (environment, ports, dependencies)
# - Service startup with dependency ordering
# - Post-deployment health checks
# - Automatic rollback on failure
# - Backup creation before deployment
#
# Requirements: 1.1, 1.2, 1.3
#
# Usage: ./deploy.sh [options]
# Options:
#   --skip-backup       Skip pre-deployment backup
#   --skip-build        Skip Docker image building
#   --skip-health       Skip health checks
#   --force             Force deployment even with warnings
#   --rollback          Rollback to previous deployment
#   --help              Show this help message
################################################################################

set -e

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

# Configuration
ENV_FILE="${ENV_FILE:-.env.production}"
COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="$PROJECT_ROOT/backups"
DEPLOYMENT_LOG="$PROJECT_ROOT/deployment.log"
STATE_FILE="$PROJECT_ROOT/.deployment_state"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Deployment options (can be overridden by command line)
SKIP_BACKUP=false
SKIP_BUILD=false
SKIP_HEALTH=false
FORCE_DEPLOY=false
ROLLBACK_MODE=false

# Timeout settings (in seconds)
HEALTH_CHECK_TIMEOUT=300
HEALTH_CHECK_INTERVAL=10
SERVICE_START_TIMEOUT=120

################################################################################
# Logging Functions
################################################################################

log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*" | tee -a "$DEPLOYMENT_LOG"
}

success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓${NC} $*" | tee -a "$DEPLOYMENT_LOG"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠${NC} $*" | tee -a "$DEPLOYMENT_LOG"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗${NC} $*" | tee -a "$DEPLOYMENT_LOG" >&2
}

section() {
    echo "" | tee -a "$DEPLOYMENT_LOG"
    echo -e "${BLUE}========================================${NC}" | tee -a "$DEPLOYMENT_LOG"
    echo -e "${BLUE}$*${NC}" | tee -a "$DEPLOYMENT_LOG"
    echo -e "${BLUE}========================================${NC}" | tee -a "$DEPLOYMENT_LOG"
}

################################################################################
# State Management Functions
################################################################################

save_deployment_state() {
    local state_data="$1"
    echo "$state_data" > "$STATE_FILE"
    log "Deployment state saved"
}

load_deployment_state() {
    if [ -f "$STATE_FILE" ]; then
        cat "$STATE_FILE"
    else
        echo ""
    fi
}

get_current_image_tags() {
    local tags=""
    
    # Get current image tags for all services
    for service in backend frontend discord-bot nginx; do
        local image_id=$(docker-compose -f "$COMPOSE_FILE" images -q "$service" 2>/dev/null || echo "")
        if [ -n "$image_id" ]; then
            tags="${tags}${service}:${image_id},"
        fi
    done
    
    echo "$tags"
}

################################################################################
# Pre-deployment Checks
################################################################################

check_prerequisites() {
    section "Checking Prerequisites"
    
    local errors=0
    
    # Check if running as root or with sudo
    if [ "$EUID" -eq 0 ]; then
        warning "Running as root. Consider using a non-root user with Docker permissions."
    fi
    
    # Check Docker
    log "Checking Docker installation..."
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        ((errors++))
    else
        success "Docker is installed: $(docker --version)"
    fi
    
    # Check Docker Compose
    log "Checking Docker Compose installation..."
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
        ((errors++))
    else
        success "Docker Compose is installed: $(docker-compose --version)"
    fi
    
    # Check if Docker daemon is running
    log "Checking Docker daemon..."
    if ! docker ps &> /dev/null; then
        error "Docker daemon is not running"
        ((errors++))
    else
        success "Docker daemon is running"
    fi
    
    # Check if compose file exists
    log "Checking Docker Compose file..."
    if [ ! -f "$COMPOSE_FILE" ]; then
        error "Docker Compose file not found: $COMPOSE_FILE"
        ((errors++))
    else
        success "Docker Compose file found: $COMPOSE_FILE"
    fi
    
    # Check if environment file exists
    log "Checking environment file..."
    if [ ! -f "$ENV_FILE" ]; then
        error "Environment file not found: $ENV_FILE"
        error "Please create it from .env.production.example"
        ((errors++))
    else
        success "Environment file found: $ENV_FILE"
    fi
    
    # Check disk space (require at least 5GB free)
    log "Checking disk space..."
    local available_space=$(df -BG "$PROJECT_ROOT" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$available_space" -lt 5 ]; then
        error "Insufficient disk space: ${available_space}GB available (minimum 5GB required)"
        ((errors++))
    else
        success "Sufficient disk space: ${available_space}GB available"
    fi
    
    return $errors
}

validate_environment() {
    section "Validating Environment Configuration"
    
    # Run environment validation script
    if [ -f "$PROJECT_ROOT/scripts/validate-env.sh" ]; then
        log "Running environment validation..."
        if bash "$PROJECT_ROOT/scripts/validate-env.sh" "$ENV_FILE"; then
            success "Environment validation passed"
            return 0
        else
            error "Environment validation failed"
            return 1
        fi
    else
        warning "Environment validation script not found, skipping..."
        return 0
    fi
}

check_port_availability() {
    section "Checking Port Availability"
    
    local errors=0
    local ports=(80 443)
    
    for port in "${ports[@]}"; do
        log "Checking port $port..."
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            local process=$(lsof -Pi :$port -sTCP:LISTEN | tail -n 1)
            warning "Port $port is already in use:"
            warning "$process"
            
            # Check if it's our own container
            if echo "$process" | grep -q "docker"; then
                warning "Port is used by Docker (possibly existing deployment)"
            else
                error "Port $port is in use by another process"
                ((errors++))
            fi
        else
            success "Port $port is available"
        fi
    done
    
    return $errors
}

check_docker_resources() {
    section "Checking Docker Resources"
    
    # Check Docker disk usage
    log "Checking Docker disk usage..."
    docker system df
    
    # Warn if Docker is using too much space
    local docker_space=$(docker system df --format "{{.Size}}" | head -1 | sed 's/GB//' | cut -d'.' -f1)
    if [ "$docker_space" -gt 50 ]; then
        warning "Docker is using ${docker_space}GB of disk space"
        warning "Consider running: docker system prune -a"
    fi
    
    return 0
}

################################################################################
# Backup Functions
################################################################################

create_pre_deployment_backup() {
    section "Creating Pre-Deployment Backup"
    
    if [ "$SKIP_BACKUP" = true ]; then
        warning "Skipping backup (--skip-backup flag set)"
        return 0
    fi
    
    # Check if database is running
    if ! docker ps --format '{{.Names}}' | grep -q "postgres"; then
        warning "Database container not running, skipping backup"
        return 0
    fi
    
    # Create backup
    log "Creating database backup..."
    if [ -f "$PROJECT_ROOT/scripts/backup-database.sh" ]; then
        if bash "$PROJECT_ROOT/scripts/backup-database.sh"; then
            success "Pre-deployment backup created"
            return 0
        else
            error "Failed to create backup"
            return 1
        fi
    else
        warning "Backup script not found, skipping backup"
        return 0
    fi
}

################################################################################
# Build Functions
################################################################################

build_docker_images() {
    section "Building Docker Images"
    
    if [ "$SKIP_BUILD" = true ]; then
        warning "Skipping build (--skip-build flag set)"
        return 0
    fi
    
    log "Building Docker images..."
    
    # Load environment variables for build args
    export $(grep -v '^#' "$ENV_FILE" | xargs)
    
    # Build images
    if docker-compose -f "$COMPOSE_FILE" build --no-cache; then
        success "Docker images built successfully"
        return 0
    else
        error "Failed to build Docker images"
        return 1
    fi
}

################################################################################
# Deployment Functions
################################################################################

stop_existing_services() {
    section "Stopping Existing Services"
    
    log "Checking for running services..."
    if docker-compose -f "$COMPOSE_FILE" ps -q | grep -q .; then
        log "Stopping existing services..."
        
        # Save current state for potential rollback
        local current_tags=$(get_current_image_tags)
        save_deployment_state "previous_tags=$current_tags"
        
        if docker-compose -f "$COMPOSE_FILE" down; then
            success "Existing services stopped"
            return 0
        else
            error "Failed to stop existing services"
            return 1
        fi
    else
        log "No existing services running"
        return 0
    fi
}

start_services_with_dependencies() {
    section "Starting Services with Dependency Ordering"
    
    # Load environment variables
    export $(grep -v '^#' "$ENV_FILE" | xargs)
    
    # Start services in dependency order
    local services=(
        "postgres"
        "redis"
        "backend"
        "celery-worker"
        "celery-beat"
        "discord-bot"
        "frontend"
        "nginx"
    )
    
    for service in "${services[@]}"; do
        log "Starting service: $service"
        
        if docker-compose -f "$COMPOSE_FILE" up -d "$service"; then
            success "Service $service started"
            
            # Wait a bit for service to initialize
            sleep 5
            
            # Check if service is running
            if docker-compose -f "$COMPOSE_FILE" ps "$service" | grep -q "Up"; then
                success "Service $service is running"
            else
                error "Service $service failed to start"
                return 1
            fi
        else
            error "Failed to start service: $service"
            return 1
        fi
    done
    
    success "All services started successfully"
    return 0
}

################################################################################
# Health Check Functions
################################################################################

wait_for_service_health() {
    local service=$1
    local timeout=$2
    local elapsed=0
    
    log "Waiting for $service to become healthy (timeout: ${timeout}s)..."
    
    while [ $elapsed -lt $timeout ]; do
        local health=$(docker inspect --format='{{.State.Health.Status}}' "$(docker-compose -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null)" 2>/dev/null || echo "unknown")
        
        if [ "$health" = "healthy" ]; then
            success "Service $service is healthy"
            return 0
        elif [ "$health" = "unhealthy" ]; then
            error "Service $service is unhealthy"
            return 1
        fi
        
        sleep $HEALTH_CHECK_INTERVAL
        elapsed=$((elapsed + HEALTH_CHECK_INTERVAL))
        echo -n "."
    done
    
    echo ""
    error "Service $service health check timed out after ${timeout}s"
    return 1
}

check_service_health() {
    section "Performing Health Checks"
    
    if [ "$SKIP_HEALTH" = true ]; then
        warning "Skipping health checks (--skip-health flag set)"
        return 0
    fi
    
    local errors=0
    
    # Check database health
    log "Checking PostgreSQL health..."
    if wait_for_service_health "postgres" 60; then
        success "PostgreSQL is healthy"
    else
        error "PostgreSQL health check failed"
        ((errors++))
    fi
    
    # Check Redis health
    log "Checking Redis health..."
    if wait_for_service_health "redis" 30; then
        success "Redis is healthy"
    else
        error "Redis health check failed"
        ((errors++))
    fi
    
    # Check backend health
    log "Checking backend health..."
    if wait_for_service_health "backend" 120; then
        success "Backend is healthy"
    else
        error "Backend health check failed"
        ((errors++))
    fi
    
    # Check frontend health
    log "Checking frontend health..."
    if wait_for_service_health "frontend" 30; then
        success "Frontend is healthy"
    else
        error "Frontend health check failed"
        ((errors++))
    fi
    
    # Check nginx health
    log "Checking nginx health..."
    if wait_for_service_health "nginx" 30; then
        success "Nginx is healthy"
    else
        error "Nginx health check failed"
        ((errors++))
    fi
    
    return $errors
}

test_api_endpoints() {
    section "Testing API Endpoints"
    
    local errors=0
    
    # Wait a bit for services to fully initialize
    sleep 10
    
    # Test backend health endpoint
    log "Testing backend health endpoint..."
    local backend_health=$(docker exec accountability-backend-prod curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
    
    if [ "$backend_health" = "200" ]; then
        success "Backend health endpoint responding (HTTP $backend_health)"
    else
        error "Backend health endpoint failed (HTTP $backend_health)"
        ((errors++))
    fi
    
    # Test nginx routing
    log "Testing nginx routing..."
    local nginx_health=$(docker exec accountability-nginx-prod curl -s -o /dev/null -w "%{http_code}" http://localhost/health 2>/dev/null || echo "000")
    
    if [ "$nginx_health" = "200" ]; then
        success "Nginx routing working (HTTP $nginx_health)"
    else
        error "Nginx routing failed (HTTP $nginx_health)"
        ((errors++))
    fi
    
    return $errors
}

################################################################################
# Rollback Functions
################################################################################

perform_rollback() {
    section "Performing Rollback"
    
    error "Deployment failed, initiating rollback..."
    
    # Stop current services
    log "Stopping failed deployment..."
    docker-compose -f "$COMPOSE_FILE" down
    
    # Load previous state
    local previous_state=$(load_deployment_state)
    
    if [ -z "$previous_state" ]; then
        error "No previous deployment state found"
        error "Manual intervention required"
        return 1
    fi
    
    log "Previous state: $previous_state"
    
    # Restore from backup if available
    log "Checking for recent backup..."
    if [ -f "$PROJECT_ROOT/scripts/restore-database.sh" ]; then
        local latest_backup=$(find "$BACKUP_DIR" -name "*.sql.gz" -o -name "*.sql.gz.enc" | sort -r | head -1)
        
        if [ -n "$latest_backup" ]; then
            warning "Latest backup found: $latest_backup"
            warning "To restore, run: bash scripts/restore-database.sh $latest_backup"
        fi
    fi
    
    error "Rollback requires manual intervention"
    error "Please review logs and restore from backup if needed"
    
    return 1
}

manual_rollback() {
    section "Manual Rollback Mode"
    
    log "Initiating manual rollback..."
    
    # Stop all services
    log "Stopping all services..."
    docker-compose -f "$COMPOSE_FILE" down
    
    # List available backups
    log "Available backups:"
    if [ -d "$BACKUP_DIR" ]; then
        find "$BACKUP_DIR" -name "*.sql.gz" -o -name "*.sql.gz.enc" | sort -r | head -10
    else
        warning "No backup directory found"
    fi
    
    echo ""
    warning "To complete rollback:"
    warning "1. Restore database from backup: bash scripts/restore-database.sh <backup-file>"
    warning "2. Checkout previous code version: git checkout <previous-commit>"
    warning "3. Rebuild images: docker-compose -f $COMPOSE_FILE build"
    warning "4. Start services: docker-compose -f $COMPOSE_FILE up -d"
    
    return 0
}

################################################################################
# Post-Deployment Functions
################################################################################

show_deployment_status() {
    section "Deployment Status"
    
    log "Service status:"
    docker-compose -f "$COMPOSE_FILE" ps
    
    echo ""
    log "Resource usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
    
    echo ""
    log "Recent logs:"
    docker-compose -f "$COMPOSE_FILE" logs --tail=20
}

show_deployment_summary() {
    section "Deployment Summary"
    
    success "Deployment completed successfully!"
    echo ""
    log "Services deployed:"
    log "  - PostgreSQL (database)"
    log "  - Redis (cache/queue)"
    log "  - Backend API (FastAPI)"
    log "  - Celery Worker (background tasks)"
    log "  - Celery Beat (scheduler)"
    log "  - Discord Bot"
    log "  - Frontend (React)"
    log "  - Nginx (reverse proxy)"
    echo ""
    log "Next steps:"
    log "  1. Configure DNS to point to this server"
    log "  2. Set up SSL certificates: bash nginx/setup-ssl-prod.sh"
    log "  3. Configure automated backups: bash scripts/setup-backup-cron.sh"
    log "  4. Monitor logs: docker-compose -f $COMPOSE_FILE logs -f"
    log "  5. Check health: curl http://localhost/health"
    echo ""
    log "Useful commands:"
    log "  - View logs: docker-compose -f $COMPOSE_FILE logs -f [service]"
    log "  - Restart service: docker-compose -f $COMPOSE_FILE restart [service]"
    log "  - Stop all: docker-compose -f $COMPOSE_FILE down"
    log "  - View status: docker-compose -f $COMPOSE_FILE ps"
}

################################################################################
# Main Deployment Flow
################################################################################

show_help() {
    cat << EOF
Production Deployment Script

Usage: ./deploy.sh [options]

Options:
  --skip-backup       Skip pre-deployment backup
  --skip-build        Skip Docker image building
  --skip-health       Skip health checks
  --force             Force deployment even with warnings
  --rollback          Rollback to previous deployment
  --help              Show this help message

Examples:
  ./deploy.sh                    # Full deployment with all checks
  ./deploy.sh --skip-backup      # Deploy without creating backup
  ./deploy.sh --rollback         # Rollback to previous deployment

EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-backup)
                SKIP_BACKUP=true
                shift
                ;;
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --skip-health)
                SKIP_HEALTH=true
                shift
                ;;
            --force)
                FORCE_DEPLOY=true
                shift
                ;;
            --rollback)
                ROLLBACK_MODE=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

main() {
    # Parse command line arguments
    parse_arguments "$@"
    
    # Handle rollback mode
    if [ "$ROLLBACK_MODE" = true ]; then
        manual_rollback
        exit $?
    fi
    
    # Start deployment
    section "Starting Production Deployment"
    log "Deployment started at $(date)"
    log "Environment file: $ENV_FILE"
    log "Compose file: $COMPOSE_FILE"
    echo ""
    
    # Pre-deployment checks
    if ! check_prerequisites; then
        error "Prerequisites check failed"
        exit 1
    fi
    
    if ! validate_environment; then
        if [ "$FORCE_DEPLOY" = true ]; then
            warning "Environment validation failed, but continuing due to --force flag"
        else
            error "Environment validation failed"
            error "Fix the errors or use --force to deploy anyway"
            exit 1
        fi
    fi
    
    if ! check_port_availability; then
        if [ "$FORCE_DEPLOY" = true ]; then
            warning "Port conflicts detected, but continuing due to --force flag"
        else
            error "Port conflicts detected"
            error "Stop conflicting services or use --force to deploy anyway"
            exit 1
        fi
    fi
    
    check_docker_resources
    
    # Create backup
    if ! create_pre_deployment_backup; then
        if [ "$FORCE_DEPLOY" = true ]; then
            warning "Backup failed, but continuing due to --force flag"
        else
            error "Backup failed"
            error "Fix the issue or use --skip-backup to deploy without backup"
            exit 1
        fi
    fi
    
    # Build images
    if ! build_docker_images; then
        error "Image build failed"
        exit 1
    fi
    
    # Stop existing services
    if ! stop_existing_services; then
        error "Failed to stop existing services"
        exit 1
    fi
    
    # Start services
    if ! start_services_with_dependencies; then
        error "Failed to start services"
        perform_rollback
        exit 1
    fi
    
    # Health checks
    if ! check_service_health; then
        error "Health checks failed"
        perform_rollback
        exit 1
    fi
    
    # Test endpoints
    if ! test_api_endpoints; then
        error "API endpoint tests failed"
        perform_rollback
        exit 1
    fi
    
    # Show status
    show_deployment_status
    
    # Show summary
    show_deployment_summary
    
    # Save successful deployment state
    local current_tags=$(get_current_image_tags)
    save_deployment_state "current_tags=$current_tags,timestamp=$(date +%s)"
    
    success "Deployment completed successfully at $(date)"
    exit 0
}

# Run main function
main "$@"
