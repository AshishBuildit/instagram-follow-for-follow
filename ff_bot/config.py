"""Saari settings aur safety limits ek hi jagah."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SESSION_PATH = DATA_DIR / "session.json"
LOG_PATH = DATA_DIR / "ff.log"

load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except ValueError:
        return default


IG_USERNAME = os.getenv("IG_USERNAME", "").strip()
IG_PASSWORD = os.getenv("IG_PASSWORD", "").strip()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_OWNER_ID = _int("TELEGRAM_OWNER_ID", 0)

DRY_RUN = _bool("DRY_RUN", True)
FOLLOWBACK_ENABLED = _bool("FOLLOWBACK_ENABLED", True)

# Dry run ka apna alag database. Warna test me hi log "DM ho gaya" aur
# "follow back ho gaya" mark ho jate, aur asli run unhe chhod deta.
DB_PATH = DATA_DIR / ("ff-dryrun.db" if DRY_RUN else "ff.db")

ACTIVE_START_HOUR = _int("ACTIVE_START_HOUR", 11)
ACTIVE_END_HOUR = _int("ACTIVE_END_HOUR", 22)

# Bot kitne ghante chal ke apne aap band ho jaye. 0 = jab tak aap band na karo.
# Phone par chalate ho to 2-4 rakho.
RUN_HOURS = _int("RUN_HOURS", 0)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

# --- Account profile ---
# "new"  = naya ya kam engagement wala account. Bahut dheema.
# "warm" = 3+ month purana, roz post, real engagement. Thoda tez.
ACCOUNT_MODE = os.getenv("ACCOUNT_MODE", "warm").strip().lower()

_PROFILES = {
    "new": {
        # (din tak, us din ka max DM)
        "warmup": [(5, 5), (12, 10), (21, 18)],
        "ceiling": 28,
        "floor": 22,
        "per_hour": 4,
        "min_gap": 150,
        "max_gap": 600,
        "followback": 15,
    },
    "warm": {
        "warmup": [(2, 10), (5, 20), (9, 30)],
        "ceiling": 40,
        "floor": 33,
        "per_hour": 8,
        "min_gap": 100,
        "max_gap": 360,
        "followback": 25,
    },
}
_P = _PROFILES.get(ACCOUNT_MODE, _PROFILES["warm"])

WARMUP_CURVE: list[tuple[int, int]] = _P["warmup"]
DAILY_DM_CEILING: int = _P["ceiling"]
DAILY_DM_FLOOR: int = _P["floor"]
MAX_DM_PER_HOUR: int = _P["per_hour"]
MIN_GAP_SECONDS: int = _P["min_gap"]
MAX_GAP_SECONDS: int = _P["max_gap"]
FOLLOWBACK_DAILY_LIMIT: int = _P["followback"]

FOLLOWBACK_MIN_GAP = 60
FOLLOWBACK_MAX_GAP = 200
# Roz ke check me apne kitne followers dekhne hain. Naye hamesha upar hote hain,
# to poori list kheenchne ki zarurat nahi.
FOLLOWER_SCAN_AMOUNT = 200

REST_DAY_EVERY = 7  # har 6-7 din me ek off day

# Instagram ka apna "new conversations per 24h" cap har account ka alag hota hai
# aur wo batata nahi. Bot khud dhoondhta hai aur uske thoda neeche settle ho jata hai.
CAP_SAFETY_MARGIN = 2  # discovered cap se itna neeche rehna
CAP_PROBE_EVERY_DAYS = 5  # itne din bina cap lage to 2 aur try karo
CAP_PROBE_STEP = 2

COOLDOWN_HOURS = 48  # asli spam block par itni der sab band

# --- Target quality filter ---
MAX_TARGET_FOLLOWERS = 50_000
MAX_TARGET_FOLLOWING = 3_000  # itno ko follow karne wala khud follow-bot hai
MIN_TARGET_POSTS = 3
SKIP_PRIVATE = True
SKIP_NO_PROFILE_PIC = True

# Zinda account check. Story lagi ho, ya haal filhaal me post kiya ho.
CHECK_ACTIVITY = _bool("CHECK_ACTIVITY", True)
MAX_LAST_POST_DAYS = 21

# Ek scrape me ek reference page se max itne log uthao
SCRAPE_PER_REF = 300
# Queue itne se neeche gire to apne aap dobara scrape
QUEUE_REFILL_THRESHOLD = 60
# Ek DM ke liye max itne candidates check karo, phir haar maan lo
MAX_CANDIDATE_CHECKS = 12

# Do refill ke beech kam se kam itna gap. Bina iske bot har minute
# har reference page ka poora followers crawl kar deta hai.
REFILL_GAP_MINUTES = 45
# Pichhli baar kuch naya nahi mila to aur lamba ruko
REFILL_BACKOFF_MINUTES = 240
# Follow-back check ka gap
FOLLOWBACK_EVERY_MINUTES = 12 * 60
# Ek hi warning dobara bhejne se pehle itna gap
WARN_REPEAT_MINUTES = 6 * 60
# Poori batch me ek bhi DM na gaya (sab filter me nikal gaye) to itna ruko
DRY_BATCH_BACKOFF_MINUTES = 20

DEFAULT_TEMPLATE = "Hey {name}, follow for follow?"


def bad_hours() -> bool:
    """Ulta window set kar diya to bot chup chaap kabhi kaam nahi karega."""
    return not (0 <= ACTIVE_START_HOUR < ACTIVE_END_HOUR <= 24)


def missing_env() -> list[str]:
    """Konsi zaroori setting missing hai."""
    missing = []
    if not IG_USERNAME:
        missing.append("IG_USERNAME")
    if not IG_PASSWORD:
        missing.append("IG_PASSWORD")
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not TELEGRAM_OWNER_ID:
        missing.append("TELEGRAM_OWNER_ID")
    return missing
