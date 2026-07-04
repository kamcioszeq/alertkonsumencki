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
  F -->|Dostosuj| G[Adjust: Bardziej formalny / Mniej formalny / Techniczny / Sugestia / Skróć 20-70% / Edytuj]
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

## GIS crawler → Telegram handoff

The crawler and the bot are **separate processes** (likely separate containers). Only the bot
talks to Telegram interactively (it owns the button state), so the crawler doesn't message
Telegram directly — it drops new warnings into a **file queue** (`queue/`, a shared volume). The
bot watches that queue and, for each new warning, DMs you the alert image + a "Wygenerować post?"
prompt. This keeps the handoff decoupled and restart-safe, and the click-to-generate/edit state
lives entirely in the bot.

```mermaid
flowchart LR
  crawler[GIS crawler] -->|new warning JSON| queue[(queue/ dir)]
  manual[Reviewer drops link] --> ingest
  queue -->|bot watches| ingest[ingest → 🔍 Generuj?]
  ingest --> review[generate · edit · publish]
  review -->|image + text| channel[broadcast channel]
```

The generated draft stays a **text message** (easy to edit/regenerate); the static
`assets/alert.png` is attached to the handoff message and to the final published post (as a photo
caption when ≤1024 chars, otherwise image + text).
