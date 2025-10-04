# --- Makefile ---
PY=python3

.PHONY: nifi-up nifi-down nifi-restart nifi-logs qdrant-up qdrant-down qdrant-restart qdrant-logs qdrant-wait qdrant-reset


# -------- Environment ----------

setup:
	@echo ">> Creating venv and installing API requirements..."
	$(PY) -m venv .venv
	- . .venv/bin/activate && pip install -U pip && pip install -r api/requirements.txt || true
	- . .venv/Scripts/activate && pip install -U pip && pip install -r api/requirements.txt || true
	@echo ">> venv ready."

clean: down
	@echo ">> Cleaning venv and reports..."
	-rm -rf .venv reports/*.json reports/*.md


# -------- NiFi ----------
nifi-up:
	@echo ">> Starting NiFi..."
	docker compose up -d nifi
	@$(SLEEP_2)
	@echo "NiFi UI: http://localhost:8080"

nifi-down:
	@echo ">> Stopping NiFi..."
	docker compose stop nifi


nifi-logs:
	docker compose logs -f nifi



# -------- Qdrant ----------
qdrant-up:
	@echo ">> Starting Qdrant..."
	docker compose up -d qdrant
	@$(SLEEP_2)
	@$(MAKE) qdrant-wait

qdrant-down:
	@echo ">> Stopping Qdrant..."
	docker compose stop qdrant

qdrant-restart: qdrant-down qdrant-up

qdrant-logs:
	docker compose logs -f qdrant


qdrant-reset:
	@echo ">> WARNING: This will remove Qdrant data volume."
	docker compose down -v qdrant || true
	docker compose up -d qdrant
	@$(MAKE) qdrant-wait


# -------- API ----------
api-build:
	@echo ">> Building API image..."
	docker compose build api

api-up:
	@echo ">> Starting API..."
	docker compose up -d api
	@echo "API Docs: http://localhost:$(API_PORT)/docs"

api-down:
	@echo ">> Stopping API..."
	docker compose stop api

up: setup nifi-up qdrant-up api-up
down: clean nifi-down qdrant-down api-down