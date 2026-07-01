# Why it works this way

This bot exists to turn a **raw source** (a GIS/gov.pl alert page, or pasted text) into a
**polished, reviewed consumer-alert post** on a public Telegram channel — with a human in the loop.

## Two places: your DM → broadcast

- **Internal review = your direct chat with the bot.** You paste links / send `/test`, the bot
  DMs back drafts, and you accept or decline right there. Nothing here is public.
- **Broadcast channel** = the shop window. Only approved, final alerts land here.

Keeping the workshop (your DM) separate from the channel means mistakes never reach subscribers.

## One bot, not two

We don't monitor other Telegram channels, so there's no need for a *user account* (userbot). A
single **bot** — admin in both chats — posts drafts, handles button clicks, and publishes. Login is
just the bot token: no phone number, no 2FA.

## Click-to-generate (no auto, no preview card)

A dropped link doesn't immediately burn a Claude call. It gets a single **🔍 Generuj post** button;
generation happens only when a reviewer clicks. There's intentionally **no raw-text preview card** —
just the trigger, then the finished draft.

## Message flow

```mermaid
flowchart TD
  A[Reviewer drops URL or /test in internal chat] --> B[ingest: apply_url_fields]
  B --> C[Message with 🔍 Generuj post / Odrzuć]
  C -->|click 🔍| D[url_read: fetch_article via trafilatura]
  D --> E[ask_claude + consumer-alert SYSTEM_PROMPT → draft]
  E --> F[Draft in internal chat: ✅ OK / Dostosuj / Odrzuć]
  F -->|Dostosuj| G[Rephrase: Bardziej formalny / Mniej formalny / Techniczny / Sugestia / Edytuj]
  G --> F
  F -->|✅ OK → Publikuj| H[publish_to_channel → BROADCAST_CHANNEL_ID]
  F -->|Odrzuć| X[Discard]
```

`/test` seeds a sample alert and `/new <text>` injects arbitrary text; both share the same path, so
plain-text items (no URL) are summarized directly instead of being fetched.

## Module architecture

Shared, platform-agnostic code lives in `core/`; anything Telegram-specific is isolated in
`telegram/`. New platforms (e.g. `facebook/`) are added as sibling directories that reuse `core/`
— without touching the Telegram code.

```mermaid
flowchart LR
  main[main.py] --> tg

  subgraph tg [telegram/]
    ingest[ingest.py] --> urlh[url_handlers.py]
    urlh --> handlers[handlers.py]
    handlers --> publish[publish.py]
    prompts[prompts.py]
    buttons[buttons.py]
    format[format.py]
  end

  subgraph core [core/ — shared]
    claude[claude.py]
    state[state.py]
    article[article.py]
  end

  tg --> core
  fb[facebook/ · future] -.-> core
```

## State & restarts

`core/state.py` keeps two dicts — `pending_adoption` (items awaiting 🔍) and `pending_posts`
(drafts under review) — and mirrors every change to `state.json`. If the bot restarts, in-flight
drafts survive (Telethon message objects are runtime-only and simply re-fetched on demand).

## Future: automatic GIS crawler

Today a human drops the link. Later, a crawler that watches GIS/gov.pl will call the same
`ingest_alert()` entry point when a new notification appears — so the review/publish machinery
downstream doesn't change at all.

```mermaid
flowchart LR
  crawler[GIS crawler · future] --> ingest[ingest_alert]
  manual[Reviewer drops link · today] --> ingest
  ingest --> review[review + publish flow]
```
