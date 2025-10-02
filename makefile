# --- Makefile ---
PY=python3

.PHONY: nifi-up nifi-down nifi-restart nifi-logs qdrant-up qdrant-down qdrant-restart qdrant-logs qdrant-wait qdrant-reset

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


qdrant-wait:
	@echo ">> Checking Qdrant health on :$(QDRANT_PORT)..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		curl -fsS http://localhost:$(QDRANT_PORT)/ready >/dev/null 2>&1 && { echo "Qdrant is ready."; exit 0; }; \
		echo "waiting... ($$i)"; \
		$(SLEEP_2); \
	done; \
	echo "Qdrant did not become ready in time." && exit 1


qdrant-reset:
	@echo ">> WARNING: This will remove Qdrant data volume."
	docker compose down -v qdrant || true
	docker compose up -d qdrant
	@$(MAKE) qdrant-wait



down: nifi-down qdrant-down