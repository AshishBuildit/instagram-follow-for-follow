#!/data/data/com.termux/files/usr/bin/bash
# Termux:Boot script. Phone restart hone ke baad bot apne aap chalu.
# install-termux.sh isko ~/.termux/boot/ff-bot me copy kar deta hai.

BOT_DIR="__BOT_DIR__"

termux-wake-lock 2>/dev/null
sleep 30  # network aane ka intezaar

cd "$BOT_DIR" || exit 1
exec python -m ff_bot >> "$BOT_DIR/data/boot.log" 2>&1
