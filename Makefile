.PHONY: help db.up db.down db.migrate backend.install backend.dev frontend.install frontend.dev dev test

# Prefer `docker compose` (v2 plugin); fall back to the standalone `docker-compose` binary.
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

help:
	@echo "Targets:"
	@echo "  db.up            - start Postgres via docker compose"
	@echo "  db.down          - stop Postgres"
	@echo "  db.migrate       - run Alembic migrations"
	@echo "  backend.install  - create venv and install backend deps"
	@echo "  backend.dev      - run FastAPI with autoreload"
	@echo "  frontend.install - install frontend deps"
	@echo "  frontend.dev     - run Vite dev server"
	@echo "  dev              - run db + backend + frontend (hint)"
	@echo "  test             - run backend pytest"

db.up:
	$(COMPOSE) up -d db

db.down:
	$(COMPOSE) down

# Homebrew-native Postgres alternative (no Docker needed).
# Creates role `docs` + database `docs` matching .env.example, then starts the service.
db.local:
	brew services start postgresql@16
	@echo "waiting for Postgres to accept connections…"
	@until /opt/homebrew/opt/postgresql@16/bin/pg_isready -h localhost -p 5432 >/dev/null 2>&1; do sleep 0.3; done
	@/opt/homebrew/opt/postgresql@16/bin/psql -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='docs'" | grep -q 1 \
		|| /opt/homebrew/opt/postgresql@16/bin/psql -d postgres -c "CREATE ROLE docs WITH LOGIN PASSWORD 'docs' CREATEDB"
	@/opt/homebrew/opt/postgresql@16/bin/psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='docs'" | grep -q 1 \
		|| /opt/homebrew/opt/postgresql@16/bin/createdb -O docs docs
	@echo "ok. Postgres 16 is running at localhost:5432 (user=docs, db=docs)."

db.local.down:
	brew services stop postgresql@16

db.migrate:
	cd backend && . .venv/bin/activate && alembic upgrade head

backend.install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt

backend.dev:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend.install:
	cd frontend && npm install

frontend.dev:
	cd frontend && npm run dev

dev:
	@echo "Run in three terminals:"
	@echo "  1) make db.up"
	@echo "  2) make backend.dev"
	@echo "  3) make frontend.dev"

test:
	cd backend && . .venv/bin/activate && pytest -q
