#!/data/data/com.termux/files/usr/bin/bash
# Termux:Widget wala one-tap launcher.
# install-termux.sh isko ~/.shortcuts/ff-bot me copy kar deta hai.

BOT_DIR="__BOT_DIR__"

cd "$BOT_DIR" 2>/dev/null || {
    echo "ff-bot folder nahi mila: $BOT_DIR"
    sleep 8
    exit 1
}

# Screen band hone par bhi bot chalta rahe
termux-wake-lock 2>/dev/null
trap 'termux-wake-unlock 2>/dev/null' EXIT

clear
echo "Bot chalu ho raha hai..."
echo "Band karne ke liye: Telegram par /stop, ya yahan Ctrl+C"
echo

python -m ff_bot
code=$?

echo
if [ $code -eq 2 ]; then
    echo "Bot pehle se chal raha tha. Telegram par /status dekho."
else
    echo "Bot band ho gaya."
fi
echo "Ye window 10 second me apne aap band ho jayegi."
sleep 10
