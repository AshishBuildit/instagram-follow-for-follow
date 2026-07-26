"""Naye followers detect karke unhe follow back karna."""

import logging
import random
from typing import Callable

from . import config, copy, db
from .ig import BlockSignal, ChallengeSignal, IGError, Instagram

log = logging.getLogger(__name__)

Notify = Callable[[str], None]


def seed_if_first_run(ig: Instagram) -> bool:
    """Pehli baar: purane followers ko 'done' mark karo.

    Warna bot ek saath 500 logon ko follow karne lagega, jo instant flag hai.
    """
    if db.get_setting("followers_seeded") == "1":
        return False
    followers = ig.my_followers()
    for pk, user in followers.items():
        db.add_follower(int(pk), user.username)
        db.mark_followed_back(int(pk))
    db.set_setting("followers_seeded", "1")
    log.info("%s purane followers seed kar diye", len(followers))
    return True


def detect_new(ig: Instagram) -> int:
    """Naye followers snapshot me daalo. Kitne naye mile wo return.

    Poori followers list nahi kheenchte. Instagram naye followers sabse upar
    deta hai, to pehle kuchh sau kaafi hain. Roz poora crawl karna khud ek
    bot signal hai.
    """
    known = db.known_follower_pks()
    followers = ig.my_followers(amount=config.FOLLOWER_SCAN_AMOUNT)
    new = 0
    for pk, user in followers.items():
        pk = int(pk)
        if pk not in known:
            db.add_follower(pk, user.username)
            new += 1
    return new


def run(ig: Instagram, notify: Notify, sleep: Callable[[float], None]) -> None:
    if not config.FOLLOWBACK_ENABLED:
        return
    if db.is_paused():
        return

    budget = config.FOLLOWBACK_DAILY_LIMIT - db.followbacks_today()
    if budget <= 0:
        return

    try:
        if seed_if_first_run(ig):
            notify(copy.FOLLOWBACK_SEEDED)
            return  # pehle din sirf list banti hai, follow kuch nahi
        detect_new(ig)
    except (BlockSignal, ChallengeSignal):
        raise
    except IGError as exc:
        log.warning("followback check fail: %s", exc)
        return

    # Zyada uthao, kyunki inme se kai already-following nikal jayenge
    pending = db.pending_followbacks(budget * 4)
    if not pending:
        return

    # Ye call mehngi hai, isliye tabhi karo jab sach me kisi ko follow karna ho
    try:
        already_following = ig.my_following_pks()
    except (BlockSignal, ChallengeSignal):
        raise
    except IGError as exc:
        log.warning("following list nahi mili: %s", exc)
        return

    done = 0
    for row in pending:
        if done >= budget:
            break
        pk = int(row["pk"])
        if pk in already_following:
            db.mark_followed_back(pk)  # pehle se follow kar rahe hain
            continue
        try:
            ig.follow(pk)
        except (BlockSignal, ChallengeSignal):
            raise
        except IGError as exc:
            log.warning("follow fail @%s: %s", row["username"], exc)
            continue
        db.mark_followed_back(pk)
        db.log_event("followback", row["username"] or str(pk))
        done += 1
        sleep(random.randint(config.FOLLOWBACK_MIN_GAP, config.FOLLOWBACK_MAX_GAP))

    if done:
        notify(copy.FOLLOWBACK_DONE.format(n=done))
