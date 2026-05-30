#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  AI SRE Copilot — Start Script
#  Usage: ./scripts/start.sh
#
#  Kya karta hai:
#  1. Docker infra start karta hai
#  2. Services healthy hone ka wait karta hai
#  3. Python venv setup karta hai
#  4. FastAPI app start karta hai
# ─────────────────────────────────────────────────────────────────

set -e  # Koi bhi error hone pe script band ho

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

# Script ki location se relative paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# ── Step 1: .env check ────────────────────────
if [ ! -f ".env" ]; then
    log_warn ".env file nahi mili, .env.example se copy kar raha hoon..."
    cp .env.example .env
    log_info ".env file bani. Please check kar lo values: $PROJECT_ROOT/.env"
fi

# ── Step 2: Docker infra start ────────────────
log_info "Docker infra start kar raha hoon..."
cd infra
docker compose up -d

log_info "Services healthy hone ka wait kar raha hoon..."

# Kafka ready hone ka wait
log_info "Kafka ka wait..."
until docker compose exec -T kafka kafka-topics --bootstrap-server localhost:29092 --list &>/dev/null; do
    echo -n "."
    sleep 3
done
echo ""
log_info "Kafka ready!"

# PostgreSQL ready hone ka wait
log_info "PostgreSQL ka wait..."
until docker compose exec -T postgres pg_isready -U sre_user -d sre_copilot &>/dev/null; do
    echo -n "."
    sleep 2
done
echo ""
log_info "PostgreSQL ready!"

# Redis ready hone ka wait
log_info "Redis ka wait..."
until docker compose exec -T redis redis-cli ping | grep -q PONG; do
    echo -n "."
    sleep 2
done
echo ""
log_info "Redis ready!"

cd "$PROJECT_ROOT"

# ── Step 3: Python venv ───────────────────────
if [ ! -d "venv" ]; then
    log_info "Python virtual environment bana raha hoon..."
    python3 -m venv venv
fi

log_info "Dependencies install kar raha hoon..."
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# ── Step 4: Runbooks ingest (agar nahi kiya) ──
if [ ! -f ".runbooks_ingested" ]; then
    log_info "Runbooks ko Qdrant mein index kar raha hoon..."
    python scripts/ingest_runbooks.py && touch .runbooks_ingested
fi

# ── Step 5: FastAPI start ─────────────────────
log_info "FastAPI app start ho raha hai..."
log_info "Docs: http://localhost:8000/docs"
log_info "Grafana: http://localhost:3000 (admin / admin123)"
log_info "Prometheus: http://localhost:9090"
log_info "Qdrant: http://localhost:6333/dashboard"

uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info
