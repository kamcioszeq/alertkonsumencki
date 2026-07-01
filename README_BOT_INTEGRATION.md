# Bot integration — Telegram setup

Everything needed to stand up the Telegram side and fill `.env`.

## 1. Create the bot (get `BOT_TOKEN`)

1. Open [@BotFather](https://t.me/BotFather) in Telegram.
2. Send `/newbot`, choose a display name and a username ending in `bot`.
3. BotFather returns a token like `123456789:AAE…`. That is your **`BOT_TOKEN`**.
4. (Optional) `/setprivacy` only matters for *groups*. You review by DMing the bot directly, so
   you can leave privacy mode on — bots always receive their direct messages.

## 2. Get API credentials (`API_ID`, `API_HASH`)

1. Log in at **https://my.telegram.org** with your phone number.
2. Open **API development tools**, create an app (any name).
3. Copy **`API_ID`** (a number) and **`API_HASH`** (a hex string).

> Telethon needs these even for a bot login; there is **no phone/2FA prompt** because we start
> with the bot token.

## 3. Set up the two endpoints

- **Internal review = your direct chat with the bot.** Open the bot in Telegram and press
  **Start** (or send any message) so it is allowed to DM you back. You'll paste links / send
  `/test` here and accept or decline drafts. No group needed — `INTERNAL_CHAT_ID` is simply **your
  own numeric user ID**, and you can leave it blank to default to your `REVIEWER_IDS`.
- **Broadcast channel** (`BROADCAST_CHANNEL_ID`): the *public* channel where approved alerts are
  published. Add the bot as an **administrator** here (post-messages permission).

## 4. Get your user ID and the channel ID

- **Your user ID** (`REVIEWER_IDS`, and implicitly `INTERNAL_CHAT_ID`): message
  [@userinfobot](https://t.me/userinfobot) → it replies with your numeric id. Comma-separate for
  multiple reviewers (drafts go to the first one's DM).
- **Broadcast channel ID** (`BROADCAST_CHANNEL_ID`): add [@userinfobot](https://t.me/userinfobot)
  (or `@JsonDumpBot`) to the channel, or forward a channel message to it. Channel IDs are
  **negative** and start with `-100…` (e.g. `-1001234567890`) — use the full value.

Quick sanity check: run `main.py`, DM the bot `/test`, and watch the console — the `[START]` line
prints the ids the bot is actually using.

## 5. Fill `.env`

```
cp .env.example .env
```

| Variable | Where it comes from |
|---|---|
| `API_ID`, `API_HASH` | my.telegram.org (step 2) |
| `BOT_TOKEN` | @BotFather (step 1) |
| `REVIEWER_IDS` | your numeric id(s) from @userinfobot |
| `INTERNAL_CHAT_ID` | leave blank (defaults to your DM) — or your user id to be explicit |
| `BROADCAST_CHANNEL_ID` | public channel id (step 4, `-100…`) |
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

- **Bot never DMs you / `chat not found` on your id** — you haven't pressed **Start** on the bot,
  so it isn't allowed to message you. Send it any message first.
- **`Cannot find any entity` / `chat not found` on the channel** — wrong id or missing `-100`
  prefix; the bot must also be an admin of the broadcast channel.
- **Publish does nothing / error** — the bot lacks *post messages* permission in the broadcast channel.
- **Buttons do nothing** — your user id isn't in `REVIEWER_IDS`.
- **`ValueError: invalid literal for int()`** — an id/`API_ID` in `.env` is empty or non-numeric.
