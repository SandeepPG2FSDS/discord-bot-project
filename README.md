# Discord Slash-Command Bot

A web app + Discord bot that handles slash commands via Discord's HTTP
Interactions API, logs them, replies in Discord, mirrors a notification to a
second channel, and exposes an admin dashboard to view the log and configure
command behavior.

## What it does

- Admin logs into the dashboard, clicks an invite link to add the bot to a
  Discord server, then picks that server and a channel from dropdowns
  (fetched live from Discord using the bot token) — or pastes a Slack
  webhook instead. That choice is saved per-server (`ServerConfig`).
- `/report <text>` and `/status` slash commands, handled by a FastAPI
  interactions endpoint (no always-on gateway bot required).
- Every request's Ed25519 signature is verified before anything else runs.
- Interactions are deduped by `interaction_id` so retried deliveries don't
  get processed twice.
- The endpoint acknowledges Discord immediately (deferred response) and does
  the real work — rule application, optional AI summarization, mirroring —
  in a background task, respecting the ~3 second response window.
- The mirror notification is routed per-guild: the Discord channel or Slack
  webhook the admin picked for that server, falling back to a global
  `MIRROR_WEBHOOK_URL` env var if no server has been connected yet.
- A React dashboard (behind admin login) shows a live command log, the
  connected-servers list, and lets the admin edit each command's reply
  template and toggle mirroring/AI, globally or per connected server.

## Project structure

```
backend/    FastAPI app, DB models, Discord verification, command registration script
frontend/   React (Vite) admin dashboard
```

## Running locally

### 1. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your values, see below
uvicorn app.main:app --reload --port 8000
```

### 2. Register slash commands

```bash
cd backend
python register_commands.py
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # set VITE_API_URL to your backend URL
npm run dev
```

### 4. Point Discord at your endpoint

Discord requires a **public** HTTPS URL for the Interactions Endpoint — it
will not accept `localhost`. For local testing, tunnel your backend with a
tool like `ngrok` (`ngrok http 8000`) and paste the HTTPS URL + `/interactions`
into your Discord application's "Interactions Endpoint URL" field
(Developer Portal → your app → General Information). Discord sends a PING
immediately when you save; the endpoint must return a PONG for it to accept
the URL.

## Environment variables

See `backend/.env.example`. Summary:

| Variable | Where to get it |
|---|---|
| `DISCORD_PUBLIC_KEY` | Developer Portal → General Information |
| `DISCORD_BOT_TOKEN` | Developer Portal → Bot → Reset Token |
| `DISCORD_APPLICATION_ID` | Developer Portal → General Information |
| `MIRROR_WEBHOOK_URL` | A Slack Incoming Webhook URL, or a Discord channel webhook URL (Channel Settings → Integrations → Webhooks) |
| `DATABASE_URL` | Neon or Supabase Postgres connection string (falls back to local SQLite if unset) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Any throwaway credentials for the dashboard login |
| `JWT_SECRET` | Any long random string |
| `GROQ_API_KEY` | Optional — only needed for the AI summarize/tag stretch goal, free at console.groq.com |

## Deployment

- **Backend**: deployed to Render (free tier). Build command
  `pip install -r requirements.txt`, start command
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Environment variables
  set in Render's dashboard, not committed to the repo.
- **Frontend**: deployed to Vercel/Netlify (free tier), with `VITE_API_URL`
  pointed at the Render backend URL.
- **Database**: Neon free-tier Postgres, connection string set as
  `DATABASE_URL` on the backend.
- **Discord Interactions Endpoint URL**: set to
  `https://<your-render-app>.onrender.com/interactions`.

Deployed URL: _fill in after deploying_
Repo: _fill in_

## Testing it

1. Log into the dashboard, click "Add the bot to your server", pick your
   server from the Developer Portal invite screen.
2. Back in the dashboard, click "Refresh server list", pick that server,
   then pick a channel (or paste a Slack webhook) and click Connect.
3. In your test Discord server, run `/status` or `/report some text`.
4. The bot acknowledges immediately ("thinking...") then edits in the real
   reply within a couple seconds.
5. Check the channel/Slack you connected for the mirrored notification.
6. The command shows up in the dashboard's log table; the config panel lets
   you edit that command's behavior globally or just for this server.

## Known limitations / not implemented

- Buttons/modals (MESSAGE_COMPONENT, MODAL_SUBMIT) are acknowledged but no
  command currently sends a button or opens a modal, so that code path is
  untested against a real interaction.
- The "connect a server" flow lists guilds the bot is already in (via the
  bot token) rather than using a full Discord OAuth user-login flow — good
  enough for a single admin, not built for self-serve multi-tenant signup.
