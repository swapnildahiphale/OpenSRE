#!/usr/bin/env bash
# ============================================================================
# OpenSRE — Docker daemon bootstrap (shared by install.sh and start.sh)
# ============================================================================
# Starts the Docker daemon inside the Cloud Agent VM if it is not already
# running, applies the networking fix required for nested containers, and waits
# until the daemon is ready. Safe to call repeatedly (idempotent).
#
# Why a script instead of `service docker start`? The Cloud Agent VM does not
# run systemd (PID 1 is not init), so we launch `dockerd` directly.
# ============================================================================

set -euo pipefail

# ----------------------------------------------------------------------------
# Nested-container networking fix (MUST run before containers talk to each other)
# ----------------------------------------------------------------------------
# Inside this VM the container bridge sits on top of another bridge, and the
# kernel's bridge-netfilter passes intra-bridge traffic through iptables. In
# this nested setup that silently drops container-to-container packets, so
# services like config-service cannot reach Postgres. Turning bridge-netfilter
# off lets same-bridge traffic flow directly while outbound NAT still works.
# `|| true` keeps this non-fatal if the knob is unavailable.
sudo modprobe br_netfilter 2>/dev/null || true
sudo sysctl -w net.bridge.bridge-nf-call-iptables=0 >/dev/null 2>&1 || true
sudo sysctl -w net.bridge.bridge-nf-call-ip6tables=0 >/dev/null 2>&1 || true

# ----------------------------------------------------------------------------
# Start dockerd only if it is not already answering.
# ----------------------------------------------------------------------------
if sudo docker info >/dev/null 2>&1; then
  echo "[dockerd] Already running."
else
  echo "[dockerd] Starting Docker daemon in the background..."
  # nohup + background so the daemon outlives this script; logs go to a file
  # the agent can inspect. setsid detaches it from our process group.
  sudo bash -c 'nohup dockerd >/var/log/dockerd.log 2>&1 &'

  # Wait (up to ~60s) for the daemon socket to come up.
  echo "[dockerd] Waiting for the daemon to become ready..."
  for i in $(seq 1 60); do
    if sudo docker info >/dev/null 2>&1; then
      echo "[dockerd] Ready after ${i}s."
      break
    fi
    if [ "$i" -eq 60 ]; then
      echo "[dockerd] ERROR: daemon did not become ready in 60s. Recent log:"
      sudo tail -n 40 /var/log/dockerd.log || true
      exit 1
    fi
    sleep 1
  done
fi

# ----------------------------------------------------------------------------
# Let the non-root agent user use `docker` without sudo.
# ----------------------------------------------------------------------------
# The Makefile / docker-compose call `docker` directly (no sudo). The daemon
# socket is root-owned, so we relax its permissions each boot. Group membership
# added in install.sh only takes effect on a fresh login, so this is the
# reliable per-boot mechanism.
if [ -S /var/run/docker.sock ]; then
  sudo chmod 666 /var/run/docker.sock || true
fi
