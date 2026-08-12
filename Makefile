.PHONY: install lint typecheck test up down migrate revision fmt

install:
	pip install -e ".[dev]"
	cd apps/web && npm install

lint:
	ruff check .
	cd apps/web && npm run lint

fmt:
	ruff format .
	cd apps/web && npm run format

typecheck:
	mypy marketedge apps/api
	cd apps/web && npm run typecheck

test:
	pytest

up:
	docker compose up --build

down:
	docker compose down

migrate:
	alembic -c marketedge/storage/migrations/alembic.ini upgrade head

revision:
	alembic -c marketedge/storage/migrations/alembic.ini revision --autogenerate -m "$(m)"
