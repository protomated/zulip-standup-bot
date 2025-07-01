# Zulip Standup Bot - Development Makefile

.PHONY: help install test lint format clean docker-build docker-run docs

# Default target
help:
	@echo "Zulip Standup Bot - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  install     Install dependencies and setup development environment"
	@echo "  test        Run test suite"
	@echo "  lint        Run linting (flake8, mypy)"
	@echo "  format      Format code (black, isort)"
	@echo "  clean       Clean up generated files"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build    Build Docker image"
	@echo "  docker-run      Run bot in Docker container"
	@echo "  docker-dev      Run development environment with Docker Compose"
	@echo "  docker-prod     Run production environment with Docker Compose"
	@echo ""
	@echo "Deployment:"
	@echo "  deploy-staging  Deploy to staging environment"
	@echo "  deploy-prod     Deploy to production environment"
	@echo ""
	@echo "Utilities:"
	@echo "  docs        Generate documentation"
	@echo "  backup      Backup database"
	@echo "  restore     Restore database from backup"

# Development tasks
install:
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	./venv/bin/pip install -e .
	@echo "Development environment ready!"
	@echo "Activate with: source venv/bin/activate"

test:
	python -m pytest zulip_bots/bots/standup/ \
		--cov=zulip_bots.bots.standup \
		--cov-report=html \
		--cov-report=term-missing \
		-v

test-watch:
	python -m pytest zulip_bots/bots/standup/ \
		--cov=zulip_bots.bots.standup \
		-f

lint:
	flake8 zulip_bots/bots/standup
	mypy zulip_bots/bots/standup
	black --check zulip_bots/bots/standup
	isort --check-only zulip_bots/bots/standup

format:
	black zulip_bots/bots/standup
	isort zulip_bots/bots/standup
	@echo "Code formatted successfully!"

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/

# Docker tasks
docker-build:
	docker build -t zulip-standup-bot:latest .

docker-run: docker-build
	docker run --rm -it \
		--env-file .env \
		-p 5002:5002 \
		-v $(PWD)/data:/app/data \
		zulip-standup-bot:latest

docker-dev:
	docker-compose -f docker-compose.dev.yml up --build

docker-prod:
	docker-compose up --build -d

docker-logs:
	docker-compose logs -f

docker-stop:
	docker-compose down

# Development database tasks
db-init:
	python -c "from zulip_bots.bots.standup import database; database.init_db()"

db-migrate:
	python -c "from zulip_bots.bots.standup import database; database.migrate_database()"

db-reset:
	rm -f data/standup.db
	$(MAKE) db-init

# Backup and restore
backup:
	@mkdir -p backups
	@if [ -f "data/standup.db" ]; then \
		cp data/standup.db backups/standup_$(shell date +%Y%m%d_%H%M%S).db; \
		echo "SQLite backup created in backups/"; \
	fi
	@if [ -n "$$DATABASE_URL" ] && [[ "$$DATABASE_URL" == postgresql* ]]; then \
		pg_dump $$DATABASE_URL > backups/standup_$(shell date +%Y%m%d_%H%M%S).sql; \
		echo "PostgreSQL backup created in backups/"; \
	fi

restore:
	@echo "Available backups:"
	@ls -la backups/
	@echo "To restore, run: cp backups/BACKUP_FILE data/standup.db"

# Documentation
docs:
	@echo "Generating documentation..."
	@mkdir -p docs
	@echo "Documentation will be available in docs/ directory"

# Security checks
security:
	safety check
	bandit -r zulip_bots/bots/standup

# Release tasks
version-bump:
	@echo "Current version: $(shell python setup.py --version)"
	@read -p "Enter new version: " version; \
	sed -i.bak "s/version=\".*\"/version=\"$$version\"/" setup.py
	@echo "Version updated. Don't forget to commit and tag!"

release-check:
	@echo "Pre-release checklist:"
	@echo "□ All tests passing"
	@echo "□ Version bumped"
	@echo "□ CHANGELOG.md updated"
	@echo "□ Documentation updated"
	@echo "□ Docker image builds successfully"
	$(MAKE) test
	$(MAKE) lint
	$(MAKE) docker-build

# Environment setup
setup-dev:
	cp .env.example .env
	@echo "Please edit .env with your configuration"
	@echo "Then run: make install"

setup-prod:
	@echo "Production setup checklist:"
	@echo "□ Configure environment variables"
	@echo "□ Set up database"
	@echo "□ Configure SSL certificates"
	@echo "□ Set up monitoring"
	@echo "□ Configure backups"

# Monitoring and health checks
health-check:
	@curl -f http://localhost:5002/health || echo "Health check failed"

logs:
	@if [ -f "logs/standup.log" ]; then \
		tail -f logs/standup.log; \
	else \
		echo "No log file found. Run 'make docker-logs' for Docker logs."; \
	fi

# Development utilities
run-local:
	python run_standup_bot.py

debug:
	python -c "from zulip_bots.bots.standup.standup import StandupBotHandler; print('Debug info here')"

shell:
	python -i -c "from zulip_bots.bots.standup import *"

# Quick development workflow
dev: format lint test docker-build
	@echo "Development workflow complete!"

# Production deployment helpers
deploy-check:
	@echo "Deployment checklist:"
	@echo "□ Environment variables configured"
	@echo "□ Database accessible"
	@echo "□ SSL certificates valid"
	@echo "□ Monitoring configured"
	@echo "□ Backup strategy in place"

# Performance testing
perf-test:
	@echo "Running performance tests..."
	@echo "This would run load tests if implemented"

# Environment variables check
env-check:
	@python -c "
import os
required = ['ZULIP_EMAIL', 'ZULIP_API_KEY', 'ZULIP_SITE']
missing = [var for var in required if not os.getenv(var)]
if missing:
    print('❌ Missing required environment variables:', ', '.join(missing))
    exit(1)
else:
    print('✅ All required environment variables are set')
"
