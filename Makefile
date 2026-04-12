.PHONY: dev build up down logs fetch index search shell

# ── Local development ─────────────────────────────────────────────────────────

dev:
	uv run uvicorn app.main:app --reload --port 8000

# ── Docker ────────────────────────────────────────────────────────────────────

build:
	docker compose build

up:
	docker compose --env-file .env up -d

down:
	docker compose down

logs:
	docker compose logs -f app

shell:
	docker compose exec app bash

# ── Search (local) ────────────────────────────────────────────────────────────

search:
	@test -n "$(IMAGE)" || (echo "Usage: make search IMAGE=path/to/image.jpg"; exit 1)
	uv run python scripts/search.py $(IMAGE)
