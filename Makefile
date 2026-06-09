.PHONY: help build up down logs shell clean install cpu gpu

SERVICE_NAME=audio-transcribe-api
COMPOSE_FILE=docker-compose.yml

help: ## Show help
	@echo "Available targets:"
	@echo "  make build   — build image"
	@echo "  make up      — start service"
	@echo "  make down    — stop service"
	@echo "  make logs    — tail logs"
	@echo "  make gpu     — build/run GPU variant"
	@echo "  make cpu     — build/run CPU variant"

.PHONY: cpu
cpu: COMPOSE_FILE=docker-compose.cpu.yml
cpu: build up

.PHONY: gpu
gpu: COMPOSE_FILE=docker-compose.gpu.yml
gpu: build up

build: ## Build image
	docker compose -f $(COMPOSE_FILE) build

up: ## Start service
	docker compose -f $(COMPOSE_FILE) up -d

down: ## Stop service
	docker compose -f $(COMPOSE_FILE) down

logs: ## Tail logs
	docker compose -f $(COMPOSE_FILE) logs -f

shell: ## Open shell in container
	docker compose -f $(COMPOSE_FILE) exec app bash

clean: ## Remove image + volumes
	docker compose -f $(COMPOSE_FILE) down -v
	docker image rm $(SERVICE_NAME)_app || true
