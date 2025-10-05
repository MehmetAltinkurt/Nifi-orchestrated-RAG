# --- Makefile ---
PY=python

.PHONY: nifi-up nifi-down nifi-restart nifi-logs qdrant-up qdrant-down qdrant-restart qdrant-logs qdrant-wait qdrant-reset api-build api-up api-down setup clean up down

SLEEP2 = powershell -Command "Start-Sleep -Seconds 2"
CURL_RDY = powershell -Command "try { iwr -UseBasicParsing http://localhost:6333/ready -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"

# -------- Environment ----------

setup:
	@echo ">> Creating venv and installing API requirements..."
	# ---- Windows
	- .venv/Scripts/python.exe -m pip --version >NUL 2>&1 || true
	- PY -3 -m venv .venv || python -m venv .venv
	- .venv/Scripts/python.exe -m pip install -U pip || true
	- .venv/Scripts/python.exe -m pip install -r api/requirements.txt || true
	# ---- macOS/Linux:
	- python3 -m venv .venv || true
	- . .venv/bin/activate && pip install -U pip && pip install -r api/requirements.txt || true
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
	@echo ">> Checking Qdrant health..."
	# Windows:
	- - powershell -Command "$$ErrorActionPreference='SilentlyContinue'; for($$i=0; $$i -lt 30; $$i++){ try { $$r = Invoke-WebRequest -UseBasicParsing http://localhost:$(QDRANT_PORT)/ready -TimeoutSec 2; if ($$r.StatusCode -eq 200) { Write-Host 'Qdrant is ready.'; exit 0 } } catch { } Start-Sleep -Seconds 2 } exit 1" || true
	# macOS/Linux:
	- sh -c 'for i in $$(seq 1 15); do curl -fsS http://localhost:6333/ready >/dev/null 2>&1 && { echo Qdrant is ready.; exit 0; }; echo waiting... $$i; sleep 2; done; exit 1' || true


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