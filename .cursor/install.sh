#!/usr/bin/env bash
# ============================================================================
# OpenSRE — Cloud Agent install script
# ============================================================================
# This runs ONCE after the repository is checked out (and, with environment
# builds, it is what creates the baseline snapshot). Everything here must be
# idempotent: it can run again on a partially-prepared machine without breaking.
#
# OpenSRE's whole dev stack runs through Docker Compose (`make dev`), so the
# main job of this script is to make Docker usable inside the Cloud Agent VM
# (a nested-container environment) and to pre-build the compose images so the
# first boot is fast. Per-boot work (starting the Docker daemon and the stack)
# lives in start.sh instead.
# ============================================================================

set -euo pipefail

# Resolve the repository root from this script's location so the script works
# no matter what directory it is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "[install] OpenSRE Cloud Agent setup starting in $REPO_ROOT"

# ----------------------------------------------------------------------------
# 1. Install Docker Engine + Compose plugin (only if it is not already present).
# ----------------------------------------------------------------------------
# The default Cloud Agent image ships Node, pnpm, Python, make, git and curl,
# but not Docker. We add Docker Engine via Docker's official convenience script.
# `command -v docker` keeps this step idempotent across re-runs / snapshots.
if ! command -v docker >/dev/null 2>&1; then
  echo "[install] Docker not found — installing Docker Engine..."
  curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
  sudo sh /tmp/get-docker.sh
  rm -f /tmp/get-docker.sh
else
  echo "[install] Docker already installed: $(docker --version)"
fi

# ----------------------------------------------------------------------------
# 2. Install fuse-overlayfs (required storage driver for nested Docker).
# ----------------------------------------------------------------------------
# The Cloud Agent root filesystem is itself an overlay mount, so Docker's normal
# overlay2 driver cannot stack on top of it. fuse-overlayfs works in userspace
# and is the reliable choice here. uidmap is handy for rootless tooling too.
# DEBIAN_FRONTEND + --force-confold keep apt fully non-interactive (some base
# images have a modified /etc/fuse.conf that would otherwise prompt).
if ! command -v fuse-overlayfs >/dev/null 2>&1; then
  echo "[install] Installing fuse-overlayfs + uidmap..."
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    -o Dpkg::Options::="--force-confold" \
    fuse-overlayfs uidmap
else
  echo "[install] fuse-overlayfs already installed."
fi

# ----------------------------------------------------------------------------
# 3. Tell the Docker daemon to use the fuse-overlayfs storage driver.
# ----------------------------------------------------------------------------
# Writing daemon.json here (durable state captured in the snapshot) means the
# daemon started in start.sh picks up the right driver automatically.
echo "[install] Writing /etc/docker/daemon.json (storage-driver: fuse-overlayfs)"
sudo mkdir -p /etc/docker
echo '{
  "storage-driver": "fuse-overlayfs"
}' | sudo tee /etc/docker/daemon.json >/dev/null

# Allow the current (non-root) user to talk to the Docker socket without sudo.
# Group membership only applies to new logins, so start.sh also relaxes the
# socket permissions each boot; adding the group here is a durable convenience.
sudo groupadd -f docker
sudo usermod -aG docker "$(id -un)" || true

# ----------------------------------------------------------------------------
# 4. Create the local .env file the compose stack reads.
# ----------------------------------------------------------------------------
# `make dev` (and docker-compose) require a .env file. We seed it from the
# committed example if the developer has not provided one. The example uses a
# placeholder ANTHROPIC_API_KEY, which is enough to boot every service; a real
# key is only needed to run live LLM investigations. If ANTHROPIC_API_KEY is
# present in the environment (e.g. injected as a Cloud Agent secret), we splice
# it into .env so investigations work out of the box.
if [ ! -f "$REPO_ROOT/.env" ]; then
  echo "[install] Creating .env from .env.example"
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
fi
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "[install] Injecting ANTHROPIC_API_KEY from the environment into .env"
  # Replace the placeholder line with the real key (portable sed in-place).
  sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}|" "$REPO_ROOT/.env"
fi

# ----------------------------------------------------------------------------
# 5. Bring Docker up briefly to create volumes and pre-build the images.
# ----------------------------------------------------------------------------
# Building the images now means they land in /var/lib/docker, which the build
# snapshot captures — so the first real boot does not pay the (heavy) build
# cost again. This needs a running daemon, so we start one temporarily.
"$SCRIPT_DIR/start-dockerd.sh"

# The named volumes in docker-compose.yml are declared `external: true` so that
# a stray `docker compose down -v` cannot wipe investigation/memory data. That
# means we must create them explicitly before the stack can start.
echo "[install] Creating external Docker volumes (idempotent)"
for vol in opensre-postgres-data opensre-neo4j-data opensre-agent-sessions; do
  docker volume create "$vol" >/dev/null
done

# Pre-build the three application images (config-service, sre-agent, web-ui).
# Postgres/Neo4j are pulled on first `up`. `make dev` also runs a helper that
# generates the (optional) LiteLLM config; setup-llm is a no-op for the default
# direct-Anthropic setup. We build here rather than run so install terminates.
echo "[install] Pre-building compose images (this is the slow, one-time step)"
export COMPOSE_PROJECT_NAME=opensre
docker compose -f docker-compose.yml build

echo "[install] Install complete. Services are started per-boot by start.sh."
