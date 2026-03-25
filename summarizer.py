import logging
import anthropic
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def summarize_articles(site_name: str, articles: list[dict]) -> list[dict]:
    """
    Summarize latest news from a site into bullet points in Russian.
    Returns list of {headline, summary, url}.
    """
    if not articles:
        return []

    titles = "\n".join(
        f"- {a['title']}" + (f" | {a['summary'][:200]}" if a.get("summary") else "")
        for a in articles[:10]
    )

    prompt = f"""Ты редактор технологического дайджеста.

Последние новости с сайта «{site_name}»:
{titles}

Напиши дайджест на русском языке: 8-10 коротких тезисов.
Каждый тезис начинается с символа "•" на новой строке.
Каждый тезис — одно информативное предложение.
Переводи заголовки на русский, не копируй английские.
Отвечай ТОЛЬКО тезисами, без вступлений и заголовков."""

    try:
        logger.info(f"[{site_name}] Calling Claude, key length={len(ANTHROPIC_API_KEY)}")
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        logger.info(f"[{site_name}] Claude returned {len(raw)} chars")
        url = articles[0].get("url", "") if articles else ""
        return [{"headline": "", "summary": raw, "url": url}]
    except Exception as e:
        logger.error(f"Claude error for {site_name}: {type(e).__name__}: {e}")
        # Fallback: return raw article titles if Claude fails
        fallback = "\n".join(f"• {a['title']}" for a in articles[:8])
        url = articles[0].get("url", "") if articles else ""
        return [{"headline": "", "summary": f"_(Claude недоступен)_\n{fallback}", "url": url}]


def translate_text(text: str) -> str:
    """Translate English text to Russian preserving style."""
    prompt = f"""Переведи текст с английского на русский язык.
Сохраняй стиль, тон и форматирование оригинала.
Переводи естественно, как носитель языка.
Отвечай ТОЛЬКО переводом, без пояснений.

Текст:
{text}"""

    try:
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return f"⚠️ Ошибка перевода: {e}"
