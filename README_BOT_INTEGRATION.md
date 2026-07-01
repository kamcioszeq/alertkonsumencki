# Bot integration — Telegram setup

Everything needed to stand up the Telegram side and fill `.env`.

## 1. Create the bot (get `BOT_TOKEN`)

1. Open [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/newbot`, choose a display name and a username ending in `bot`.
3. BotFather returns a token like `123456789:AAE…`. That is your **`BOT_TOKEN`**.
4. Send `/setprivacy` → select the bot → **Disable**, so the bot can read messages in groups
   (needed if your internal chat is a group and you paste links there).

## 2. Get API credentials (`API_ID`, `API_HASH`)

1. Log in at **https://my.telegram.org** with your phone number.
2. Open **API development tools**, create an app (any name).
3. Copy **`API_ID`** (a number) and **`API_HASH`** (a hex string).

> Telethon needs these even for a bot login; there is **no phone/2FA prompt** because we start
> with the bot token.

## 3. Create the two chats

- **Internal review chat** (`INTERNAL_CHAT_ID`): a *private* group or channel where drafts appear
  and you press buttons. A **group** is the easiest (buttons + replies work well).
- **Broadcast channel** (`BROADCAST_CHANNEL_ID`): the *public* channel where approved alerts are
  published.

Add your bot as an **administrator in both** (it must be able to post messages; in the internal
chat it also needs to send messages and edit its own).

## 4. Get the chat IDs and your reviewer ID

- **Your user ID** (`REVIEWER_IDS`): message [@userinfobot](https://t.me/userinfobot) → it replies
  with your numeric id. Add more ids comma-separated for multiple reviewers.
- **Chat IDs**: add [@userinfobot](https://t.me/userinfobot) (or `@JsonDumpBot`) to the chat, or
  forward a message from the channel to it. Channel/supergroup IDs are **negative** and start with
  `-100…` (e.g. `-1001234567890`). Use the full value including the `-100`.

Quick sanity check without extra bots: temporarily run `main.py`, send `/test` in the internal
chat, and watch the console — the `[START]` line prints the ids the bot is actually using.

## 5. Fill `.env`

```
cp .env.example .env
```

| Variable | Where it comes from |
|---|---|
| `API_ID`, `API_HASH` | my.telegram.org (step 2) |
| `BOT_TOKEN` | @BotFather (step 1) |
| `INTERNAL_CHAT_ID` | internal group/channel id (step 4, `-100…`) |
| `BROADCAST_CHANNEL_ID` | public channel id (step 4, `-100…`) |
| `REVIEWER_IDS` | your numeric id(s) from @userinfobot |
| `CLAUDE_API_KEY` | Anthropic console |
| `CLAUDE_MODEL` | optional; defaults to `claude-haiku-4-5-20251001` |

## 6. Run

```bash
./venv/bin/pip install -r requirements.txt
./venv/bin/python main.py
```

Then in the internal chat send `/test` — you should get a message with a **🔍 Generuj post**
button. Click it to generate a draft.

## Troubleshooting

- **Bot doesn't react in a group** — privacy mode still on (step 1.4) or bot isn't an admin.
- **`Cannot find any entity` / `chat not found`** — wrong id or missing `-100` prefix; the bot must
  also be a member/admin of that chat.
- **Publish does nothing / error** — the bot lacks *post messages* permission in the broadcast channel.
- **Buttons do nothing** — your user id isn't in `REVIEWER_IDS`.
- **`ValueError: invalid literal for int()`** — an id/`API_ID` in `.env` is empty or non-numeric.
