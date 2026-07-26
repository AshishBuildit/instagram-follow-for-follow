"""Roz ka plan: kitne DM, rest day hai ya nahi, abhi bhejna chahiye ya nahi."""

import random
from datetime import date, datetime, timedelta

from . import config, db


def _day_random(salt: str) -> random.Random:
    """Ek hi din ke liye hamesha same random. Restart se plan nahi badalta."""
    return random.Random(f"{date.today().isoformat()}:{salt}")


def is_rest_day() -> bool:
    """Har 6-7 din me ek off day, par fixed pattern nahi."""
    day = db.day_number()
    if day <= 7:
        return False  # warmup week me rest nahi, waise hi kam DM hain
    block = day // config.REST_DAY_EVERY
    rng = random.Random(f"rest:{db.first_run_date()}:{block}")
    return day % config.REST_DAY_EVERY == rng.randrange(config.REST_DAY_EVERY)


def profile_quota() -> int:
    """Warmup curve ke hisaab se aaj ka target, cap ko ignore karke."""
    day = db.day_number()
    for until_day, cap in config.WARMUP_CURVE:
        if day <= until_day:
            return cap
    return _day_random("quota").randint(config.DAILY_DM_FLOOR, config.DAILY_DM_CEILING)


def cap_ceiling() -> int | None:
    """Instagram ke chhupe cap se nikla hua aaj ka safe max.

    Cap lagne ke baad thoda neeche rehte hain, aur har kuch din me
    do aur try karke dekhte hain ki cap badha ya nahi.
    """
    found = db.discovered_cap()
    if not found:
        return None
    ceiling = found - config.CAP_SAFETY_MARGIN
    since = db.days_since_cap_hit()
    if since:
        probes = since // config.CAP_PROBE_EVERY_DAYS
        ceiling += probes * config.CAP_PROBE_STEP
    return max(2, ceiling)


def daily_quota() -> int:
    """Aaj max kitne DM."""
    if is_rest_day():
        return 0
    quota = profile_quota()
    ceiling = cap_ceiling()
    if ceiling is not None:
        quota = min(quota, ceiling)
    return quota


def is_warmup() -> bool:
    return db.day_number() <= config.WARMUP_CURVE[-1][0]


def remaining_today() -> int:
    return max(0, daily_quota() - db.sent_count())


def in_active_window(now: datetime | None = None) -> bool:
    hour = (now or datetime.now()).hour
    return config.ACTIVE_START_HOUR <= hour < config.ACTIVE_END_HOUR


def next_active_start(now: datetime | None = None) -> datetime:
    """Agla active window kab shuru hoga."""
    now = now or datetime.now()
    start = now.replace(
        hour=config.ACTIVE_START_HOUR, minute=0, second=0, microsecond=0
    )
    if now >= start:
        start += timedelta(days=1)
    return start


def in_cooldown() -> bool:
    until = db.cooldown_until()
    if until is None:
        return False
    if datetime.now() >= until:
        db.clear_cooldown()
        return False
    return True


def hour_budget_left() -> int:
    return max(0, config.MAX_DM_PER_HOUR - db.sent_last_hour())


def cap_budget_left() -> int | None:
    """Rolling 24 ghante me discovered cap se kitna bacha hai.

    Ye calendar-din wale quota se alag hai. Kal raat 11 baje 25 DM bheje aur
    aaj subah 11 baje 25 aur bhej diye to Instagram ke liye wo 50 in 12 hours hai,
    chahe do alag din hon. Isliye ye check zaruri hai.
    """
    ceiling = cap_ceiling()
    if ceiling is None:
        return None
    return max(0, ceiling - db.sent_last_24h())


def next_gap_seconds() -> int:
    return random.randint(config.MIN_GAP_SECONDS, config.MAX_GAP_SECONDS)


def can_send_now() -> tuple[bool, str]:
    """(bhej sakte hain?, kyun nahi) - reason ek short code hota hai."""
    if db.is_paused():
        return False, "paused"
    if in_cooldown():
        return False, "cooldown"
    if is_rest_day():
        return False, "rest"
    if not in_active_window():
        return False, "sleep"
    if remaining_today() <= 0:
        return False, "done"
    cap_left = cap_budget_left()
    if cap_left is not None and cap_left <= 0:
        return False, "cap24"
    if hour_budget_left() <= 0:
        return False, "hourly"
    if db.queue_size() <= 0:
        return False, "empty"
    return True, ""
