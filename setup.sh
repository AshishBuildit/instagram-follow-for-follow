#!/data/data/com.termux/files/usr/bin/bash
# ff-bot ka poora setup. Termux me chalao:
#
#     bash setup.sh
#
# Jitni baar chaho chalao. Jo kaam ho chuka hai wo dobara nahi hoga,
# sirf jo bacha hai wahi hoga.

set -u

BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BOT_DIR"

GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; DIM=$'\033[2m'; OFF=$'\033[0m'
step()  { printf "\n%s>>%s %s\n" "$YELLOW" "$OFF" "$1"; }
ok()    { printf "   %sOK%s   %s\n" "$GREEN" "$OFF" "$1"; }
skip()  { printf "   %s--   %s%s\n" "$DIM" "$1" "$OFF"; }
fail()  { printf "   %sFAIL%s %s\n" "$RED" "$OFF" "$1"; }
die()   { fail "$1"; printf "\n%sSetup ruk gaya. Theek karke phir se: bash setup.sh%s\n\n" "$RED" "$OFF"; exit 1; }

printf "\n  ff-bot setup\n  %s%s%s\n" "$DIM" "$BOT_DIR" "$OFF"

# --- 0. Jagah sahi hai? -----------------------------------------------------

case "$BOT_DIR" in
    */storage/shared/*|/sdcard/*|/storage/emulated/*|*/storage/downloads/*)
        fail "Ye folder shared storage me hai."
        echo
        echo "   Yahan SQLite ka file locking kaam nahi karta, database kharab ho jayega."
        echo "   Termux ke apne home me le jao:"
        echo
        echo "      cp -r \"$BOT_DIR\" ~/ff-bot && cd ~/ff-bot && bash setup.sh"
        echo
        exit 1
        ;;
esac

# --- 1. System packages -----------------------------------------------------
# python-pillow yahan se lena zaruri hai. pip se banane par jpeg headers
# chahiye hote hain aur build fail ho jata hai.

step "1/6  System packages"

PKGS="python rust binutils termux-api python-pillow libjpeg-turbo libpng zlib freetype"
MISSING=""
for p in $PKGS; do
    dpkg -s "$p" >/dev/null 2>&1 || MISSING="$MISSING $p"
done

if [ -z "$MISSING" ]; then
    skip "sab pehle se hain"
else
    echo "   Chahiye:$MISSING"
    pkg update -y >/dev/null 2>&1 || true
    # shellcheck disable=SC2086
    if pkg install -y $MISSING; then
        ok "install ho gaye"
    else
        die "packages install nahi hue. Internet check karo."
    fi
fi

command -v python >/dev/null 2>&1 || die "python nahi mila"

# --- 2. Build ke liye zaruri settings ---------------------------------------

step "2/6  Build settings"

# Bina iske maturin "Failed to determine Android API level" deta hai
export ANDROID_API_LEVEL="${ANDROID_API_LEVEL:-24}"
# Phone ki RAM kam hai, saare cores par compile karne se build mar jata hai
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}"
export TMPDIR="${TMPDIR:-$PREFIX/tmp}"
# Cache HOME me rakho taki dobara build na karna pade
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$HOME/.cache/pip}"
mkdir -p "$PIP_CACHE_DIR" "$TMPDIR"
ok "API level $ANDROID_API_LEVEL, jobs $CARGO_BUILD_JOBS"

# --- 3. Python libraries ----------------------------------------------------

step "3/6  Python libraries"

libs_ready() {
    python - <<'PY' >/dev/null 2>&1
import instagrapi, telegram, dotenv, PIL  # noqa: F401
PY
}

if libs_ready; then
    skip "sab pehle se installed hain"
else
    echo "   Pehli baar 20-40 min lag sakte hain (pydantic Rust me compile hota hai)."
    echo "   Beech me ruk gaya to dobara chalane par wahin se aage badhega."
    echo
    # NOTE: --no-cache-dir kabhi mat lagana. Uske bina bana hua pydantic wheel
    # cache me reh jata hai aur agli baar seconds me install hota hai.
    if pip install -r requirements.txt; then
        libs_ready && ok "sab libraries ready" || die "install to hua par import nahi ho raha"
    else
        fail "pip install fail hua"
        echo
        echo "   Phone hang hua ya build mara ho to RAM kam padi hai. Ye try karo:"
        echo "      CARGO_BUILD_JOBS=1 bash setup.sh"
        echo
        exit 1
    fi
fi

# --- 4. One-tap shortcut aur boot script ------------------------------------

step "4/6  Widget aur boot script"

mkdir -p "$HOME/.shortcuts" "$HOME/.termux/boot"
chmod 700 "$HOME/.shortcuts" 2>/dev/null || true

sed "s|__BOT_DIR__|$BOT_DIR|" scripts/ff-bot.sh > "$HOME/.shortcuts/ff-bot"
chmod +x "$HOME/.shortcuts/ff-bot"

sed "s|__BOT_DIR__|$BOT_DIR|" scripts/boot.sh > "$HOME/.termux/boot/ff-bot"
chmod +x "$HOME/.termux/boot/ff-bot"

ok "widget shortcut aur boot script ready"

# --- 5. .env ----------------------------------------------------------------

step "5/6  Settings file"

ENV_READY=0
if [ ! -f .env ]; then
    cp .env.example .env
    ok ".env bana diya"
else
    skip ".env pehle se hai"
fi

# Placeholder abhi tak bhare hain ya nahi
if grep -q "your_ig_username\|123456:ABC-your-bot-token\|^TELEGRAM_OWNER_ID=123456789" .env; then
    ENV_READY=0
else
    ENV_READY=1
    ok "details bhari hui hain"
fi

# --- 6. Final check ---------------------------------------------------------

step "6/6  Sab check"

python -c "import ff_bot, ff_bot.config, ff_bot.db, ff_bot.worker" 2>/dev/null \
    && ok "bot ka code load ho raha hai" \
    || die "bot ka code load nahi hua"

echo
if [ "$ENV_READY" -eq 1 ]; then
    printf "  %sSab ready hai.%s\n\n" "$GREEN" "$OFF"
    echo "  Chalane ke liye:"
    echo "     python -m ff_bot"
    echo
    echo "  Ya home screen par Termux:Widget lagao aur 'ff-bot' dabao."
else
    printf "  %sBas ek kaam bacha hai: .env bharna.%s\n\n" "$YELLOW" "$OFF"
    echo "     nano $BOT_DIR/.env"
    echo
    echo "  Ye 4 bharo:"
    echo "     IG_USERNAME        - Instagram username"
    echo "     IG_PASSWORD        - Instagram password"
    echo "     TELEGRAM_TOKEN     - @BotFather se"
    echo "     TELEGRAM_OWNER_ID  - @userinfobot se"
    echo
    echo "  Save: Ctrl+O, Enter, Ctrl+X"
    echo
    echo "  Phir:  python -m ff_bot"
fi
echo
