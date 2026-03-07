.PHONY: bootstrap dev up down test lint typecheck

bootstrap:
	python -m pip install -e ".[dev]"
	cd apps/ops-console && npm install

dev:
	docker compose up --build

up:
	docker compose up -d --build

down:
	docker compose down -v

test:
	pytest

lint:
	ruff check .

typecheck:
	mypy apps services packages
