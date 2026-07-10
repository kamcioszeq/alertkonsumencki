"""Kontekst generowania: powtórki GIS + hint ikon hooka."""
from core import shared_facts
from core.icon_rotation import next_warning_icon
from core.repeat_detector import detect_repeat
from telegram.prompts import icon_hint_instruction


async def build_icon_hint(
    phase1_msg_id: int,
    article_text: str,
    source: str,
    title: str = "",
) -> str:
    cached = shared_facts.load(phase1_msg_id) or {}
    repeat_context = cached.get("repeat_context")
    if not repeat_context:
        repeat_context = await detect_repeat(
            article_text,
            source_url=source if source.startswith("http") else "",
            title=title,
        )
        shared_facts.merge(phase1_msg_id, repeat_context=repeat_context)
    warning_icon = next_warning_icon()
    return icon_hint_instruction(repeat_context, warning_icon)
