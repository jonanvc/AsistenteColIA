# Makefile for Proyecto Final IA
# Provides convenient commands for development and deployment

.PHONY: help build up down logs migrate seed run-scrape run-scrape-all test lint clean

# Default target
help:
	@echo "Proyecto Final IA - Available commands:"
	@echo ""
	@echo "  make build          - Build all Docker images"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make logs           - View logs from all services"
	@echo "  make migrate        - Run database migrations"
	@echo "  make seed           - Load sample data"
	@echo "  make run-scrape ID=1 - Run scraping for organization ID"
	@echo "  make run-scrape-all - Run scraping for all organizations"
	@echo "  make test           - Run backend tests"
	@echo "  make lint           - Run linting"
	@echo "  make clean          - Remove all containers and volumes"
	@echo ""

# Build Docker images
build:
	cd infra && docker-compose build

# Start all services
up:
	cd infra && docker-compose up -d --build
	@echo ""
	@echo "Services started!"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

# Stop all services
down:
	cd infra && docker-compose down

# View logs
logs:
	cd infra && docker-compose logs -f

# View backend logs
logs-backend:
	docker logs -f proyecto_ia_backend

# View worker logs
logs-worker:
	docker logs -f proyecto_ia_worker

# View frontend logs
logs-frontend:
	docker logs -f proyecto_ia_frontend

# Run database migrations
migrate:
	docker exec proyecto_ia_backend alembic upgrade head

# Create new migration
migration:
	@read -p "Migration message: " msg; \
	docker exec proyecto_ia_backend alembic revision --autogenerate -m "$$msg"

# Initialize database (create tables without Alembic)
init-db:
	docker exec proyecto_ia_backend python -c "import asyncio; from app.db.base import init_db; asyncio.run(init_db())"

# Load seed data
seed:
	docker exec proyecto_ia_backend python scripts/seed.py

# Run scraping for one organization
run-scrape:
ifndef ID
	$(error ID is required. Usage: make run-scrape ID=1)
endif
	docker exec proyecto_ia_backend python -m app.services.scraper $(ID)

# Run scraping for all organizations
run-scrape-all:
	docker exec proyecto_ia_backend python -m app.services.scraper --all

# Run backend tests
test:
	docker exec proyecto_ia_backend pytest -v

# Run tests with coverage
test-cov:
	docker exec proyecto_ia_backend pytest --cov=app --cov-report=html

# Run linting
lint:
	docker exec proyecto_ia_backend flake8 app/
	docker exec proyecto_ia_backend black --check app/

# Format code
format:
	docker exec proyecto_ia_backend black app/

# Clean up everything
clean:
	cd infra && docker-compose down -v --rmi local
	docker system prune -f

# Restart all services
restart: down up

# Restart backend only
restart-backend:
	docker restart proyecto_ia_backend

# Restart worker only
restart-worker:
	docker restart proyecto_ia_worker

# Enter backend shell
shell-backend:
	docker exec -it proyecto_ia_backend bash

# Enter worker shell
shell-worker:
	docker exec -it proyecto_ia_worker bash

# Enter database shell
shell-db:
	docker exec -it proyecto_ia_db psql -U postgres -d proyecto_ia

# Check service health
health:
	@echo "Checking services..."
	@curl -s http://localhost:8000/health | python -m json.tool || echo "Backend: DOWN"
	@docker exec proyecto_ia_db pg_isready -U postgres && echo "Database: UP" || echo "Database: DOWN"
	@docker exec proyecto_ia_redis redis-cli ping && echo "Redis: UP" || echo "Redis: DOWN"

# Install frontend dependencies locally
install-frontend:
	cd frontend && npm install

# Run frontend locally (without Docker)
dev-frontend:
	cd frontend && npm run dev

# Install backend dependencies locally
install-backend:
	cd backend && pip install -r requirements.txt

# Run backend locally (without Docker)
dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
