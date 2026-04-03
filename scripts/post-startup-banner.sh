#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# Post-startup banner — shown after `make dev` completes
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Read admin token from .env (default from docker-compose)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
source "$SCRIPT_DIR/banner.sh"
ADMIN_TOKEN="${ADMIN_TOKEN:-local-admin-token}"
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  val=$(grep -E '^ADMIN_TOKEN=' "$PROJECT_ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)
  [[ -n "$val" ]] && ADMIN_TOKEN="$val"
fi

echo ""
print_banner "$GREEN"
echo ""
echo -e "${GREEN}${BOLD} ✓ OpenSRE is running!${NC}"
echo ""
echo -e "  ${BOLD}OpenSRE Web UI:${NC}        ${CYAN}http://localhost:3002${NC}"
echo -e "  ${BOLD}Admin token:${NC}   ${YELLOW}${ADMIN_TOKEN}${NC}"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo -e "    1. Open ${CYAN}http://localhost:3002${NC}"
echo -e "    2. Paste the admin token to sign in"
echo -e "    3. Go to ${BOLD}Org Tree${NC} → click a team → ${BOLD}Tokens${NC} → issue a team token"
echo -e "    4. Sign out, sign back in with the team token for investigations"
echo ""
echo -e "  ${DIM}Useful commands:${NC}"
echo -e "    ${DIM}make logs        Follow all service logs${NC}"
echo -e "    ${DIM}make logs-agent  Follow sre-agent logs${NC}"
echo -e "    ${DIM}make status      Check service health${NC}"
echo -e "    ${DIM}make stop        Stop all services${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
