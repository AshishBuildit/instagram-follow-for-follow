"""Reference pages se targets nikalna aur quality filter lagana."""

import logging
import random
import time
from typing import Callable

from . import config, db
from .ig import BlockSignal, ChallengeSignal, DailyCapSignal, IGError, Instagram

log = logging.getLogger(__name__)

Notify = Callable[[str], None]


def passes_shallow(user) -> tuple[bool, str]:
    """Followers list se jo halka data milta hai uspar pehla filter. Zero API cost."""
    if config.SKIP_PRIVATE and getattr(user, "is_private", False):
        return False, "private"
    if getattr(user, "is_verified", False):
        return False, "verified"
    if config.SKIP_NO_PROFILE_PIC and not getattr(user, "profile_pic_url", None):
        return False, "no pic"
    return True, ""


def passes_profile(info) -> tuple[bool, str]:
    """user_info ke baad ka filter."""
    if config.SKIP_PRIVATE and info.is_private:
        return False, "private"
    if info.follower_count and info.follower_count > config.MAX_TARGET_FOLLOWERS:
        return False, "bada account"
    if info.following_count and info.following_count > config.MAX_TARGET_FOLLOWING:
        return False, "follow-bot"
    if (info.media_count or 0) < config.MIN_TARGET_POSTS:
        return False, "post kam hain"
    return True, ""


def is_alive(ig: Instagram, pk: int, info) -> tuple[bool, str]:
    """Sach me zinda banda hai ya dead/bot account?

    Sabse pakka signal story hai. Story na ho to dekho ki haal filhaal me
    post kiya hai ya nahi.
    """
    if not config.CHECK_ACTIVITY:
        return True, ""
    if ig.has_story(pk):
        return True, "story"
    if (info.media_count or 0) == 0:
        return False, "dead"
    age = ig.last_post_age_days(pk)
    if age <= config.MAX_LAST_POST_DAYS:
        return True, "recent post"
    return False, "dead"


def scrape_ref(ig: Instagram, username: str, my_following: set[int]) -> int:
    """Ek reference page ki list se targets queue me daalo. Kitne naye mile wo return."""
    try:
        ref_pk = ig.user_id(username)
        if config.SCRAPE_SOURCE == "followers":
            people = ig.followers(ref_pk, amount=config.SCRAPE_PER_REF)
        else:
            people = ig.following(ref_pk, amount=config.SCRAPE_PER_REF)
    except (BlockSignal, ChallengeSignal, DailyCapSignal):
        raise
    except IGError as exc:
        log.warning("@%s scan fail: %s", username, exc)
        return -1

    items = list(people.items())
    random.shuffle(items)  # hamesha list ke upar wale hi nahi

    added = 0
    for pk, user in items:
        pk = int(pk)
        if pk in my_following or pk == ig.me_pk:
            continue
        if db.target_exists(pk):
            continue
        ok, _reason = passes_shallow(user)
        if not ok:
            continue
        if db.add_target(pk, user.username, getattr(user, "full_name", "") or "", username):
            added += 1

    db.mark_ref_scraped(username, added)
    log.info("@%s ki %s list se %s naye targets", username, config.SCRAPE_SOURCE, added)
    return added


def refill_queue(ig: Instagram, notify: Notify, sleep: Callable[[float], None] = time.sleep) -> int:
    """Queue kam ho to sabse purane scrape wale refs dobara scan karo.

    Ek hi summary message bhejta hai, har ref ka alag nahi.
    """
    refs = db.list_refs()
    if not refs:
        return 0

    try:
        my_following = ig.my_following_pks()
    except (BlockSignal, ChallengeSignal, DailyCapSignal):
        raise
    except IGError:
        my_following = set()

    order = sorted(refs, key=lambda r: r["last_scrape"] or "")
    total = 0
    failed: list[str] = []
    for ref in order:
        got = scrape_ref(ig, ref["username"], my_following)
        if got < 0:
            failed.append(ref["username"])
        else:
            total += got
        if db.queue_size() >= config.QUEUE_REFILL_THRESHOLD * 3:
            break
        sleep(random.randint(20, 60))  # refs ke beech saans lo

    if total:
        notify(f"{total} naye log queue me add kar diye. Total {db.queue_size()} hain.")
    if failed:
        notify("Ye pages scan nahi hue: " + ", ".join("@" + u for u in failed))
    return total
