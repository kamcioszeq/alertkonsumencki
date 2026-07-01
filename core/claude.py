"""Claude API client — platform-agnostic text generation."""
import httpx
import config


async def ask_claude(text: str, source: str, instruction: str, *, system_prompt: str = None) -> str:
    """Ask Claude to transform `text` per `instruction`. Returns the generated text.

    `system_prompt` is supplied by the calling platform (e.g. the Telegram consumer-alert
    prompt). If None, no system prompt is sent.
    """
    prompt = (
        f"Źródło: {source}\n\n"
        f"Oryginalny tekst:\n{text}\n\n"
        f"Instrukcja: {instruction}"
    )

    body = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt is not None:
        body["system"] = system_prompt

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": config.CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
            timeout=30,
        )

    data = response.json()
    if data.get("content"):
        texts = [b["text"] for b in data["content"] if b["type"] == "text"]
        return "\n".join(texts)
    return f"Błąd Claude: {data.get('error', {}).get('message', 'unknown')}"
