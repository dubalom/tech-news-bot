#!/usr/bin/env python3
"""
Tech News Parser Bot (@news223news_bot)
---------------------------------------
• Собирает технологические новости с 19 источников каждое утро
• Переводит и суммаризирует на русский язык через Claude AI
• Переводчик EN → RU по запросу
• Красивые инлайн-кнопки навигации

Запуск:
    python main.py          — запустить бота (polling)
    python main.py --once   — разовый запуск дайджеста (для теста)
"""

import asyncio
import logging
import sys

from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, ANTHROPIC_API_KEY
from telegram_bot import build_application, run_news_pipeline
from telegram import Bot

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def validate_config() -> bool:
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("BOT_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("CHAT_ID")
    if not ANTHROPIC_API_KEY:
        missing.append("CLAUDE_KEY")
    if missing:
        logger.error(f"Не заданы переменные окружения: {', '.join(missing)}")
        logger.error("Заполни файл .env (скопируй из .env.example)")
        return False
    return True


async def run_once() -> None:
    logger.info("Запуск разового дайджеста...")
    bot = Bot(token=TELEGRAM_TOKEN)
    # Для теста отправляем себе (используй свой chat_id)
    await run_news_pipeline(bot=bot, chat_id=TELEGRAM_CHAT_ID)
    logger.info("Готово.")


def main() -> None:
    if not validate_config():
        sys.exit(1)

    if "--once" in sys.argv:
        asyncio.run(run_once())
        return

    logger.info("Запускаю @news223news_bot...")
    app = build_application()
    logger.info(f"Бот работает. Отправка в: {TELEGRAM_CHAT_ID}")
    logger.info("Нажми Ctrl+C для остановки")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
