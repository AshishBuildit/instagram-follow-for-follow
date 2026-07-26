#!/data/data/com.termux/files/usr/bin/bash
# Ek baar chalane wala setup.
# Termux me:  cd ~/ff-bot && bash scripts/install-termux.sh
#
# Dobara chala sakte ho, kuch tootega nahi. .env aur data/ ko haath nahi lagata.
set -e

BOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BOT_DIR"

echo
echo "  ff-bot setup"
echo "  $BOT_DIR"
echo

# Shared storage par SQLite ka file locking bharosemand nahi hai aur chmod +x
# kaam nahi karta. Bot ko Termux ke apne home me hona chahiye.
case "$BOT_DIR" in
    */storage/shared/*|/sdcard/*|/storage/emulated/*|*/storage/downloads/*)
        echo "  RUKO. Ye folder shared storage me hai."
        echo
        echo "  Yahan se bot theek se nahi chalega (database corrupt ho sakta hai)."
        echo "  Termux ke apne home me le jao:"
        echo
        echo "     cp -r \"$BOT_DIR\" ~/ff-bot"
        echo "     cd ~/ff-bot"
        echo "     bash scripts/install-termux.sh"
        echo
        exit 1
        ;;
esac

echo "1/5  Packages..."
pkg update -y >/dev/null 2>&1 || true
pkg install -y python rust binutils termux-api >/dev/null

echo "2/5  Python libraries (pehli baar 10-20 min lag sakte hain)..."
# Termux me pip ko upgrade karna mana hai, wo python-pip package tod deta hai
pip install -r requirements.txt

echo "3/5  One-tap widget shortcut..."
mkdir -p "$HOME/.shortcuts"
sed "s|__BOT_DIR__|$BOT_DIR|" scripts/ff-bot.sh > "$HOME/.shortcuts/ff-bot"
chmod +x "$HOME/.shortcuts/ff-bot"
chmod 700 "$HOME/.shortcuts"

echo "4/5  Restart ke baad apne aap chalu..."
mkdir -p "$HOME/.termux/boot"
sed "s|__BOT_DIR__|$BOT_DIR|" scripts/boot.sh > "$HOME/.termux/boot/ff-bot"
chmod +x "$HOME/.termux/boot/ff-bot"

echo "5/5  .env..."
mkdir -p data
if [ ! -f .env ]; then
    cp .env.example .env
    NEW_ENV=1
else
    echo "     .env pehle se hai, chhod diya."
fi

echo
echo "  Setup ho gaya."
echo
if [ -n "$NEW_ENV" ]; then
    echo "  Ab .env bharo:"
    echo "     nano $BOT_DIR/.env"
    echo "     (save: Ctrl+O, Enter, Ctrl+X)"
    echo
fi
echo "  Phir home screen par Termux:Widget lagao aur 'ff-bot' dabao."
echo
