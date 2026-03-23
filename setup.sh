#!/bin/bash
set -e

echo "=== Tech News Parser Bot — Setup ==="

# Check Python
python3 --version || { echo "Python 3.10+ required"; exit 1; }

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env if missing
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  .env создан. Заполни его перед запуском:"
    echo "   TELEGRAM_BOT_TOKEN — токен от @BotFather"
    echo "   TELEGRAM_CHAT_ID   — например @parse_ch"
    echo "   ANTHROPIC_API_KEY  — ключ с console.anthropic.com"
fi

echo ""
echo "✅ Установка завершена!"
echo ""
echo "Следующие шаги:"
echo "  1. Отредактируй .env"
echo "  2. source .venv/bin/activate"
echo "  3. python main.py --once   # тест"
echo "  4. python main.py          # запустить бота"
