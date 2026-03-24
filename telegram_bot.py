import asyncio
import logging
from datetime import datetime
from typing import Union, Optional
import pytz

from telegram import (
    Update, Bot,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters,
)
from telegram.constants import ParseMode

from config import (
    TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
    SCHEDULE_HOUR, SCHEDULE_MINUTE, TIMEZONE,
)
from sources import (
    get_all_sites, get_active_sites, get_custom_sources,
    get_disabled_names, is_builtin, is_disabled,
    toggle_source, add_source, delete_source,
)
from scraper import fetch_site_articles
from summarizer import summarize_articles, translate_text

logger = logging.getLogger(__name__)

# ─── Conversation states ───────────────────────────────────────────────────────
WAITING_TRANSLATION = 1
WAITING_SOURCE_URL  = 2
WAITING_SOURCE_NAME = 3
WAITING_SOURCE_RSS  = 4

PAGE_SIZE = 6  # sources per page

# ─── Emoji map ────────────────────────────────────────────────────────────────
SITE_EMOJIS = {
    "Bloomberg Technology": "📊",
    "WSJ Tech": "📰",
    "CNBC Technology": "📺",
    "New York Times Technology": "🗞️",
    "404 Media": "🔍",
    "SamMobile": "📱",
    "Reddit /r/technology": "🤖",
    "Macworld": "🍎",
    "Electrek": "⚡",
    "Car News China": "🚗",
    "New Atlas": "🌐",
    "Sostav.ru": "📣",
    "Apple Newsroom": "🍏",
    "WCCFTech": "💻",
    "Android Authority": "🤖",
    "Android Police": "👮",
    "Ars Technica": "🔬",
    "BleepingComputer": "🛡️",
    "ZDNet": "🖥️",
}

CATEGORIES = {
    "cat_mobile":   ["SamMobile", "Macworld"],
    "cat_apple":    ["Apple Newsroom", "Macworld"],
    "cat_android":  ["Android Authority", "Android Police", "SamMobile"],
    "cat_security": ["BleepingComputer", "Ars Technica", "ZDNet"],
    "cat_auto":     ["Electrek", "Car News China", "New Atlas"],
    "cat_other":    [
        "Bloomberg Technology", "WSJ Tech", "CNBC Technology",
        "New York Times Technology", "404 Media", "Reddit /r/technology",
        "WCCFTech", "Sostav.ru",
    ],
}

# ─── Keyboards ────────────────────────────────────────────────────────────────

def kb_main() -> InlineKeyboardMarkup:
    active = len(get_active_sites())
    total  = len(get_all_sites())
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📰 Дайджест новостей", callback_data="news_menu")],
        [
            InlineKeyboardButton("🌐 Перевести текст", callback_data="translate"),
            InlineKeyboardButton(f"📋 Источники ({active}/{total})", callback_data="src_list:0"),
        ],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
    ])

def kb_news() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📱 Мобильные",    callback_data="cat_mobile"),
            InlineKeyboardButton("🍎 Apple",         callback_data="cat_apple"),
        ],
        [
            InlineKeyboardButton("🤖 Android",       callback_data="cat_android"),
            InlineKeyboardButton("🛡️ Безопасность",  callback_data="cat_security"),
        ],
        [
            InlineKeyboardButton("⚡ Авто/Электро",  callback_data="cat_auto"),
            InlineKeyboardButton("🔬 Остальные",     callback_data="cat_other"),
        ],
        [InlineKeyboardButton("🌍 Все источники",   callback_data="news_all")],
        [InlineKeyboardButton("◀️ Назад",            callback_data="main_menu")],
    ])

def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
    ])

def kb_after_news() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Ещё новости", callback_data="news_menu"),
            InlineKeyboardButton("🏠 Меню",        callback_data="main_menu"),
        ]
    ])

def kb_sources(page: int) -> InlineKeyboardMarkup:
    """
    Source list page with toggle / delete buttons.
    Each source row:  [📌 Name]  [✅ ON / ❌ OFF]  [🗑️] (custom only)
    """
    all_sites = get_all_sites()
    disabled  = get_disabled_names()
    total_pages = max(1, (len(all_sites) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    chunk = all_sites[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    rows  = []

    for site in chunk:
        name   = site["name"]
        emoji  = SITE_EMOJIS.get(name, "📌")
        on     = name not in disabled
        toggle_btn = InlineKeyboardButton(
            "✅" if on else "❌",
            callback_data=f"src_toggle:{name}:{page}",
        )
        label_btn = InlineKeyboardButton(
            f"{emoji} {name[:22]}{'…' if len(name) > 22 else ''}",
            callback_data=f"src_info:{name}:{page}",
        )
        row = [label_btn, toggle_btn]
        if not is_builtin(name):
            row.append(InlineKeyboardButton(
                "🗑️", callback_data=f"src_delete:{name}:{page}"
            ))
        rows.append(row)

    # Pagination row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"src_list:{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"src_list:{page+1}"))
    rows.append(nav)

    # Action row
    rows.append([
        InlineKeyboardButton("➕ Добавить источник", callback_data="add_source"),
    ])
    rows.append([
        InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu"),
    ])

    return InlineKeyboardMarkup(rows)


def sources_text(page: int) -> str:
    all_sites = get_all_sites()
    disabled  = get_disabled_names()
    active    = len(all_sites) - len([d for d in disabled if d in {s["name"] for s in all_sites}])
    custom_names = {s["name"] for s in get_custom_sources()}

    total_pages = max(1, (len(all_sites) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = all_sites[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    lines = [
        f"📋 *Управление источниками*",
        f"Активно: *{active}* из *{len(all_sites)}*\n",
        "✅ — включён  ❌ — выключен  🗑️ — удалить (только свои)\n",
    ]
    for site in chunk:
        name = site["name"]
        on   = name not in disabled
        tag  = "✏️" if name in custom_names else ""
        rss  = "RSS" if site.get("rss") else "HTML"
        status = "✅" if on else "❌"
        lines.append(f"{status} {name} {tag} `[{rss}]`")

    return "\n".join(lines)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def split_text(text: str, max_len: int = 4000) -> list:
    if len(text) <= max_len:
        return [text]
    chunks, buf = [], ""
    for line in text.splitlines(keepends=True):
        if len(buf) + len(line) > max_len:
            chunks.append(buf)
            buf = ""
        buf += line
    if buf:
        chunks.append(buf)
    return chunks


# ─── News pipeline ────────────────────────────────────────────────────────────

async def run_news_pipeline(
    bot: Bot,
    chat_id: Union[int, str],
    site_names: Optional[list] = None,
) -> None:
    active_sites = get_active_sites()
    sites = active_sites if not site_names else [
        s for s in active_sites if s["name"] in site_names
    ]

    tz  = pytz.timezone(TIMEZONE)
    now = datetime.now(tz).strftime("%d.%m.%Y %H:%M")
    loop = asyncio.get_event_loop()

    await bot.send_message(
        chat_id=chat_id,
        text=f"📡 *Технодайджест — {now}*\n⏳ Собираю с {len(sites)} источников...",
        parse_mode=ParseMode.MARKDOWN,
    )

    for site in sites:
        name = site["name"]
        try:
            articles  = await loop.run_in_executor(None, fetch_site_articles, site)
            if not articles:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ *{name}* — нет данных",
                    parse_mode=ParseMode.MARKDOWN,
                )
                continue

            summaries = await loop.run_in_executor(
                None, summarize_articles, name, articles
            )
            if not summaries:
                continue

            emoji  = SITE_EMOJIS.get(name, "📌")
            header = f"{emoji} *{name}*\n{'─'*28}"
            await bot.send_message(
                chat_id=chat_id,
                text=header,
                parse_mode=ParseMode.MARKDOWN,
            )

            for art in summaries:
                url = art.get("url", site["url"])
                from urllib.parse import urlparse
                try:
                    domain = urlparse(url).netloc.replace("www.", "")
                except Exception:
                    domain = url
                block = (
                    f"🔖 *{art['headline']}*\n"
                    f"{art['summary']}"
                    + (f"\n🔗 [{domain}]({url})" if url else "")
                )
                for chunk in split_text(block):
                    await bot.send_message(
                        chat_id=chat_id,
                        text=chunk,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True,
                    )
                    await asyncio.sleep(0.3)

            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error: {name}: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ *{name}* — ошибка: {e}",
                parse_mode=ParseMode.MARKDOWN,
            )

    await bot.send_message(
        chat_id=chat_id,
        text="✅ *Дайджест готов!*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_after_news(),
    )


# ─── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Привет, *{user.first_name}*!\n\n"
        "Я *Tech News Bot* — собираю технологические новости "
        "с 19+ источников и перевожу на русский каждые 2 часа.\n\n"
        "Выбери действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_main(),
    )


# ─── Callbacks: navigation ────────────────────────────────────────────────────

async def cb_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🏠 *Главное меню*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_main(),
    )

async def cb_news_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📰 *Выбери категорию:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_news(),
    )

async def cb_news_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer("Запускаю...")
    await q.edit_message_text("⏳ Загружаю все источники... (~3–5 мин)")
    await run_news_pipeline(bot=context.bot, chat_id=q.message.chat_id)

async def cb_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    labels = {
        "cat_mobile":   "📱 Мобильные",
        "cat_apple":    "🍎 Apple",
        "cat_android":  "🤖 Android",
        "cat_security": "🛡️ Безопасность",
        "cat_auto":     "⚡ Авто/Электро",
        "cat_other":    "🔬 Остальные",
    }
    label = labels.get(q.data, q.data)
    await q.edit_message_text(f"⏳ Загружаю: *{label}*...", parse_mode=ParseMode.MARKDOWN)
    await run_news_pipeline(
        bot=context.bot,
        chat_id=q.message.chat_id,
        site_names=CATEGORIES.get(q.data, []),
    )

async def cb_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    tz  = pytz.timezone(TIMEZONE)
    now = datetime.now(tz).strftime("%d.%m.%Y %H:%M:%S")
    active = len(get_active_sites())
    total  = len(get_all_sites())
    text = (
        f"⚙️ *Настройки бота*\n\n"
        f"🕐 Сейчас: `{now}`\n"
        f"🌍 Часовой пояс: `{TIMEZONE}`\n"
        f"⏰ Обновление: *каждые 2 часа*\n"
        f"📡 Источников: `{active}` активных из `{total}`\n"
        f"📨 Отправка в: `{TELEGRAM_CHAT_ID}`"
    )
    await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back())


# ─── Callbacks: source management ─────────────────────────────────────────────

async def cb_src_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show source list page."""
    q = update.callback_query
    await q.answer()
    page = int(q.data.split(":")[1])
    await q.edit_message_text(
        sources_text(page),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_sources(page),
    )

async def cb_src_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle source on/off."""
    q = update.callback_query
    parts = q.data.split(":", 2)   # src_toggle : name : page
    name  = parts[1]
    page  = int(parts[2])
    now_enabled = toggle_source(name)
    await q.answer("✅ Включён" if now_enabled else "❌ Выключен")
    await q.edit_message_text(
        sources_text(page),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_sources(page),
    )

async def cb_src_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a custom source (with confirmation)."""
    q = update.callback_query
    parts = q.data.split(":", 2)
    name  = parts[1]
    page  = int(parts[2])

    # First tap → ask confirmation
    confirm_key = f"confirm_delete:{name}"
    if context.user_data.get("pending_delete") != name:
        context.user_data["pending_delete"] = name
        await q.answer(f"Нажми ещё раз 🗑️ для подтверждения удаления «{name}»", show_alert=True)
        return

    # Second tap → delete
    context.user_data.pop("pending_delete", None)
    ok = delete_source(name)
    await q.answer("✅ Удалён" if ok else "⚠️ Не удалось удалить")
    new_page = max(0, page - (1 if len(get_all_sites()) % PAGE_SIZE == 0 else 0))
    await q.edit_message_text(
        sources_text(new_page),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_sources(new_page),
    )

async def cb_src_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show brief info about source (tap on name)."""
    q = update.callback_query
    parts = q.data.split(":", 2)
    name  = parts[1]
    all_sites = get_all_sites()
    site = next((s for s in all_sites if s["name"] == name), None)
    if not site:
        await q.answer("Источник не найден")
        return
    rss  = site.get("rss") or "нет"
    kind = "Встроенный" if is_builtin(name) else "Добавлен вручную"
    status = "❌ Выключен" if is_disabled(name) else "✅ Включён"
    await q.answer(
        f"{name}\n{status}\n{kind}\nRSS: {rss[:40] if rss else 'нет'}",
        show_alert=True,
    )

async def cb_noop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()


# ─── Add source conversation ──────────────────────────────────────────────────

async def cb_add_source(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "➕ *Добавить источник*\n\n"
        "Введи URL сайта:\n`https://techcrunch.com`\n\n"
        "_/cancel — отмена_",
        parse_mode=ParseMode.MARKDOWN,
    )
    return WAITING_SOURCE_URL

async def got_source_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text("⚠️ Некорректный URL. Введи ещё раз (начиная с https://):")
        return WAITING_SOURCE_URL
    context.user_data["new_url"] = url
    await update.message.reply_text(
        "✏️ Введи название источника:\n`TechCrunch`",
        parse_mode=ParseMode.MARKDOWN,
    )
    return WAITING_SOURCE_NAME

async def got_source_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_name"] = update.message.text.strip()
    await update.message.reply_text(
        "📡 Введи URL RSS-ленты (или `-` если нет):\n"
        "`https://techcrunch.com/feed/`",
        parse_mode=ParseMode.MARKDOWN,
    )
    return WAITING_SOURCE_RSS

async def got_source_rss(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    rss_raw = update.message.text.strip()
    rss  = None if rss_raw == "-" else rss_raw
    name = context.user_data.pop("new_name", "")
    url  = context.user_data.pop("new_url", "")
    ok   = add_source(name=name, url=url, rss=rss)
    if ok:
        await update.message.reply_text(
            f"✅ *{name}* добавлен!\nURL: {url}\nRSS: {rss or 'нет'}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 К списку источников", callback_data="src_list:0")],
                [InlineKeyboardButton("🏠 Главное меню",        callback_data="main_menu")],
            ]),
        )
    else:
        await update.message.reply_text(
            "⚠️ Источник с таким именем или URL уже существует.",
            reply_markup=kb_main(),
        )
    return ConversationHandler.END


# ─── Translation conversation ─────────────────────────────────────────────────

async def cb_translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "🌐 *Переводчик EN → RU*\n\n"
        "Отправь текст на английском — переведу на русский.\n\n"
        "_/cancel — отмена_",
        parse_mode=ParseMode.MARKDOWN,
    )
    return WAITING_TRANSLATION

async def handle_translation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if len(text) < 3:
        await update.message.reply_text("⚠️ Слишком короткий текст.")
        return WAITING_TRANSLATION
    msg = await update.message.reply_text("⏳ Перевожу...")
    loop = asyncio.get_event_loop()
    translated = await loop.run_in_executor(None, translate_text, text)
    await msg.delete()
    await update.message.reply_text(
        f"🌐 *Перевод:*\n\n{translated}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Ещё перевод", callback_data="translate"),
                InlineKeyboardButton("🏠 Меню",         callback_data="main_menu"),
            ]
        ]),
    )
    return ConversationHandler.END

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Отменено.", reply_markup=kb_main())
    return ConversationHandler.END


# ─── Scheduled job ────────────────────────────────────────────────────────────

async def scheduled_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Running scheduled digest")
    await run_news_pipeline(bot=context.bot, chat_id=TELEGRAM_CHAT_ID)


# ─── App builder ──────────────────────────────────────────────────────────────

def build_application() -> Application:
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    translate_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_translate, pattern="^translate$")],
        states={WAITING_TRANSLATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translation)
        ]},
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    add_source_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_add_source, pattern="^add_source$")],
        states={
            WAITING_SOURCE_URL:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_source_url)],
            WAITING_SOURCE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_source_name)],
            WAITING_SOURCE_RSS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_source_rss)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(translate_conv)
    app.add_handler(add_source_conv)

    app.add_handler(CallbackQueryHandler(cb_main_menu,   pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(cb_news_menu,   pattern="^news_menu$"))
    app.add_handler(CallbackQueryHandler(cb_news_all,    pattern="^news_all$"))
    app.add_handler(CallbackQueryHandler(cb_settings,    pattern="^settings$"))
    app.add_handler(CallbackQueryHandler(cb_category,    pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(cb_src_list,    pattern=r"^src_list:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_src_toggle,  pattern=r"^src_toggle:"))
    app.add_handler(CallbackQueryHandler(cb_src_delete,  pattern=r"^src_delete:"))
    app.add_handler(CallbackQueryHandler(cb_src_info,    pattern=r"^src_info:"))
    app.add_handler(CallbackQueryHandler(cb_noop,        pattern="^noop$"))

    # Автоматическая рассылка отключена — запуск только по кнопке

    return app
