#!/bin/bash
#
# Health check script for StudyMate Bot
# Usage: ./scripts/health_check.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_service() {
    SERVICE=$1
    echo -n "Checking $SERVICE... "

    if docker-compose ps $SERVICE | grep -q "Up"; then
        echo -e "${GREEN}✓ Running${NC}"
        return 0
    else
        echo -e "${RED}✗ Not running${NC}"
        return 1
    fi
}

check_postgres() {
    echo -n "Checking PostgreSQL connection... "

    if docker-compose exec -T postgres pg_isready -U studymate > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Connected${NC}"

        # Check database size
        DB_SIZE=$(docker-compose exec -T postgres psql -U studymate -d studymate -t -c "SELECT pg_size_pretty(pg_database_size('studymate'));" | tr -d ' ')
        echo "  Database size: $DB_SIZE"
        return 0
    else
        echo -e "${RED}✗ Connection failed${NC}"
        return 1
    fi
}

check_redis() {
    echo -n "Checking Redis connection... "

    if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
        echo -e "${GREEN}✓ Connected${NC}"

        # Check Redis memory usage
        REDIS_MEM=$(docker-compose exec -T redis redis-cli INFO memory | grep "used_memory_human" | cut -d':' -f2 | tr -d '\r')
        echo "  Memory usage: $REDIS_MEM"

        # Check number of keys
        REDIS_KEYS=$(docker-compose exec -T redis redis-cli DBSIZE | tr -d '\r')
        echo "  Keys: $REDIS_KEYS"
        return 0
    else
        echo -e "${RED}✗ Connection failed${NC}"
        return 1
    fi
}

check_bot_logs() {
    echo -n "Checking bot logs for errors... "

    # Check last 50 lines for errors
    ERROR_COUNT=$(docker-compose logs --tail=50 bot 2>&1 | grep -i "error" | wc -l)

    if [ $ERROR_COUNT -eq 0 ]; then
        echo -e "${GREEN}✓ No recent errors${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Found $ERROR_COUNT error(s) in recent logs${NC}"
        return 1
    fi
}

check_disk_space() {
    echo -n "Checking disk space... "

    USAGE=$(df -h "$PROJECT_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')

    if [ $USAGE -lt 80 ]; then
        echo -e "${GREEN}✓ ${USAGE}% used${NC}"
        return 0
    elif [ $USAGE -lt 90 ]; then
        echo -e "${YELLOW}⚠ ${USAGE}% used (warning)${NC}"
        return 1
    else
        echo -e "${RED}✗ ${USAGE}% used (critical)${NC}"
        return 1
    fi
}

echo "========================================="
echo "StudyMate Bot - Health Check"
echo "========================================="
echo ""

FAILED=0

# Check services
check_service "postgres" || FAILED=$((FAILED + 1))
check_service "redis" || FAILED=$((FAILED + 1))
check_service "bot" || FAILED=$((FAILED + 1))

echo ""

# Check connections
check_postgres || FAILED=$((FAILED + 1))
check_redis || FAILED=$((FAILED + 1))

echo ""

# Check bot health
check_bot_logs || FAILED=$((FAILED + 1))
check_disk_space || FAILED=$((FAILED + 1))

echo ""
echo "========================================="

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All checks passed!${NC}"
    exit 0
else
    echo -e "${RED}$FAILED check(s) failed!${NC}"
    exit 1
fi
