"""Publish alert posts to a Facebook Page via Graph API."""
import os
import re
from html import unescape
from typing import Optional, Tuple

import httpx

import config


def html_to_plain(text: str) -> str:
    """Strip Telegram HTML markup for Facebook caption."""
    value = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = unescape(value).replace("\r\n", "\n")
    return re.sub(r"\n{3,}", "\n\n", value).strip()


async def publish_to_facebook(text: str, *, image_path: Optional[str] = None) -> Tuple[bool, str]:
    """Post text (+ optional image) to the configured Facebook Page."""
    if not config.FB_PAGE_ACCESS_TOKEN or not config.FB_PAGE_ID:
        return False, "Brak FB_PAGE_ACCESS_TOKEN lub FB_PAGE_ID w .env"

    caption = html_to_plain(text)
    if not caption:
        return False, "Pusty tekst posta"

    page_id = config.FB_PAGE_ID
    token = config.FB_PAGE_ACCESS_TOKEN
    base = f"https://graph.facebook.com/v25.0/{page_id}"

    async with httpx.AsyncClient(timeout=60) as client:
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                resp = await client.post(
                    f"{base}/photos",
                    data={"caption": caption, "access_token": token},
                    files={"source": (os.path.basename(image_path), f)},
                )
        else:
            resp = await client.post(
                f"{base}/feed",
                data={"message": caption, "access_token": token},
            )

    data = resp.json()
    if resp.status_code >= 400:
        err = data.get("error", {})
        return False, err.get("message", str(data))

    post_id = data.get("id") or data.get("post_id", "")
    return True, post_id or "OK"


async def comment_on_facebook(
    object_id: str, text: str, *, image_path: Optional[str] = None,
) -> Tuple[bool, str]:
    """Dodaj komentarz (+ opcjonalny obrazek) pod istniejącym postem/zdjęciem FB."""
    if not config.FB_PAGE_ACCESS_TOKEN or not config.FB_PAGE_ID:
        return False, "Brak FB_PAGE_ACCESS_TOKEN lub FB_PAGE_ID w .env"
    if not object_id:
        return False, "Brak ID posta do skomentowania"

    message = html_to_plain(text)
    token = config.FB_PAGE_ACCESS_TOKEN
    api = "https://graph.facebook.com/v25.0"

    async with httpx.AsyncClient(timeout=60) as client:
        data = {"message": message, "access_token": token}

        # Obrazek w komentarzu: najpierw wgraj jako nieopublikowane zdjęcie, potem podepnij
        # przez attachment_id (endpoint /comments nie przyjmuje pliku bezpośrednio).
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                up = await client.post(
                    f"{api}/{config.FB_PAGE_ID}/photos",
                    data={"published": "false", "access_token": token},
                    files={"source": (os.path.basename(image_path), f)},
                )
            up_data = up.json()
            if up.status_code < 400 and up_data.get("id"):
                data["attachment_id"] = up_data["id"]
            else:
                print(f"[PROMO_FB] Nie udało się wgrać QR, komentarz bez obrazka: {up_data}")

        resp = await client.post(f"{api}/{object_id}/comments", data=data)

    result = resp.json()
    if resp.status_code >= 400:
        err = result.get("error", {})
        return False, err.get("message", str(result))

    return True, result.get("id", "OK")
