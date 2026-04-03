#!/usr/bin/env bash
set -euo pipefail

# Applies Alembic migrations to the DB pointed to by DATABASE_URL.
#
# Usage:
#   ./scripts/db_migrate.sh
#
# This script will auto-load `.env` from config_service (gitignored) if present.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${DATABASE_URL:-}" && -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set. Ensure .env exists (or export DATABASE_URL) and retry."
  exit 1
fi

# If you're running with an SSM tunnel (scripts/rds_tunnel.sh), set DATABASE_URL_TUNNEL
# to point to localhost:5433. Keep `sslmode=require` (RDS enforces SSL).
if [[ -n "${DATABASE_URL_TUNNEL:-}" ]]; then
  export DATABASE_URL="${DATABASE_URL_TUNNEL}"
fi

# If DATABASE_URL points at localhost (tunnel), ensure the tunnel is running.
python3 - <<'PY'
import os, socket, sys
from urllib.parse import urlparse

u = urlparse(os.environ["DATABASE_URL"])
host = u.hostname or ""
port = int(u.port or 5432)
if host in ("127.0.0.1", "localhost"):
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", port))
    except Exception:
        print(f"SSM tunnel is not running on 127.0.0.1:{port}.", file=sys.stderr)
        print("Start it in another terminal: ./scripts/rds_tunnel.sh", file=sys.stderr)
        sys.exit(1)
    finally:
        try: s.close()
        except Exception: pass
PY

python3 -m alembic upgrade head
echo "Migrations applied."


