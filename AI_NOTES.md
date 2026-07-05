# AI Notes

## Tools and models used

Claude Code (Sonnet 5) was used throughout — as an agent with shell,
file-edit, and browser-verification tooling, not just a chat autocomplete.
It scaffolded the FastAPI backend (Ed25519 verification, dedup, deferred-ack
background processing, dashboard/auth routes) and the React dashboard, then
was used interactively for the rest of the build: implementing the
per-server "connect a Discord server + pick a channel" flow end-to-end,
redesigning the dashboard UI, diagnosing two production bugs against the
live Neon DB and live Discord bot, and walking through GitHub/Render/Vercel
deployment step by step (I did the account creation and dashboard clicks;
Claude ran the git/API/deploy commands and verified each step against the
real Discord API, Neon DB, and deployed URLs before calling it done).
Roughly 80-85% of the code is AI-written, with me driving priorities,
running the app for real in Discord, and reporting back what I saw
(including screenshots) so mistakes got caught against real behavior
instead of assumptions.

I didn't use a separate CLAUDE.md/AGENTS.md/.cursorrules file — all
steering happened conversationally in the coding session itself.

## Key decisions I made myself

1. **Render for the backend, Vercel for the frontend — not everything on
   one platform.** The interaction flow depends on a deferred ack followed
   by background work (reply, mirror, optional AI call) that keeps running
   *after* the HTTP response is sent. Vercel's Python support is
   short-lived serverless functions that can be torn down right after
   responding, which would silently kill that background work. Render's
   free "Web Service" runs one continuously-alive process, so the
   background-task design works exactly as built. I chose to keep the
   working architecture and split hosting by service instead of
   rearchitecting around a host's constraints.
2. **Admin picks a real Discord channel from a live dropdown, not a pasted
   ID.** Since the bot already needs a token, I had the backend call
   Discord's own API to list the guilds the bot is in and each guild's text
   channels, so connecting a server is a real pick-from-a-list flow instead
   of the admin having to go find and copy a raw channel ID.
3. **Per-guild mirror routing over a single global webhook.** Instead of
   one `MIRROR_WEBHOOK_URL` env var for the whole app, each connected
   server gets its own `ServerConfig` row (Discord channel or Slack
   webhook), so multiple servers stay isolated rather than all sharing one
   notification destination.

## The hardest bug / wrong turn

The hardest one only showed up under real load, not in any test: running
`/status` in Discord came back **"The application didn't respond in
time."** The server logs showed the interaction handler crashed on its
very first database query with
`sqlalchemy.exc.OperationalError: SSL connection has been closed
unexpectedly`. Root cause: Neon (serverless Postgres) closes idle
connections after a few minutes, and the SQLAlchemy engine had no way to
detect a dead pooled connection before reusing it — so the very first
request after some idle time crashed instead of reconnecting, and that
crash happened *before* Discord's 3-second ack could be sent. It's exactly
the "should not silently lose an interaction if your own service is briefly
unavailable" failure mode called out in the brief, and I hit it for real.

Fixed two ways: (1) `pool_pre_ping=True` + `pool_recycle=300` on the engine
so a dead connection gets detected and transparently replaced before use,
and (2) hardened the interaction handler itself so a DB failure during the
dedup check still acks Discord (skipping background processing rather than
raising) instead of turning a database hiccup into a visible Discord
failure. Added a unit test (`test_safe_dedup_and_log_tolerates_db_outage`)
that simulates exactly this failure so it can't silently regress.

A second, smaller one during deployment: Render's build succeeded but
`uvicorn` crashed on startup with
`ImportError: ...psycopg2/_psycopg...so: undefined symbol:
_PyInterpreterState_Get`. Render defaulted to Python 3.14, and the pinned
`psycopg2-binary==2.9.9`'s compiled extension isn't compatible with that
interpreter's ABI. Fixed by pinning `.python-version` to `3.11.9` — the
exact version already tested against locally — instead of chasing a newer
psycopg2/Python combination blind.

One more honest one, not a bug but a real mistake: an earlier scaffolding
pass left a **real, live Discord bot token and a real Neon database
password** sitting in `backend/.env.example` — the exact file meant to be
committed to a public repo. It was caught before anything was pushed (by
decoding the token and confirming it matched the live application ID), the
file was scrubbed to placeholders, and a proper `.gitignore` was added. The
credentials still got rotated-worthy exposure during local testing, which
is a good reminder that "it's just a placeholder file" is worth verifying,
not assuming.

## What I'd improve with more time

- Buttons and the `/report` modal: handler code exists for
  `MESSAGE_COMPONENT`/`MODAL_SUBMIT` interactions, but nothing currently
  sends a button or opens a modal, so that path is untested against a real
  interaction — either wire it up for real or remove the dead code.
- Test the AI summarize/tag stretch goal against a real `GROQ_API_KEY` (the
  code path exists and fails gracefully without one, but isn't verified
  against the live Groq API).
- Structured, queryable observability — a visible retry/failure history in
  the dashboard beyond the per-row status/error fields that exist today.
- Move the admin login off a single shared username/password to something
  more real if this ever had more than one admin.
