# OpenSRE — Local Development
#
# Run 'make help' to see all available targets.

.PHONY: help dev stop logs logs-agent logs-config logs-web status clean db-shell

.DEFAULT_GOAL := help

# ═══════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════

CONFIG_PORT      := 8081
AGENT_PORT       := 8001
WEB_UI_PORT      := 3002

# ═══════════════════════════════════════════════════════════════════════
# Help
# ═══════════════════════════════════════════════════════════════════════

help:
	@echo ""
	@echo "OpenSRE — AI SRE Platform"
	@echo "═══════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Local Development:"
	@echo "  make dev          Start all services (postgres, config, litellm, agent, web-ui)"
	@echo "  make stop         Stop all services"
	@echo "  make logs         Follow all service logs"
	@echo "  make logs-agent   Follow sre-agent logs"
	@echo "  make logs-config  Follow config-service logs"
	@echo "  make logs-web     Follow web-ui logs"
	@echo "  make status       Show service health status"
	@echo "  make clean        Remove containers, volumes, and images"
	@echo "  make db-shell     Open PostgreSQL shell"
	@echo ""

# ═══════════════════════════════════════════════════════════════════════
# Local Development
# ═══════════════════════════════════════════════════════════════════════

dev:
	docker compose up -d --build

stop:
	docker compose down

logs:
	docker compose logs -f

logs-agent:
	docker compose logs -f sre-agent

logs-config:
	docker compose logs -f config-service

logs-web:
	docker compose logs -f web-ui

status:
	@echo "═══════════════════════════════════════"
	@echo " OpenSRE Service Status"
	@echo "═══════════════════════════════════════"
	@docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
	@echo ""
	@curl -sf http://localhost:$(CONFIG_PORT)/health > /dev/null 2>&1 \
		&& echo "  config-service: ✅ healthy (port $(CONFIG_PORT))" \
		|| echo "  config-service: ❌ down"
	@curl -sf http://localhost:$(AGENT_PORT)/health > /dev/null 2>&1 \
		&& echo "  sre-agent:      ✅ healthy (port $(AGENT_PORT))" \
		|| echo "  sre-agent:      ❌ down"
	@curl -sf http://localhost:$(WEB_UI_PORT)/ > /dev/null 2>&1 \
		&& echo "  web-ui:         ✅ healthy (port $(WEB_UI_PORT))" \
		|| echo "  web-ui:         ❌ down"

clean:
	docker compose down -v --remove-orphans

db-shell:
	docker compose exec postgres psql -U opensre -d opensre
