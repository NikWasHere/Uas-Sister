# Makefile untuk Windows PowerShell
# Gunakan: make <target>

.PHONY: help build up down restart logs test clean

help: ## Show this help message
	@echo "Available commands:"
	@echo "  make build       - Build all Docker images"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services (keep data)"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View all logs"
	@echo "  make test        - Run tests"
	@echo "  make clean       - Remove all containers and volumes"
	@echo "  make stats       - Show aggregator stats"
	@echo "  make health      - Check aggregator health"

build: ## Build Docker images
	docker compose build

up: ## Start all services
	docker compose up -d

up-build: ## Build and start all services
	docker compose up --build -d

down: ## Stop all services (keep volumes)
	docker compose down

down-clean: ## Stop services and remove volumes
	docker compose down -v

restart: ## Restart all services
	docker compose restart

restart-aggregator: ## Restart only aggregator
	docker compose restart aggregator

logs: ## View all logs
	docker compose logs -f

logs-aggregator: ## View aggregator logs
	docker compose logs -f aggregator

logs-publisher: ## View publisher logs
	docker compose logs -f publisher

test: ## Run pytest tests
	pip install -r tests/requirements.txt
	pytest tests/test_aggregator.py -v

test-coverage: ## Run tests with coverage
	pip install -r tests/requirements.txt
	pytest tests/test_aggregator.ps1 --cov=aggregator --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

load-test: ## Run K6 load test
	k6 run tests/load_test.js

stats: ## Show aggregator statistics
	curl http://localhost:8080/stats

health: ## Check aggregator health
	curl http://localhost:8080/health

events: ## Show recent events
	curl http://localhost:8080/events?limit=10

ps: ## Show running containers
	docker compose ps

clean: ## Remove containers, volumes, and images
	docker compose down -v --rmi all
	docker system prune -f

clean-volumes: ## Remove only volumes
	docker compose down -v

db-shell: ## Open PostgreSQL shell
	docker compose exec storage psql -U loguser -d logdb

redis-shell: ## Open Redis shell
	docker compose exec broker redis-cli

shell-aggregator: ## Open shell in aggregator container
	docker compose exec aggregator sh

install-deps: ## Install local development dependencies
	pip install -r aggregator/requirements.txt
	pip install -r publisher/requirements.txt
	pip install -r tests/requirements.txt

verify: ## Verify installation
	@echo "Checking Docker..."
	docker --version
	@echo "Checking Docker Compose..."
	docker compose version
	@echo "Checking Python..."
	python --version
	@echo "Checking curl..."
	curl --version
	@echo "All prerequisites installed!"

demo: ## Quick demo sequence
	@echo "Starting services..."
	docker compose up -d
	@echo "Waiting for services to be ready..."
	timeout /t 30
	@echo "Checking health..."
	curl http://localhost:8080/health
	@echo "Showing stats..."
	curl http://localhost:8080/stats
	@echo "Demo complete!"
