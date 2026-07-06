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

    if not config.CLAUDE_API_KEY:
        return "Błąd Claude: brak CLAUDE_API_KEY"

    try:
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
        if response.status_code >= 400:
            try:
                data = response.json()
                error_msg = data.get("error", {}).get("message", response.text)
            except ValueError:
                error_msg = response.text
            return f"Błąd Claude: {response.status_code} {error_msg}"
        data = response.json()
    except httpx.HTTPError as e:
        return f"Błąd Claude: brak połączenia z API ({type(e).__name__})"
    except Exception as e:
        return f"Błąd Claude: {type(e).__name__}: {e}"

    if data.get("content"):
        texts = [b["text"] for b in data["content"] if b["type"] == "text"]
        return "\n".join(texts)
    return f"Błąd Claude: {data.get('error', {}).get('message', 'unknown')}"
