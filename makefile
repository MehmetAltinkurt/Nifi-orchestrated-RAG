# --- Makefile ---
.PHONY: nifi-up nifi-down nifi-restart nifi-logs qdrant-up qdrant-down qdrant-restart qdrant-logs qdrant-wait qdrant-reset api-build api-up api-down setup clean up down

SLEEP2 = powershell -Command "Start-Sleep -Seconds 2"
CURL_RDY = powershell -Command "try { iwr -UseBasicParsing http://localhost:6333/ready -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"

# -------- Environment ----------

setup:
	@echo ">> Creating venv and installing API requirements..."
	@if [ ! -x ".venv/Scripts/python.exe" ] && [ ! -x ".venv/bin/python" ]; then \
		echo ">> Creating venv..."; \
		python3 -m venv .venv || python -m venv .venv; \
	fi; \
	if [ -x ".venv/Scripts/python.exe" ]; then VENV_PY=".venv/Scripts/python.exe"; \
	elif [ -x ".venv/bin/python" ]; then VENV_PY=".venv/bin/python"; \
	else echo "!! venv python not found"; exit 1; fi; \
	echo ">> Using venv python: $$VENV_PY"; \
	"$$VENV_PY" -m pip install -U pip; \
	if [ -f "api/requirements.txt" ]; then "$$VENV_PY" -m pip install -r api/requirements.txt; fi; \
	echo ">> venv ready."

clean: down
	@echo ">> Cleaning venv and reports..."
	-rm -rf .venv reports/*.json reports/*.md


# -------- NiFi ----------
nifi-up:
	@echo ">> Starting NiFi..."
	docker compose up -d nifi
	@$(SLEEP2)
	@echo "NiFi UI: http://localhost:8443/nifi"

nifi-down:
	@echo ">> Stopping NiFi..."
	docker compose stop nifi


nifi-logs:
	docker compose logs -f nifi



# -------- Qdrant ----------
qdrant-up:
	@echo ">> Starting Qdrant..."
	docker compose up -d qdrant

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


# -------- API ----------
api-build:
	@echo ">> Building API image..."
	docker compose build api

api-up:
	@echo ">> Starting API..."
	docker compose up -d api
	@echo "API Docs: http://localhost:8000/docs"

api-down:
	@echo ">> Stopping API..."
	docker compose stop api

up: setup nifi-up qdrant-up api-build api-up
down: clean nifi-down qdrant-down api-down