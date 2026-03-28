# Attribution

OpenSRE is an open-source AI SRE agent platform.

## License

OpenSRE is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for the full text.

## What Was Excluded

The following components were **not included** in OpenSRE:

- `sre-agent/sandbox_manager.py` — gVisor K8s sandbox pod management
- `sre-agent/sandbox_server.py` — Sandbox-internal FastAPI server
- `sre-agent/credential-proxy/` — Zero-knowledge secret injection (Envoy + resolver)
- `sre-agent/sandbox-router/` — Sandbox request routing
- `sre-agent/Dockerfile` (hardened production image) — replaced with simplified Dockerfile
- 8 Helm templates related to sandbox/credential infrastructure

## OpenSRE Differentiators

1. **Episodic Memory System** — learns from past investigations to improve future ones
2. **Neo4j Knowledge Graph** — service topology and dependency awareness
3. **Memory UI Pages** — dashboard, episode browser, similarity search, strategy explorer
