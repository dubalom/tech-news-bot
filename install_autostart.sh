#!/bin/bash
# Устанавливает бота как системную службу macOS (launchd).
# Бот будет запускаться автоматически при входе в систему.

PLIST_NAME="com.technewsbot"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python3"
LOG="$PROJECT_DIR/bot.log"

echo "=== Tech News Bot — Автозапуск ==="
echo "Папка проекта: $PROJECT_DIR"

# Останови старый экземпляр если был
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Создай plist файл
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON}</string>
        <string>${PROJECT_DIR}/main.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>${LOG}</string>

    <key>StandardErrorPath</key>
    <string>${LOG}</string>
</dict>
</plist>
EOF

# Запусти службу
launchctl load "$PLIST_PATH"
echo ""
echo "✅ Бот зарегистрирован и запущен!"
echo ""
echo "Управление:"
echo "  Статус:    launchctl list | grep technewsbot"
echo "  Остановить: launchctl unload ~/Library/LaunchAgents/${PLIST_NAME}.plist"
echo "  Запустить:  launchctl load ~/Library/LaunchAgents/${PLIST_NAME}.plist"
echo "  Логи:      tail -f $LOG"
