# Microsoft Entra SSO — Web Console

Operator guide for signing into the OpenSRE web console with Microsoft Entra ID (Azure AD). Token paste remains as break-glass.

This is **not** the Teams bot app. Teams uses a separate Entra registration (`TEAMS_APP_ID`). See [`teams-bot/README.md`](../teams-bot/README.md).

**Time required:** ~20 minutes the first time (Entra app + Admin → SSO).

---

## Which login path to use

OpenSRE has two OIDC-related paths. Use **one**.

| Path | When | Helm / env |
|------|------|------------|
| **Admin → SSO** (this guide) | Entra **Web** (confidential) app; Authorization Code without PKCE | Keep `services.webUi.oidc.enabled=false`. Do **not** set `WEB_UI_OIDC_*`. |
| Helm / `WEB_UI_OIDC_*` PKCE | SPA-style public client with PKCE | Separate product path. Leave it off for Entra Web apps. |

Admin → SSO stores tenant and client id in `sso_configs`. The client secret is **not** stored in the database — set `SSO_CLIENT_SECRET` on config-service only. Those values must not land in git, Helm overlays, or committed runbooks.

---

## 1. Create the Entra app

Azure Portal → **Microsoft Entra ID** → **App registrations** → **New registration**.

1. **Name** — e.g. `OpenSRE Web Console`
2. **Supported account types** — *Accounts in this organizational directory only* (single tenant)
3. **Redirect URI** — platform **Web** (not SPA):
   - Production: `https://<web-ui-host>/api/auth/callback`
   - Local Docker Compose: `http://localhost:3002/api/auth/callback`
4. Register, then note:
   - **Application (client) ID**
   - **Directory (tenant) ID**

### Authentication

App → **Authentication**:

- Platform is **Web** only (0 SPA, public client flows **disabled**)
- Implicit grant / hybrid: **ID tokens** and **Access tokens** unchecked
- Add every public origin you will actually use as a redirect URI. A mismatch returns `AADSTS500112`.

### Client secret

App → **Certificates & secrets** → **New client secret**. Copy the **Value** once. Treat it like a password.

### API permissions

App → **API permissions** → Microsoft Graph **delegated**:

- `openid`
- `email`
- `profile`
- `User.Read`

Grant admin consent for the tenant.

### Optional: email claim

Entra often omits `email` from Graph `/oidc/userinfo`. OpenSRE also accepts `preferred_username` / `upn` when they look like emails.

Optional portal follow-up (not required): **Token configuration** → add optional claim `email` on ID and access tokens.

---

## 2. OpenSRE environment

| Variable | Where | Purpose |
|----------|--------|---------|
| `WEB_UI_SSO_ORG_ID` | web-ui | Org whose `sso_configs` row drives the login button. Helm sets this from `global.configService.orgId`. Compose default: `local`. If unset, the SSO button stays hidden. |
| `WEB_UI_PUBLIC_BASE_URL` | web-ui | Browser origin used as Entra `redirect_uri`. Required when the process binds `0.0.0.0` (Docker/K8s). Helm uses `services.webUi.oidc.publicBaseUrl` if set, otherwise `https://<ingress.host>`. Compose default: `http://localhost:3002`. |
| `WEB_UI_COOKIE_SECURE` | web-ui | `1` on HTTPS so the session cookie is `Secure`. Keep `0` for http://localhost. |
| `SSO_DEFAULT_TEAM_NODE_ID` | config-service | Team node SSO sessions attach to (default `default`). |
| `SSO_CLIENT_SECRET` | config-service | Entra/OIDC client secret (env only — not stored in DB or Admin form). |
| `TOKEN_PEPPER` | config-service | Must match the pepper used to hash team tokens. SSO cookies are ordinary team tokens. |
| `SSO_ALLOWED_DOMAINS` | seed / Admin form | Comma-separated email domains. Include **every** domain Entra may return (work UPN and mail nickname can differ). |

Local seed (optional): if `SSO_AZURE_TENANT_ID` and `SSO_AZURE_CLIENT_ID` are set in root `.env`, `seed_demo_data.py` writes `sso_configs` for the seeded org. Set `SSO_CLIENT_SECRET` separately on config-service. Production should use the Admin form for tenant/client id, not env seed.

Do not reuse Azure Monitor / Teams variables (`AZURE_CLIENT_SECRET`, `TEAMS_APP_PASSWORD`).

---

## 3. Enable in Admin → SSO

1. Sign in with the **admin token** (break-glass).
2. Open **Admin → SSO**.
3. Provider: **Microsoft Entra ID**.
4. Paste tenant ID and client ID from the Entra app.
5. Confirm **Client secret** shows `SSO_CLIENT_SECRET detected` on config-service (set the env var in compose/K8s — not in this form).
6. Scopes: `openid email profile`
7. Allowed domains: your company email domain(s)
8. Enable and save.

Helm already wires `WEB_UI_SSO_ORG_ID` and `WEB_UI_PUBLIC_BASE_URL` on self-hosted installs with Ingress. Paste Entra tenant/client id in the Admin form and put `SSO_CLIENT_SECRET` in the config-service secret — not in `values.yaml`.

---

## 4. Local Docker Compose

```bash
# .env — placeholders only; never commit real tenant/client/secret values
WEB_UI_SSO_ORG_ID=local
WEB_UI_PUBLIC_BASE_URL=http://localhost:3002
SSO_DEFAULT_TEAM_NODE_ID=default
SSO_CLIENT_SECRET=
SSO_AZURE_TENANT_ID=
SSO_AZURE_CLIENT_ID=
SSO_ALLOWED_DOMAINS=example.com
SSO_SCOPES=openid email profile
```

Add `http://localhost:3002/api/auth/callback` as a **Web** redirect URI on the Entra app. Set `SSO_CLIENT_SECRET` to the Entra app secret value. Then `make dev` and open http://localhost:3002.

If you skip the seed env vars, leave them empty and fill **Admin → SSO** (tenant + client id) after logging in with the admin token.

---

## 5. Kubernetes (self-hosted chart)

Keep `services.webUi.oidc.enabled: false`.

The chart sets:

- `WEB_UI_SSO_ORG_ID` = `global.configService.orgId`
- `WEB_UI_PUBLIC_BASE_URL` = `services.webUi.oidc.publicBaseUrl` or `https://<ingress.host>`

Put `SSO_CLIENT_SECRET` and `TOKEN_PEPPER` in the config-service secret (`opensre-config-service-env` on the simple profile). After deploy:

1. Sign in with the admin token
2. **Admin → SSO** → paste Entra tenant + client id → enable
3. Incognito: **Continue with Microsoft Entra ID** → land on `/team`

SSO sessions share the org’s working team (`default` unless you set `SSO_DEFAULT_TEAM_NODE_ID`).

---

## Smoke

- Incognito window → Microsoft button → Entra login → `/team` dashboard
- Token login still works
- `/api/identity` returns the SSO user’s org/team (not `Invalid token`)

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| No Microsoft button on login | `WEB_UI_SSO_ORG_ID` unset, or Admin → SSO not enabled for that org |
| `AADSTS500112` / redirect URI mismatch | Entra app is missing the exact `redirect_uri`. Inside Docker/K8s, set `WEB_UI_PUBLIC_BASE_URL` so the callback is not `http://0.0.0.0:...` |
| `Email domain '…' not allowed` | Add that domain to **Allowed domains** (Entra may return a different domain than the UPN you expect) |
| Lands on `/` with no session after Entra | Cookie dropped on a cross-site 302. Current callback returns 200 HTML then navigates in-page. Rebuild `web-ui` if you are on an older image. |
| `Invalid token` right after SSO | `TOKEN_PEPPER` used to hash the SSO token does not match `/api/v1/auth/me` |
| Token exchange 500 / secret not configured | `SSO_CLIENT_SECRET` missing on config-service |
| Teams login / bot confusion | Wrong Entra app. Web console callback is `/api/auth/callback`. Teams uses `/api/messages` and `TEAMS_*`. |
