import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env only for local dev; on Railway env vars are injected by the platform
if Path(".env").exists():
    load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "8"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

MAX_ARTICLES_PER_SITE = int(os.getenv("MAX_ARTICLES_PER_SITE", "10"))

SITES = [
    {
        "name": "Bloomberg Technology",
        "url": "https://www.bloomberg.com/technology",
        "rss": None,  # No public RSS, will scrape HTML
    },
    {
        "name": "WSJ Tech",
        "url": "https://www.wsj.com/tech",
        "rss": None,  # Paywalled, limited scraping
    },
    {
        "name": "CNBC Technology",
        "url": "https://www.cnbc.com/technology/",
        "rss": "https://www.cnbc.com/id/19854910/device/rss/rss.html",
    },
    {
        "name": "New York Times Technology",
        "url": "https://www.nytimes.com/section/technology",
        "rss": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    },
    {
        "name": "404 Media",
        "url": "https://www.404media.co/",
        "rss": "https://www.404media.co/rss/",
    },
    {
        "name": "SamMobile",
        "url": "https://www.sammobile.com/",
        "rss": "https://www.sammobile.com/feed/",
    },
    {
        "name": "Reddit /r/technology",
        "url": "https://www.reddit.com/r/technology/new/",
        "rss": "https://www.reddit.com/r/technology/new/.rss",
    },
    {
        "name": "Macworld",
        "url": "https://www.macworld.com/",
        "rss": "https://www.macworld.com/feed",
    },
    {
        "name": "Electrek",
        "url": "https://electrek.co/",
        "rss": "https://electrek.co/feed/",
    },
    {
        "name": "Car News China",
        "url": "https://carnewschina.com/",
        "rss": "https://carnewschina.com/feed/",
    },
    {
        "name": "New Atlas",
        "url": "https://newatlas.com/",
        "rss": "https://newatlas.com/index.rss",
    },
    {
        "name": "Sostav.ru",
        "url": "https://www.sostav.ru/",
        "rss": "https://www.sostav.ru/rss/news.xml",
    },
    {
        "name": "Apple Newsroom",
        "url": "https://www.apple.com/newsroom/",
        "rss": "https://www.apple.com/newsroom/rss-feed.rss",
    },
    {
        "name": "WCCFTech",
        "url": "https://wccftech.com/",
        "rss": "https://wccftech.com/feed/",
    },
    {
        "name": "Android Authority",
        "url": "https://www.androidauthority.com/",
        "rss": "https://www.androidauthority.com/feed/",
    },
    {
        "name": "Android Police",
        "url": "https://www.androidpolice.com/",
        "rss": "https://www.androidpolice.com/feed/",
    },
    {
        "name": "Ars Technica",
        "url": "https://arstechnica.com/",
        "rss": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    },
    {
        "name": "BleepingComputer",
        "url": "https://www.bleepingcomputer.com/",
        "rss": "https://www.bleepingcomputer.com/feed/",
    },
    {
        "name": "ZDNet",
        "url": "https://www.zdnet.com/",
        "rss": "https://www.zdnet.com/news/rss.xml",
    },
]
