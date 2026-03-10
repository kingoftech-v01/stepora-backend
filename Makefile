.PHONY: help build up down restart logs shell migrate makemigrations test coverage clean

# Default target
help:
	@echo "Stepora Backend - Available commands:"
	@echo "  make build          - Build Docker images"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View logs (all services)"
	@echo "  make logs-web       - View web service logs"
	@echo "  make logs-celery    - View Celery worker logs"
	@echo "  make shell          - Open Django shell"
	@echo "  make bash           - Open bash shell in web container"
	@echo "  make migrate        - Run database migrations"
	@echo "  make makemigrations - Create new migrations"
	@echo "  make createsuperuser - Create Django superuser"
	@echo "  make test           - Run tests"
	@echo "  make test-cov       - Run tests with coverage"
	@echo "  make coverage       - Generate coverage report"
	@echo "  make lint           - Run linters (flake8, black)"
	@echo "  make format         - Format code with black"
	@echo "  make clean          - Remove containers and volumes"
	@echo "  make reset-db       - Reset database (WARNING: deletes all data)"

# Build Docker images
build:
	docker-compose build

# Start services
up:
	docker-compose up -d
	@echo "Services started. Access API at http://localhost:8000"
	@echo "Access Flower (Celery monitoring) at http://localhost:5555"

# Stop services
down:
	docker-compose down

# Restart services
restart:
	docker-compose restart

# View logs
logs:
	docker-compose logs -f

logs-web:
	docker-compose logs -f web

logs-celery:
	docker-compose logs -f celery

logs-beat:
	docker-compose logs -f celery-beat

# Django shell
shell:
	docker-compose exec web python manage.py shell

# Bash shell
bash:
	docker-compose exec web bash

# Database migrations
migrate:
	docker-compose exec web python manage.py migrate

makemigrations:
	docker-compose exec web python manage.py makemigrations

# Create superuser
createsuperuser:
	docker-compose exec web python manage.py createsuperuser

# Testing
test:
	docker-compose exec web pytest

test-cov:
	docker-compose exec web pytest --cov --cov-report=html

test-unit:
	docker-compose exec web pytest -m unit

test-integration:
	docker-compose exec web pytest -m integration

coverage:
	docker-compose exec web pytest --cov --cov-report=html --cov-report=term

# Linting and formatting
lint:
	docker-compose exec web flake8 apps core integrations
	docker-compose exec web black --check apps core integrations

format:
	docker-compose exec web black apps core integrations
	docker-compose exec web isort apps core integrations

# Database operations
reset-db:
	docker-compose down -v
	docker-compose up -d db
	@echo "Waiting for database..."
	@sleep 5
	docker-compose exec db psql -U stepora -d stepora -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	docker-compose up -d
	@echo "Waiting for services..."
	@sleep 5
	docker-compose exec web python manage.py migrate
	@echo "Database reset complete"

# Backup database
backup-db:
	@echo "Creating database backup..."
	docker-compose exec db pg_dump -U stepora stepora > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup created"

# Restore database
restore-db:
	@echo "Restoring database from backup..."
	@read -p "Enter backup file name: " backup_file; \
	docker-compose exec -T db psql -U stepora stepora < $$backup_file
	@echo "Database restored"

# Clean up
clean:
	docker-compose down -v --remove-orphans
	docker system prune -f

# Production commands
build-prod:
	docker build -t stepora-api:latest -f Dockerfile .

up-prod:
	docker-compose -f docker-compose.prod.yml up -d

down-prod:
	docker-compose -f docker-compose.prod.yml down

logs-prod:
	docker-compose -f docker-compose.prod.yml logs -f

# Check services health
health:
	@curl -f http://localhost:8000/health/ || echo "Web service not healthy"
	@curl -f http://localhost:8000/health/readiness/ || echo "Readiness check failed"

# Install pre-commit hooks
install-hooks:
	pre-commit install

# Run pre-commit on all files
pre-commit:
	pre-commit run --all-files

# Generate requirements
freeze:
	docker-compose exec web pip freeze > requirements/development.txt
