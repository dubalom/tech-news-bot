import logging
import anthropic
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def summarize_articles(site_name: str, articles: list[dict]) -> list[dict]:
    """
    For each article: generate a Russian headline + 3-sentence summary.
    Returns list of {headline, summary, url}.
    """
    if not articles:
        return []

    # Build numbered article list for Claude
    items = []
    for i, a in enumerate(articles[:8], 1):
        line = f"{i}. {a['title']}"
        if a.get("summary"):
            line += f"\n   Описание: {a['summary'][:300]}"
        if a.get("url"):
            line += f"\n   URL: {a['url']}"
        items.append(line)

    prompt = f"""Ты редактор русскоязычного технологического дайджеста.

Ниже — список статей с сайта «{site_name}».
Для КАЖДОЙ статьи напиши строго в таком формате:

---
ЗАГОЛОВОК: <краткий заголовок на русском, 5-10 слов>
ТЕКСТ: <3 предложения краткого содержания на русском, информативно и по сути>
---

Статьи:
{chr(10).join(items)}

Правила:
- Переводи заголовки на русский, не копируй английские
- Пиши живо, без воды
- Строго соблюдай формат ЗАГОЛОВОК / ТЕКСТ для каждой статьи
- Не добавляй ничего лишнего"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        return _parse_response(raw, articles)
    except Exception as e:
        logger.error(f"Claude error for {site_name}: {e}")
        return []


def _parse_response(raw: str, articles: list[dict]) -> list[dict]:
    """Parse Claude's structured response into list of dicts."""
    results = []
    blocks = raw.split("---")
    article_idx = 0

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        headline = ""
        summary = ""

        for line in block.splitlines():
            line = line.strip()
            if line.startswith("ЗАГОЛОВОК:"):
                headline = line.replace("ЗАГОЛОВОК:", "").strip()
            elif line.startswith("ТЕКСТ:"):
                summary = line.replace("ТЕКСТ:", "").strip()
            elif summary and line and not line.startswith("ЗАГОЛОВОК"):
                summary += " " + line  # multiline text

        if headline and summary:
            url = articles[article_idx]["url"] if article_idx < len(articles) else ""
            results.append({"headline": headline, "summary": summary, "url": url})
            article_idx += 1

    return results


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
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return f"⚠️ Ошибка перевода: {e}"
