.PHONY: help build up down logs shell clean install cpu gpu

SERVICE_NAME=audio-transcribe-api
COMPOSE_FILE=docker-compose.yml

help: ## Show help
	@echo "Available targets:"
	@echo "  make build   — build image"
	@echo "  make up      — start service"
	@echo "  make down    — stop service"
	@echo "  make logs    — tail logs"
	@echo "  make gpu     — build GPU variant"
	@echo "  make cpu     — build CPU variant"

cpu: COMPOSE_FILE=docker-compose.cpu.yml
cpu: build up

gpu: COMPOSE_FILE=docker-compose.gpu.yml
gpu: build up

build: ## Build image
	docker compose -f $(COMPOSE_FILE) -p $(SERVICE_NAME) build --pull

up: ## Start service
	docker compose -f $(COMPOSE_FILE) -p $(SERVICE_NAME) up -d

down: ## Stop service
	docker compose -f $(COMPOSE_FILE) -p $(SERVICE_NAME) down

logs: ## Tail logs
	docker compose -f $(COMPOSE_FILE) -p $(SERVICE_NAME) logs -f

shell: ## Open shell in container
	docker compose -f $(COMPOSE_FILE) -p $(SERVICE_NAME) exec app bash

clean: ## Remove image + volumes
	docker compose -f $(COMPOSE_FILE) -p $(SERVICE_NAME) down -v
	docker image rm $(SERVICE_NAME)-app || true
