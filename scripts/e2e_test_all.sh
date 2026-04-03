#!/bin/bash
#
# OpenSRE E2E Test Suite
# 
# Runs comprehensive end-to-end tests for:
# 1. Slack integration
# 2. otel-demo fault injection
#
# Usage:
#   ./e2e_test_all.sh              # Run all tests
#   ./e2e_test_all.sh slack        # Run only Slack tests
#   ./e2e_test_all.sh otel         # Run only otel-demo tests
#   ./e2e_test_all.sh otel cart    # Run specific fault test
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AWS_PROFILE=${AWS_PROFILE:-playground}
export AWS_REGION=${AWS_REGION:-us-west-2}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║       OpenSRE E2E Test Suite                         ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not found${NC}"
    exit 1
fi
echo "✅ kubectl available"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ aws cli not found${NC}"
    exit 1
fi
echo "✅ aws cli available"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ python3 not found${NC}"
    exit 1
fi
echo "✅ python3 available"

# Check cluster connectivity
echo -e "\n${YELLOW}Checking cluster connectivity...${NC}"
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ Cannot connect to Kubernetes cluster${NC}"
    echo "Please run: aws eks update-kubeconfig --name opensre-demo --region us-west-2"
    exit 1
fi
CLUSTER=$(kubectl config current-context)
echo "✅ Connected to cluster: $CLUSTER"

# Check namespaces
echo -e "\n${YELLOW}Checking namespaces...${NC}"
if ! kubectl get ns opensre &> /dev/null; then
    echo -e "${RED}❌ opensre namespace not found${NC}"
    exit 1
fi
echo "✅ opensre namespace exists"

if ! kubectl get ns otel-demo &> /dev/null; then
    echo -e "${YELLOW}⚠️ otel-demo namespace not found (otel tests will fail)${NC}"
else
    echo "✅ otel-demo namespace exists"
fi

# Install Python dependencies
echo -e "\n${YELLOW}Installing Python dependencies...${NC}"
pip3 install -q requests > /dev/null 2>&1 || true

# Run tests based on argument
TEST_TYPE=${1:-all}
FAULT_TYPE=${2:-cart}

run_slack_test() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Running Slack E2E Test${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    python3 "$SCRIPT_DIR/e2e_test_slack.py"
}

run_otel_test() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Running otel-demo Fault Injection Test${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    python3 "$SCRIPT_DIR/e2e_test_otel_demo.py" --fault "$FAULT_TYPE"
}

case $TEST_TYPE in
    slack)
        run_slack_test
        ;;
    otel)
        run_otel_test
        ;;
    all)
        run_slack_test
        echo ""
        run_otel_test
        ;;
    *)
        echo "Usage: $0 [slack|otel|all] [fault_type]"
        echo "Fault types: cart, product, recommendation, ad, all"
        exit 1
        ;;
esac

echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       E2E Tests Complete!                                  ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"

