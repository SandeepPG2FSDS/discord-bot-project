# AI Notes

## Tools and models used

_e.g. Claude (Sonnet) via claude.ai for scaffolding and architecture,
GitHub Copilot for inline completions while wiring up the frontend, etc.
Roughly estimate the split of AI-written vs hand-written code._

## Key decisions I made myself

1. _e.g. Chose deferred response + background task over doing everything
   synchronously, to respect Discord's 3-second window and keep the AI/mirror
   calls from blocking the ack._
2. _e.g. Chose SQLAlchemy + SQLite-by-default/Postgres-in-prod so the app
   runs with zero setup locally but scales to Neon in production._
3. _e.g. ..._

## The hardest bug / wrong turn

_Be specific and honest here — this is the section they read most closely.
What did the AI suggest that was wrong, how did you notice, how did you fix
it?_

## What I'd improve with more time

- Full per-server config isolation for multi-server support.
- Wire up buttons (MESSAGE_COMPONENT) and a modal form for `/report`.
- Structured logging + a visible retry/failure history in the dashboard.
- Tests for the signature verification and dedup logic.
