#!/bin/bash
#
# OpenSRE Quick Health Check
# 
# Fast validation of deployment health without secrets
# Useful for quick verification after deployments
#
# Usage:
#   ./health_check.sh
#   ./health_check.sh --verbose
#

VERBOSE=${1:-""}
NAMESPACE=${NAMESPACE:-opensre}
WEB_UI_URL=${WEB_UI_URL:-https://ui.opensre.ai}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASSED=0
FAILED=0

check() {
    local name=$1
    local cmd=$2
    
    echo -n "Checking $name... "
    
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✅${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}❌${NC}"
        ((FAILED++))
        if [[ "$VERBOSE" == "--verbose" ]]; then
            echo -e "  ${YELLOW}Command: $cmd${NC}"
            eval "$cmd" 2>&1 | head -5 | sed 's/^/  /'
        fi
        return 1
    fi
}

check_pods() {
    local name=$1
    local label=$2
    
    echo -n "Pod: $name... "
    
    STATUS=$(kubectl get pods -n $NAMESPACE -l app=opensre-$name -o jsonpath='{.items[0].status.phase}' 2>/dev/null)
    
    if [[ "$STATUS" == "Running" ]]; then
        echo -e "${GREEN}✅ Running${NC}"
        ((PASSED++))
    else
        echo -e "${RED}❌ $STATUS${NC}"
        ((FAILED++))
        if [[ "$VERBOSE" == "--verbose" ]]; then
            kubectl get pods -n $NAMESPACE -l app=opensre-$name 2>&1 | sed 's/^/  /'
        fi
    fi
}

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════╗"
echo "║     OpenSRE Health Check              ║"
echo "╚════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}── Kubernetes Cluster ──${NC}"
check "kubectl access" "kubectl cluster-info"
check "namespace exists" "kubectl get ns $NAMESPACE"

echo -e "\n${YELLOW}── Pods ──${NC}"
check_pods "agent"
check_pods "config-service"
check_pods "orchestrator"
check_pods "web-ui"

echo -e "\n${YELLOW}── Services ──${NC}"
check "agent service" "kubectl get svc opensre-agent -n $NAMESPACE"
check "config-service service" "kubectl get svc opensre-config-service -n $NAMESPACE"
check "orchestrator service" "kubectl get svc opensre-orchestrator -n $NAMESPACE"
check "web-ui service" "kubectl get svc opensre-web-ui -n $NAMESPACE"

echo -e "\n${YELLOW}── Ingress ──${NC}"
check "ingress exists" "kubectl get ingress opensre-web-ui -n $NAMESPACE"
ALB_ADDR=$(kubectl get ingress opensre-web-ui -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
if [[ -n "$ALB_ADDR" ]]; then
    echo -e "  ALB: ${GREEN}$ALB_ADDR${NC}"
else
    echo -e "  ALB: ${RED}Not provisioned${NC}"
fi

echo -e "\n${YELLOW}── Secrets ──${NC}"
check "external secrets synced" "kubectl get externalsecret -n $NAMESPACE -o jsonpath='{.items[*].status.conditions[0].status}' | grep -q True"
SECRET_COUNT=$(kubectl get secrets -n $NAMESPACE --no-headers 2>/dev/null | wc -l | tr -d ' ')
echo -e "  Secrets count: $SECRET_COUNT"

echo -e "\n${YELLOW}── HTTPS Endpoints ──${NC}"
check "Web UI health" "curl -sf $WEB_UI_URL/api/health"
check "DNS resolves" "nslookup ui.opensre.ai"

echo -e "\n${YELLOW}── otel-demo (for testing) ──${NC}"
if kubectl get ns otel-demo > /dev/null 2>&1; then
    OTEL_PODS=$(kubectl get pods -n otel-demo --no-headers 2>/dev/null | wc -l | tr -d ' ')
    echo -e "  otel-demo pods: $OTEL_PODS"
    
    # Check if flagd is running for fault injection
    check "flagd running" "kubectl get pods -n otel-demo -l app.kubernetes.io/name=flagd -o jsonpath='{.items[0].status.phase}' | grep -q Running"
else
    echo -e "  ${YELLOW}otel-demo namespace not found${NC}"
fi

# Summary
echo -e "\n${BLUE}════════════════════════════════════════════${NC}"
echo -e "Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✅ All checks passed!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some checks failed${NC}"
    echo -e "${YELLOW}Run with --verbose for details${NC}"
    exit 1
fi

