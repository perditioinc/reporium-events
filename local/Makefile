# Local OSS substrate for reporium-events.
# All targets are additive and local-only: nothing touches production/cloud.

COMPOSE := docker compose -f docker-compose.yml

.PHONY: help up down seed smoke logs clean

help:
	@echo "reporium-events local OSS substrate"
	@echo ""
	@echo "  make up     - start Pub/Sub + Firestore emulators (waits for health)"
	@echo "  make seed   - create the reporium-events topic + smoke subscription"
	@echo "  make smoke  - run publish->subscribe delivery smoke test (PASS/FAIL)"
	@echo "  make down   - stop and remove emulators + volumes"
	@echo "  make logs   - tail emulator logs"
	@echo "  make clean  - down + prune dangling smoke containers"

up:
	$(COMPOSE) up -d --wait

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f

# seed is folded into the smoke (topic + subscription are created idempotently),
# but exposed separately for manual use.
seed:
	@bash scripts/run-smoke.sh || true

smoke:
	@bash scripts/run-smoke.sh

clean: down
	-docker ps -aq --filter ancestor=python:3.12-slim | xargs -r docker rm -f
