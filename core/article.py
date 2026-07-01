"""URL detection + article extraction (text-only) via trafilatura.

Platform-agnostic: a fetched article can feed any platform's post generator.
"""
import asyncio
import re
import httpx

URL_RE = re.compile(r'https?://[^\s<>"\]]+', re.I)
FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AlertKonsumenckiBot/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def extract_urls(text: str) -> list:
    if not text:
        return []
    return [u.rstrip(".,;:)") for u in URL_RE.findall(text)]


def has_url(text: str) -> bool:
    return bool(extract_urls(text))


def split_url_and_comment(text: str) -> tuple:
    """Return (first_url, user_comment_without_urls)."""
    if not text:
        return None, ""
    urls = extract_urls(text)
    if not urls:
        return None, text.strip()
    first_url = urls[0]
    comment = text
    for u in urls:
        comment = comment.replace(u, " ")
    comment = re.sub(r"\s+", " ", comment).strip()
    return first_url, comment


def apply_url_fields(post: dict, text: str) -> dict:
    """Populate has_url/article_url/user_instruction on a post from raw text."""
    url, instruction = split_url_and_comment(text)
    if url:
        post["has_url"] = True
        post["article_url"] = url
        post["user_instruction"] = instruction
    return post


async def fetch_article(url: str) -> dict:
    """Fetch URL and extract article title + text. Returns {title, text, url}."""
    import trafilatura

    async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=FETCH_HEADERS) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
        final_url = str(response.url)

    text = await asyncio.to_thread(
        trafilatura.extract,
        html,
        url=final_url,
        include_comments=False,
        include_tables=False,
    )
    if not text or len(text.strip()) < 80:
        raise ValueError("Nie udało się wyciągnąć treści artykułu")

    metadata = trafilatura.extract_metadata(html, default_url=final_url)
    title = metadata.title if metadata and metadata.title else ""
    return {"title": title, "text": text.strip(), "url": final_url}
