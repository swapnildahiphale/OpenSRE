# OpenSRE — Local Development & E2E Testing
#
# Run 'make help' to see all available targets.

.PHONY: help dev dev-slack stop logs logs-agent logs-config logs-web status clean db-shell \
        kind-create kind-delete otel-install otel-images otel-wait e2e-verify \
        e2e-setup e2e-teardown e2e-agent e2e-status e2e-token \
        e2e-setup-eks e2e-teardown-eks eks-port-forward eks-port-forward-stop \
        e2e-test e2e-test-cart e2e-test-product e2e-test-recommendation e2e-test-ad e2e-test-all

.DEFAULT_GOAL := help

# ═══════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════

KIND_CLUSTER     := opensre-test
KIND_CONFIG      := test-infra/kind/kind-config.yaml
OTEL_VALUES_BASE := test-infra/otel-demo-values-base.yaml
OTEL_VALUES_KIND := test-infra/kind/otel-demo-values-kind.yaml
OTEL_VALUES_EKS  := test-infra/eks/otel-demo-values-eks.yaml
OTEL_CHART_VER   := 0.32.8
OTEL_APP_VER     := 1.11.1
OTEL_NAMESPACE   := otel-demo
KUBECONFIG_DOCKER:= test-infra/kind/kubeconfig-docker.yaml

# EKS configuration
EKS_CLUSTER      ?= $(error EKS_CLUSTER is required — set via env or make EKS_CLUSTER=your-cluster)
EKS_REGION       ?= $(error EKS_REGION is required — set via env or make EKS_REGION=us-west-2)

# Ports (must match docker-compose.yml and kind-config.yaml)
CONFIG_PORT      := 8081
AGENT_PORT       := 8001
WEB_UI_PORT      := 3002
PROMETHEUS_PORT  := 9090
GRAFANA_PORT     := 3001
JAEGER_PORT      := 16686
FRONTEND_PORT    := 8090

# ═══════════════════════════════════════════════════════════════════════
# Banner
# ═══════════════════════════════════════════════════════════════════════

define OPENSRE_BANNER
 ██████╗ ██████╗ ███████╗███╗   ██╗███████╗██████╗ ███████╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║██╔════╝██╔══██╗██╔════╝
██║   ██║██████╔╝█████╗  ██╔██╗ ██║███████╗██████╔╝█████╗
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║╚════██║██╔══██╗██╔══╝
╚██████╔╝██║     ███████╗██║ ╚████║███████║██║  ██║███████╗
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚══════╝
endef
export OPENSRE_BANNER

print-banner = @echo "$$OPENSRE_BANNER"

# ═══════════════════════════════════════════════════════════════════════
# Help
# ═══════════════════════════════════════════════════════════════════════

help:
	@echo ""
	$(print-banner)
	@echo ""
	@echo "OpenSRE — AI SRE Platform"
	@echo ""
	@echo "Local Development:"
	@echo "  make dev                Start all services (postgres, config, litellm, agent, web-ui)"
	@echo "  make dev-slack          Start all services + Slack bot"
	@echo "  make stop               Stop all services"
	@echo "  make logs               Follow all service logs"
	@echo "  make logs-agent         Follow sre-agent logs"
	@echo "  make logs-config        Follow config-service logs"
	@echo "  make logs-web           Follow web-ui logs"
	@echo "  make status             Show service health status"
	@echo "  make clean              Remove containers, volumes, and images"
	@echo "  make db-shell           Open PostgreSQL shell"
	@echo ""
	@echo "E2E Testing — Kind (local cluster):"
	@echo "  make e2e-setup          Full setup: kind cluster + otel-demo + networking"
	@echo "  make e2e-teardown       Delete kind cluster and clean up"
	@echo ""
	@echo "E2E Testing — EKS (remote cluster):"
	@echo "  make e2e-setup-eks      Full setup: otel-demo on EKS + port-forward tunnels"
	@echo "  make e2e-teardown-eks   Uninstall otel-demo from EKS"
	@echo "  make eks-port-forward   Start port-forward tunnels to EKS"
	@echo "  make eks-port-forward-stop  Stop port-forward tunnels"
	@echo ""
	@echo "E2E Testing — Shared (works with both kind and EKS):"
	@echo "  make e2e-status         Show cluster, pods, and observability status"
	@echo "  make e2e-token          Generate a team token for web UI access"
	@echo "  make e2e-agent          Restart sre-agent with E2E config"
	@echo ""
	@echo "E2E Fault Injection Tests:"
	@echo "  make e2e-test           Quick cart failure test (raw curl, no Python)"
	@echo "  make e2e-test-cart      Cart service fault (~10% EmptyCart failures)"
	@echo "  make e2e-test-product   Product catalog fault (~5% GetProduct failures)"
	@echo "  make e2e-test-recommendation  Recommendation service cache failure"
	@echo "  make e2e-test-ad        Ad service failure (all requests fail)"
	@echo "  make e2e-test-all       Run all 4 fault injection tests sequentially"
	@echo ""
	@echo "E2E Infrastructure (individual steps):"
	@echo "  make kind-create        Create kind cluster with port mappings"
	@echo "  make kind-delete        Delete kind cluster"
	@echo "  make otel-install       Install otel-demo helm chart (kind)"
	@echo "  make otel-wait          Wait for all otel-demo pods to be ready"
	@echo ""

# ═══════════════════════════════════════════════════════════════════════
# Local Development
# ═══════════════════════════════════════════════════════════════════════

dev:
	@bash scripts/generate-litellm-config.sh
	docker compose up -d --build
	@bash scripts/post-startup-banner.sh

dev-slack:
	@bash scripts/generate-litellm-config.sh
	docker compose --profile slack up -d --build
	@bash scripts/post-startup-banner.sh

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
	$(print-banner)
	@echo ""
	@echo " Service Status"
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

# ═══════════════════════════════════════════════════════════════════════
# E2E Testing — Full Setup
# ═══════════════════════════════════════════════════════════════════════

## Full E2E setup: kind cluster + otel-demo + networking + agent restart (local)
e2e-setup: kind-create otel-images otel-install otel-wait e2e-verify e2e-network e2e-agent
	@echo ""
	$(print-banner)
	@echo ""
	@echo " E2E Setup Complete!"
	@echo "  Kind cluster:  $(KIND_CLUSTER)"
	@echo "  Prometheus:    http://localhost:$(PROMETHEUS_PORT)"
	@echo "  Grafana:       http://localhost:$(GRAFANA_PORT)"
	@echo "  Jaeger:        http://localhost:$(JAEGER_PORT)"
	@echo "  otel Frontend: http://localhost:$(FRONTEND_PORT)"
	@echo "  OpenSRE Web UI:        http://localhost:$(WEB_UI_PORT)"
	@echo "  Agent API:     http://localhost:$(AGENT_PORT)"
	@echo ""
	@echo "Run 'make e2e-test' to trigger a cart failure investigation."
	@echo "Run 'make e2e-status' to check everything is healthy."

## Tear down kind cluster and clean up
e2e-teardown: kind-delete
	@echo "E2E environment torn down."

# ═══════════════════════════════════════════════════════════════════════
# E2E Testing — EKS
# ═══════════════════════════════════════════════════════════════════════

## Full E2E setup on EKS: otel-demo + port-forward tunnels + agent restart
e2e-setup-eks:
	@EKS_CLUSTER=$(EKS_CLUSTER) EKS_REGION=$(EKS_REGION) OTEL_NAMESPACE=$(OTEL_NAMESPACE) \
		OTEL_CHART_VER=$(OTEL_CHART_VER) bash test-infra/eks/setup.sh
	@echo ""
	@echo "[eks] Generating kubeconfig for sre-agent container..."
	@EKS_CLUSTER=$(EKS_CLUSTER) EKS_REGION=$(EKS_REGION) OTEL_NAMESPACE=$(OTEL_NAMESPACE) \
		bash test-infra/eks/generate-kubeconfig.sh
	@echo ""
	@echo "[eks] Waiting for telemetry to flow (30s)..."
	@sleep 30
	@$(MAKE) e2e-verify
	@$(MAKE) e2e-agent-eks
	@echo "[eks] Generating team token for OpenSRE Web UI..."
	@TOKEN=$$(curl -s -X POST "http://localhost:$(CONFIG_PORT)/api/v1/admin/orgs/local/teams/default/tokens" \
		-H "Authorization: Bearer local-admin-token" \
		-H "Content-Type: application/json" \
		-d '{"description":"e2e-setup","permissions":["team:read","team:write"]}' \
		| python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null); \
	echo ""; \
	echo "$$OPENSRE_BANNER"; \
	echo ""; \
	echo " EKS E2E Setup Complete!"; \
	echo "  Cluster:       $(EKS_CLUSTER) ($(EKS_REGION))"; \
	echo "  Prometheus:    http://localhost:9090"; \
	echo "  Grafana:       http://localhost:3000"; \
	echo "  Jaeger:        http://localhost:16686"; \
	echo "  OpenSearch:    http://localhost:9200"; \
	echo "  OpenSRE Web UI:        http://localhost:$(WEB_UI_PORT)"; \
	echo "  Agent API:     http://localhost:$(AGENT_PORT)"; \
	echo ""; \
	if [ -n "$$TOKEN" ]; then \
		echo "  Team token:    $$TOKEN"; \
		echo ""; \
		echo "  Paste this token in the OpenSRE Web UI to sign in."; \
	else \
		echo "  ⚠ Token generation failed. Run 'make e2e-token' manually."; \
	fi; \
	echo ""; \
	echo "Run 'make e2e-test' to trigger a cart failure investigation."; \
	echo "═══════════════════════════════════════"

## Uninstall otel-demo from EKS and stop tunnels
e2e-teardown-eks:
	@OTEL_NAMESPACE=$(OTEL_NAMESPACE) bash test-infra/eks/teardown.sh
	@echo "EKS E2E environment torn down."

## Start port-forward tunnels to EKS cluster
eks-port-forward:
	@OTEL_NAMESPACE=$(OTEL_NAMESPACE) bash test-infra/eks/port-forward.sh start

## Stop port-forward tunnels
eks-port-forward-stop:
	@bash test-infra/eks/port-forward.sh stop

## Restart sre-agent with EKS kubeconfig
e2e-agent-eks:
	@echo "Restarting sre-agent with EKS config..."
	@docker compose -f docker-compose.yml -f docker-compose.e2e-eks.yml up -d sre-agent web-ui 2>&1 | grep -v "level=warning" || true
	@echo "Waiting for agent to be healthy..."
	@for i in $$(seq 1 12); do \
		sleep 5; \
		curl -sf http://localhost:$(AGENT_PORT)/health > /dev/null 2>&1 \
			&& { echo "  sre-agent ready!"; break; } \
			|| echo "  waiting... ($${i}x5s)"; \
	done

# ═══════════════════════════════════════════════════════════════════════
# Kind Cluster
# ═══════════════════════════════════════════════════════════════════════

kind-create:
	@echo "Creating kind cluster '$(KIND_CLUSTER)'..."
	@kind get clusters 2>/dev/null | grep -q "^$(KIND_CLUSTER)$$" \
		&& echo "Cluster '$(KIND_CLUSTER)' already exists, skipping." \
		|| kind create cluster --config $(KIND_CONFIG)
	@kubectl cluster-info --context kind-$(KIND_CLUSTER) 2>/dev/null | head -1

kind-delete:
	@echo "Deleting kind cluster '$(KIND_CLUSTER)'..."
	@kind delete cluster --name $(KIND_CLUSTER) 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════════════
# otel-demo Images (pre-load for VPN/network issues)
# ═══════════════════════════════════════════════════════════════════════

OTEL_IMAGES := \
	ghcr.io/open-feature/flagd:v0.11.1 \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-accountingservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-adservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-cartservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-checkoutservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-currencyservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-emailservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-frauddetectionservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-frontend \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-frontendproxy \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-imageprovider \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-kafka \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-loadgenerator \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-paymentservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-productcatalogservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-quoteservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-recommendationservice \
	ghcr.io/open-telemetry/demo:$(OTEL_APP_VER)-shippingservice \
	valkey/valkey:7.2-alpine \
	busybox:latest \
	grafana/grafana:11.1.0 \
	jaegertracing/all-in-one:1.53.0 \
	opensearchproject/opensearch:2.15.0 \
	otel/opentelemetry-collector-contrib:0.108.0 \
	quay.io/prometheus/prometheus:v2.53.1

## Pull images on host and load into kind (works around VPN/Docker networking issues)
otel-images:
	@echo "Pulling otel-demo images on host..."
	@FAIL=0; for img in $(OTEL_IMAGES); do \
		docker image inspect "$$img" > /dev/null 2>&1 \
			&& echo "  cached: $$(basename $$img)" \
			|| { echo "  pulling: $$img"; docker pull "$$img" > /dev/null 2>&1 \
				|| { echo "  FAILED: $$img"; FAIL=$$((FAIL+1)); }; }; \
	done; \
	if [ "$$FAIL" -gt 0 ]; then echo "WARNING: $$FAIL image(s) failed to pull"; fi
	@echo "Loading images into kind cluster..."
	@OK=0; for img in $(OTEL_IMAGES); do \
		docker save "$$img" | docker exec -i $(KIND_CLUSTER)-control-plane \
			ctr --namespace=k8s.io images import - > /dev/null 2>&1 \
			&& OK=$$((OK+1)) \
			|| echo "  WARN: failed to load $$img"; \
	done; \
	echo "  Loaded $$OK images into kind."

# ═══════════════════════════════════════════════════════════════════════
# otel-demo Helm Install
# ═══════════════════════════════════════════════════════════════════════

otel-install:
	@echo "Installing otel-demo (chart v$(OTEL_CHART_VER)) for kind..."
	@helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts 2>/dev/null || true
	@helm repo update open-telemetry > /dev/null 2>&1
	@kubectl create namespace $(OTEL_NAMESPACE) 2>/dev/null || true
	@helm status otel-demo -n $(OTEL_NAMESPACE) > /dev/null 2>&1 \
		&& echo "otel-demo already installed, upgrading..." \
		&& helm upgrade otel-demo open-telemetry/opentelemetry-demo \
			--version $(OTEL_CHART_VER) -n $(OTEL_NAMESPACE) \
			-f $(OTEL_VALUES_BASE) -f $(OTEL_VALUES_KIND) \
		|| helm install otel-demo open-telemetry/opentelemetry-demo \
			--version $(OTEL_CHART_VER) -n $(OTEL_NAMESPACE) \
			-f $(OTEL_VALUES_BASE) -f $(OTEL_VALUES_KIND)

## Wait for otel-demo pods to be ready (timeout 5 min)
otel-wait:
	@echo "Waiting for otel-demo pods (timeout 5m)..."
	@for i in $$(seq 1 30); do \
		READY=$$(kubectl get pods -n $(OTEL_NAMESPACE) --no-headers 2>/dev/null \
			| awk '{print $$3}' | grep -c Running); \
		TOTAL=$$(kubectl get pods -n $(OTEL_NAMESPACE) --no-headers 2>/dev/null \
			| wc -l | tr -d ' '); \
		echo "  $$READY/$$TOTAL running ($${i}0s)"; \
		if [ "$$READY" -ge 22 ]; then echo "  All pods ready!"; break; fi; \
		if [ "$$i" -eq 30 ]; then \
			echo "  WARNING: Timeout — some pods not ready:"; \
			kubectl get pods -n $(OTEL_NAMESPACE) --no-headers | grep -v Running; \
		fi; \
		sleep 10; \
	done

# ═══════════════════════════════════════════════════════════════════════
# E2E Telemetry Verification
# ═══════════════════════════════════════════════════════════════════════

## Verify telemetry is flowing to Prometheus and Jaeger (runs after otel-wait)
e2e-verify:
	@echo "Verifying telemetry flow (waiting 30s for metrics to arrive)..."
	@sleep 30
	@SERVICES=$$(curl -sf 'http://localhost:$(PROMETHEUS_PORT)/api/v1/label/service_name/values' \
		| python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',[])))" 2>/dev/null || echo 0); \
	echo "  Prometheus: $$SERVICES services reporting metrics"; \
	if [ "$$SERVICES" -ge 5 ]; then echo "  OK"; else echo "  WARNING: Expected 20+ services, got $$SERVICES"; fi
	@JAEGER=$$(kubectl exec deploy/otel-demo-jaeger -n $(OTEL_NAMESPACE) -- \
		wget -q -O- 'http://localhost:16686/jaeger/ui/api/services' 2>/dev/null \
		| python3 -c "import sys,json; print(len(json.load(sys.stdin).get('data',[])))" 2>/dev/null || echo 0); \
	echo "  Jaeger: $$JAEGER services reporting traces"; \
	if [ "$$JAEGER" -ge 5 ]; then echo "  OK"; else echo "  WARNING: Expected 20+ services, got $$JAEGER"; fi
	@OS_DOCS=$$(curl -sf 'http://localhost:9200/otel/_count' \
		| python3 -c "import sys,json; print(json.load(sys.stdin).get('count',0))" 2>/dev/null || echo 0); \
	echo "  OpenSearch: $$OS_DOCS log documents in 'otel' index"; \
	if [ "$$OS_DOCS" -ge 10 ]; then echo "  OK"; else echo "  WARNING: Expected logs in OpenSearch, got $$OS_DOCS"; fi

# ═══════════════════════════════════════════════════════════════════════
# E2E Networking & Agent
# ═══════════════════════════════════════════════════════════════════════

## Connect kind cluster to OpenSRE Docker networks and generate kubeconfig
e2e-network:
	@echo "Setting up Docker networking..."
	@bash test-infra/kind/generate-kubeconfig.sh
	@docker network connect opensre_default $(KIND_CLUSTER)-control-plane 2>/dev/null \
		|| echo "  already connected to opensre_default"
	@docker network connect opensre_app_network $(KIND_CLUSTER)-control-plane 2>/dev/null \
		|| echo "  already connected to opensre_app_network"
	@echo "  Networking ready."

## Restart sre-agent with E2E override (kubeconfig + port-forward tunnels)
e2e-agent:
	@echo "Restarting sre-agent with E2E config..."
	@docker compose up -d sre-agent 2>&1 | grep -v "level=warning" || true
	@echo "Waiting for agent to be healthy..."
	@for i in $$(seq 1 12); do \
		sleep 5; \
		curl -sf http://localhost:$(AGENT_PORT)/health > /dev/null 2>&1 \
			&& { echo "  sre-agent ready!"; break; } \
			|| echo "  waiting... ($${i}x5s)"; \
	done

# ═══════════════════════════════════════════════════════════════════════
# E2E Status & Testing
# ═══════════════════════════════════════════════════════════════════════

## Show full E2E environment status (works with both kind and EKS)
e2e-status:
	$(print-banner)
	@echo ""
	@echo " E2E Environment Status"
	@echo ""
	@echo "Kubernetes cluster:"
	@CTX=$$(kubectl config current-context 2>/dev/null || echo "none"); \
	echo "  Context: $$CTX"; \
	NODES=$$(kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' '); \
	echo "  Nodes: $$NODES"
	@echo ""
	@echo "otel-demo pods:"
	@READY=$$(kubectl get pods -n $(OTEL_NAMESPACE) --no-headers 2>/dev/null \
		| awk '{print $$3}' | grep -c Running 2>/dev/null || echo 0); \
	TOTAL=$$(kubectl get pods -n $(OTEL_NAMESPACE) --no-headers 2>/dev/null \
		| wc -l | tr -d ' ' 2>/dev/null || echo 0); \
	echo "  $$READY/$$TOTAL running"
	@kubectl get pods -n $(OTEL_NAMESPACE) --no-headers 2>/dev/null \
		| grep -v Running | awk '{print "  ⚠️  " $$1 " → " $$3}' || true
	@echo ""
	@echo "Observability tools:"
	@curl -sf http://localhost:$(PROMETHEUS_PORT)/-/healthy > /dev/null 2>&1 \
		&& echo "  ✅ Prometheus  http://localhost:$(PROMETHEUS_PORT)" \
		|| echo "  ❌ Prometheus"
	@curl -sf http://localhost:$(GRAFANA_PORT)/api/health > /dev/null 2>&1 \
		&& echo "  ✅ Grafana     http://localhost:$(GRAFANA_PORT)" \
		|| echo "  ❌ Grafana"
	@curl -sf http://localhost:$(JAEGER_PORT)/ > /dev/null 2>&1 \
		&& echo "  ✅ Jaeger      http://localhost:$(JAEGER_PORT)" \
		|| echo "  ❌ Jaeger"
	@curl -sf http://localhost:9200/ > /dev/null 2>&1 \
		&& echo "  ✅ OpenSearch  http://localhost:9200" \
		|| echo "  ❌ OpenSearch"
	@curl -sf http://localhost:$(FRONTEND_PORT)/ > /dev/null 2>&1 \
		&& echo "  ✅ otel UI     http://localhost:$(FRONTEND_PORT)" \
		|| echo "  ❌ otel Frontend"
	@echo ""
	@echo "OpenSRE services:"
	@curl -sf http://localhost:$(CONFIG_PORT)/health > /dev/null 2>&1 \
		&& echo "  ✅ config-service  http://localhost:$(CONFIG_PORT)" \
		|| echo "  ❌ config-service"
	@curl -sf http://localhost:$(AGENT_PORT)/health > /dev/null 2>&1 \
		&& echo "  ✅ sre-agent       http://localhost:$(AGENT_PORT)" \
		|| echo "  ❌ sre-agent"
	@curl -sf http://localhost:$(WEB_UI_PORT)/ > /dev/null 2>&1 \
		&& echo "  ✅ web-ui          http://localhost:$(WEB_UI_PORT)" \
		|| echo "  ❌ web-ui"

## Generate a team token for web UI access
e2e-token:
	@echo "Generating team token..."
	@TOKEN=$$(curl -s -X POST "http://localhost:$(CONFIG_PORT)/api/v1/admin/orgs/local/teams/default/tokens" \
		-H "Authorization: Bearer local-admin-token" \
		-H "Content-Type: application/json" \
		-d '{"description":"e2e-test","permissions":["team:read","team:write"]}' \
		| python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null); \
	if [ -n "$$TOKEN" ]; then \
		echo ""; \
		echo "Team token: $$TOKEN"; \
		echo ""; \
		echo "To login via web UI, open http://localhost:$(WEB_UI_PORT)"; \
		echo "and run in browser console:"; \
		echo "  fetch('/api/session/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:'$$TOKEN'})})"; \
	else \
		echo "Failed to generate token. Is config-service running?"; \
	fi

## Quick cart failure test (raw curl, no fault injection script)
e2e-test:
	@echo "Triggering cart failure investigation..."
	@TOKEN=$$(curl -s -X POST "http://localhost:$(CONFIG_PORT)/api/v1/admin/orgs/local/teams/default/tokens" \
		-H "Authorization: Bearer local-admin-token" \
		-H "Content-Type: application/json" \
		-d '{"description":"e2e-test","permissions":["team:read","team:write"]}' \
		| python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null); \
	if [ -z "$$TOKEN" ]; then echo "Failed to get token"; exit 1; fi; \
	echo "Token acquired. Starting investigation..."; \
	curl -s -N -X POST "http://localhost:$(AGENT_PORT)/investigate" \
		-H "Content-Type: application/json" \
		-H "Authorization: Bearer $$TOKEN" \
		-d '{"prompt":"Investigate cart service failure in the otel-demo namespace. Users report errors adding items to cart. Check pod health, logs, and recent deployments."}' \
		| python3 test-infra/parse-sse.py

## Cart service fault: ~10% EmptyCart operation failures via cartServiceFailure flag
e2e-test-cart:
	python3 scripts/e2e_test_otel_demo.py --fault cart \
		--agent-url http://localhost:$(AGENT_PORT) \
		--config-url http://localhost:$(CONFIG_PORT)

## Product catalog fault: ~5% GetProduct failures via productCatalogFailure flag
e2e-test-product:
	python3 scripts/e2e_test_otel_demo.py --fault product \
		--agent-url http://localhost:$(AGENT_PORT) \
		--config-url http://localhost:$(CONFIG_PORT)

## Recommendation service fault: cache failure causing high latency
e2e-test-recommendation:
	python3 scripts/e2e_test_otel_demo.py --fault recommendation \
		--agent-url http://localhost:$(AGENT_PORT) \
		--config-url http://localhost:$(CONFIG_PORT)

## Ad service fault: all ad requests fail via adServiceFailure flag
e2e-test-ad:
	python3 scripts/e2e_test_otel_demo.py --fault ad \
		--agent-url http://localhost:$(AGENT_PORT) \
		--config-url http://localhost:$(CONFIG_PORT)

## Run all 4 fault injection tests sequentially
e2e-test-all:
	python3 scripts/e2e_test_otel_demo.py --fault all \
		--agent-url http://localhost:$(AGENT_PORT) \
		--config-url http://localhost:$(CONFIG_PORT)
