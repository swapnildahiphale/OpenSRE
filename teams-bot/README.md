# OpenSRE Teams Bot

Self-hosted Microsoft Teams bot for OpenSRE incident investigations. Uses the
[Microsoft Teams SDK for Python](https://pypi.org/project/microsoft-teams-apps/) to
receive channel @mentions and personal messages, stream investigation progress,
and collect clarifying answers via Adaptive Cards.

## Environment variables

Set these in the repo root `.env` (see `env.example`):

| Variable | Description |
|----------|-------------|
| `TEAMS_APP_ID` | Entra / Azure Bot application (client) ID |
| `TEAMS_APP_PASSWORD` | Client secret |
| `TEAMS_TENANT_ID` | Azure AD tenant ID |
| `SRE_AGENT_URL` | sre-agent base URL (default `http://localhost:8000`) |
| `INVESTIGATE_AUTH_TOKEN` | Bearer token for `/investigate` and `/answer` |
| `WEB_UI_PUBLIC_BASE_URL` | Web console origin for “View in OpenSRE” links on final replies (e.g. `http://localhost:3002`) |
| `PORT` | HTTP listen port (default `3978`) |

`config.py` maps `TEAMS_*` to the SDK's `CLIENT_ID`, `CLIENT_SECRET`, and
`TENANT_ID` at startup. If any of the three Teams credentials are missing, `app.py`
exits cleanly with code 0 (no crash loop in Docker).

## Local development

Start the core stack, then opt in to the Teams bot:

```bash
make dev
make dev-teams
```

Or directly:

```bash
docker compose -f docker-compose.yml --profile teams up -d --build teams-bot
```

The bot listens on **port 3978**. Check logs for `Starting OpenSRE teams-bot`.

## Azure Bot messaging endpoint

Teams delivers activities over HTTPS. For local dev, expose port 3978 with a
public tunnel:

```bash
cloudflared tunnel --protocol http2 --url http://localhost:3978
# or: ngrok http 3978
```

Verify: `curl -s -o /dev/null -w '%{http_code}\n' https://<tunnel-host>/api/messages` → **405**.

In [Azure Bot](https://portal.azure.com) → **Configuration**, set **Messaging endpoint** to
`https://<tunnel-host>/api/messages`. Enable the **Microsoft Teams** channel.

**Web Chat** (Azure Bot → Test in Web Chat) validates the full loop without a Teams license or sideload zip.

## Sideload the Teams app (optional)

Only needed for real Teams UI — not for Web Chat or routine code deploys.

1. Copy `manifest/manifest.json` and replace `{{TEAMS_APP_ID}}` with your app ID.
2. Icons are already in `manifest/` (`color.png` 192×192, `outline.png` 32×32) from the OpenSRE spinner logo.
3. Build the zip:

   ```bash
   cd teams-bot/manifest
   zip -r ../opensre-teams-app.zip manifest.json color.png outline.png
   ```

4. In **Teams** → **Apps** → **Manage your apps** → **Upload a custom app**, upload the zip.

Full onboarding checklist, licensing notes, and troubleshooting:
[`docs/TEAMS_SETUP.md`](../docs/TEAMS_SETUP.md).

## Self-hosted production

Point the Azure Bot messaging endpoint at `https://<your-host>/api/messages` (POST only; GET should return 405). Helm can give the bot its own Ingress host via a private site overlay. Site hostnames and overlay paths stay in the private `deploy/` runbook, not here.

## Behavior

- **Channel / group chat:** bot must be @mentioned; mention text is stripped.
- **Personal chat / Web Chat:** no mention required; `help` or `status` returns a welcome card.
- **Investigations:** message handler awaits the SSE runner so `ctx.stream` stays
  valid for live progress updates (humanized tool labels; current thought last).
- **Final reply:** 1:1 / Web Chat use an Adaptive Card with an optional footer link; channel/group threads use plain text with the same inline link.
- **Questions:** Adaptive Card submit verb `opensre.submit_answers` posts answers to
  sre-agent `/answer`.

## Tests

```bash
cd teams-bot
uv sync
uv run pytest -v
uv run ruff check app.py bot_handlers.py tests/test_bot_handlers.py
```
