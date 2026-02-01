.PHONY: help start stop restart logs build backup restore health migrate shell test clean install

help:
	@echo "StudyMate Bot - Available Commands"
	@echo "==================================="
	@echo ""
	@echo "Development:"
	@echo "  make install     - Install dependencies"
	@echo "  make migrate     - Run database migrations"
	@echo "  make shell       - Open Django shell"
	@echo "  make test        - Run tests (if available)"
	@echo ""
	@echo "Docker Operations:"
	@echo "  make build       - Build Docker images"
	@echo "  make start       - Start all services"
	@echo "  make stop        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View bot logs"
	@echo ""
	@echo "Maintenance:"
	@echo "  make backup      - Backup database"
	@echo "  make restore     - Restore from latest backup"
	@echo "  make health      - Check services health"
	@echo "  make clean       - Clean up containers and volumes"
	@echo ""

# Development
install:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt
	@echo "✓ Dependencies installed"
	@echo "Run: source .venv/bin/activate (Linux/Mac) or .venv\\Scripts\\activate (Windows)"

migrate:
	python manage.py migrate
	@echo "✓ Migrations applied"

shell:
	python manage.py shell

test:
	python manage.py test
	@echo "✓ Tests completed"

# Docker operations
build:
	docker-compose build
	@echo "✓ Images built"

start:
	docker-compose up -d
	@echo "✓ Services started"
	@echo "Check logs: make logs"

stop:
	docker-compose down
	@echo "✓ Services stopped"

restart:
	docker-compose restart
	@echo "✓ Services restarted"

logs:
	docker-compose logs -f bot

# Maintenance
backup:
	@chmod +x scripts/backup.sh
	./scripts/backup.sh
	@echo "✓ Backup completed"

restore:
	@chmod +x scripts/restore.sh
	./scripts/restore.sh
	@echo "✓ Restore completed"

health:
	@chmod +x scripts/health_check.sh
	./scripts/health_check.sh

clean:
	docker-compose down -v
	rm -rf logs/*.log
	@echo "✓ Cleaned up"

# Production
deploy-systemd:
	@echo "Deploying systemd service..."
	sudo cp scripts/studymate-bot.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable studymate-bot
	@echo "✓ Systemd service installed"
	@echo "Start with: sudo systemctl start studymate-bot"

status:
	docker-compose ps

ps:
	docker-compose ps
