# Security Policy

## Supported Versions

We release security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| Latest release | :white_check_mark: |
| Older releases | :x: |

We strongly recommend running the latest version of OpenSRE.

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of these methods:

### 1. GitHub Security Advisories (Preferred)

Report security vulnerabilities privately through GitHub:

1. Go to the [Security tab](https://github.com/swapnildahiphale/OpenSRE/security)
2. Click "Report a vulnerability"
3. Fill out the advisory form with details

### 2. Email

Send details to **swapnil@opensre.in** with:

- Type of vulnerability (RCE, injection, XSS, etc.)
- Affected component(s)
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### What to Expect

- **Acknowledgment**: Within 24 hours
- **Initial assessment**: Within 3 business days
- **Regular updates**: At least every 7 days until resolved
- **Disclosure timeline**: Coordinated disclosure after patch is available

We follow responsible disclosure practices and will credit reporters (unless you prefer to remain anonymous).

## Scope

### In Scope

Security issues in:

- **OpenSRE core** (agent, orchestrator, config-service)
- **Web console** (authentication, authorization, XSS, CSRF)
- **API endpoints** (injection, authentication bypass)
- **Slack bot** (command injection, unauthorized access)
- **Integrations** (credential leakage, SSRF)
- **Deployment configs** (Kubernetes, Docker)
- **Dependencies** (critical CVEs in direct dependencies)

### Out of Scope

- Social engineering attacks
- Physical attacks
- Attacks requiring MITM on local network
- DoS/DDoS attacks
- Issues in third-party services (Slack, AWS, etc.)
- Issues only exploitable with admin access
- Theoretical vulnerabilities without proof of concept
- Brute force attacks without additional vulnerability

## Simple-Mode / Local-Dev Security Posture

> **⚠️ Simple-mode is for local development only.**

`sre-agent/server_simple.py` (activated by `USE_SIMPLE_MODE=true` or `make dev`) runs the agent in-process, without Kubernetes sandboxes, and with **no TLS, no rate limiting, and no request-body size caps** by design. This is intentional for a single-developer laptop workflow where the compose stack is not exposed beyond `localhost`.

### What this means

| Property | Simple-mode behaviour | Production expectation |
|---|---|---|
| Transport | Cleartext HTTP (port 8000) | TLS terminated at reverse proxy / ingress |
| Rate limiting | None | Reverse proxy / ingress (e.g. nginx `limit_req`, Caddy, AWS ALB) |
| Request body cap | None | Reverse proxy `client_max_body_size` / ALB max payload |
| Concurrency | Unbounded asyncio tasks | Reverse proxy worker limits / API gateway throttling |
| Process isolation | Shared process (no sandbox) | `server.py` + Kubernetes sandboxes |

### Recommended setup for self-hosters

If you expose OpenSRE on a network (VM, VPS, cloud instance), follow these steps:

1. **Bind to localhost only** — do not publish port 8000 to `0.0.0.0`:

   ```yaml
   # docker-compose.yml override
   services:
     sre-agent:
       ports:
         - "127.0.0.1:8000:8000"   # ✅ loopback only
         # - "8000:8000"            # ❌ exposed on all interfaces
   ```

2. **Terminate TLS at a reverse proxy** (nginx, Caddy, Traefik, AWS ALB, GCP Load Balancer, etc.) — do **not** run simple-mode directly on a public port. Simple-mode has no built-in TLS support.

3. **Add rate limiting and body-size caps at the proxy layer** — see the [Hardening Checklist](#hardening-checklist) below.

4. **Prefer `server.py` (Kubernetes sandbox mode) for any shared / production deployment** — it provides process isolation that simple-mode intentionally omits.

---

## Hardening Checklist

Use this checklist before exposing any OpenSRE deployment beyond a personal laptop.

### TLS at the ingress

- [ ] A valid TLS certificate is provisioned (Let's Encrypt / cert-manager / ACM).
- [ ] HTTP → HTTPS redirect is enforced.
- [ ] TLS 1.2+ only; TLS 1.0 and 1.1 disabled.
- [ ] `Strict-Transport-Security` (HSTS) header set (min `max-age=31536000`).

### Rate limiting

- [ ] Per-IP request rate limited at the reverse proxy / API gateway (e.g. nginx `limit_req_zone`, Caddy `rate_limit`, AWS WAF rate-based rules).
- [ ] `/investigate` (POST) endpoint rate limited more aggressively than read endpoints, as each call triggers an LLM completion.
- [ ] Burst allowance tuned so legitimate interactive use is not impacted.

### Request body size caps

- [ ] Reverse proxy `client_max_body_size` (nginx) or equivalent set to a reasonable limit (e.g. 10 MB for file attachments).
- [ ] Server-side validation rejects unexpectedly large payloads before they reach the agent.

### Concurrency limits at the edge

- [ ] Maximum concurrent connections / workers configured at the proxy (e.g. nginx `worker_connections`, ALB target group connection limits).
- [ ] Gunicorn / Uvicorn worker count tuned to available CPU, not left at default.
- [ ] Long-running SSE streams accounted for in connection-limit calculations.

### Authentication & network controls

- [ ] Admin token rotated from the auto-generated default before first exposure.
- [ ] Port 8000 not published to `0.0.0.0`; all traffic enters via the proxy.
- [ ] Firewall / security group allows only the proxy's IP range to reach the agent.
- [ ] SSO / OIDC enabled for multi-user deployments (see [docs/SSO_SETUP.md](docs/SSO_SETUP.md)).

### Monitoring

- [ ] Access logs from the proxy shipped to a SIEM or log aggregator.
- [ ] Anomalous request rates / 4xx spikes trigger an alert.
- [ ] Agent audit logs (all tool calls) reviewed periodically.

---

## Security Best Practices

When deploying OpenSRE:

### Secrets Management

- **Never commit secrets** to version control
- Use **secrets proxy** in production (see [deployment guide](docs/DEPLOYMENT.md))
- Rotate credentials regularly
- Use separate credentials for dev/staging/prod

### Network Security

- Deploy behind a firewall
- Use TLS for all external communications
- Restrict API access to authorized networks
- Enable audit logging

### Authentication & Authorization

- Enable SSO/OIDC for production deployments
- Use role-based access control (RBAC)
- Review team permissions regularly
- Enable approval workflows for critical changes

### Agent Sandboxing

- Use **Claude Sandbox** in production (isolated Kubernetes namespaces)
- Limit agent permissions to minimum required
- Monitor agent actions via audit logs
- Review tool usage patterns

### Updates & Monitoring

- Subscribe to security announcements (watch this repo)
- Update OpenSRE regularly
- Monitor dependency vulnerabilities (Dependabot enabled)
- Review audit logs for suspicious activity

## Known Security Considerations

### Agent Tool Execution

OpenSRE agents execute commands against your infrastructure (kubectl, AWS CLI, etc.). This is by design for incident response.

**Mitigations:**
- Tools run in isolated sandboxes
- Secrets never touch the agent (injected by proxy)
- Approval workflows for critical operations
- Full audit trail of all actions

### LLM Prompt Injection

Like all LLM-powered tools, OpenSRE may be susceptible to prompt injection attacks.

**Mitigations:**
- Input validation and sanitization
- Separate system and user contexts
- Tool-specific safety checks
- Human approval for destructive operations

### Data Privacy

Agents may access sensitive data (logs, metrics, code).

**Mitigations:**
- On-premise deployment option (full data control)
- Configurable data retention policies
- Audit logs for data access
- RBAC for sensitive integrations

## Security Features

OpenSRE includes security features for production:

- **SOC 2 compliant** infrastructure (managed deployments)
- **End-to-end encryption** for data in transit
- **Secrets proxy** (credentials never touch agents)
- **Audit logging** (all actions tracked)
- **RBAC** (role-based access control)
- **SSO/OIDC** support
- **Approval workflows** for critical changes
- **Isolated sandboxes** (Kubernetes namespaces per agent)

See [Enterprise Ready](README.md#enterprise-ready) for details.

## Vulnerability Disclosure Policy

When we receive a security report:

1. **Confirmation**: We confirm the vulnerability
2. **Patch development**: We develop and test a fix
3. **Coordinated disclosure**: We coordinate with the reporter on disclosure timeline
4. **Release**: We release a patch and security advisory
5. **Public disclosure**: We publicly disclose the issue (typically 90 days after patch)

We credit security researchers in:
- Security advisories
- Release notes
- Public acknowledgments (if desired)

## Security Hall of Fame

We recognize security researchers who help keep OpenSRE secure:

<!-- This section will be updated as we receive security reports -->

*No security issues reported yet. Be the first!*

## Contact

- **Security issues**: swapnil@opensre.in
- **General questions**: swapnil@opensre.in
- **Community**: [Slack](https://join.slack.com/t/opensre/shared_invite/zt-3ojlxvs46-xuEJEplqBHPlymxtzQi8KQ) | [Discussions](https://github.com/swapnildahiphale/OpenSRE/discussions)

## Learn More

- [Deployment Guide](docs/DEPLOYMENT.md) — production deployment best practices
- [Architecture](docs/ARCHITECTURE.md) — system design and security architecture
- [Enterprise Ready](README.md#enterprise-ready) — advanced security features
