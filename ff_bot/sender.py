"""DM bhejne ka kaam. Ek baar me ek DM, phir random gap."""

import logging
import random
import re
from typing import Callable, Optional

from . import config, copy, db, scheduler
from .ig import BlockSignal, ChallengeSignal, DailyCapSignal, IGError, Instagram
from .scraper import is_alive, passes_profile

log = logging.getLogger(__name__)

Notify = Callable[[str], None]

_BAD_NAME = re.compile(r"[^A-Za-zऀ-ॿ' -]")

# Username me se nikle aise shabd naam nahi hote. Inke saath DM bot jaisa lagta hai.
_NOT_A_NAME = {
    "the", "official", "real", "its", "iam", "mr", "mrs", "miss", "user", "insta",
    "team", "page", "editz", "edits", "photography", "world", "life", "boy", "girl",
    "king", "queen", "love", "army", "fan", "club", "zone", "hub", "wala", "ff",
}


def _titled(word: str) -> str:
    return word[0].upper() + word[1:] if word else ""


def pretty_name(full_name: str, username: str) -> str:
    """Bhejne layak naam, ya khali string agar koi bharosemand naam na mile."""
    words = _BAD_NAME.sub(" ", full_name or "").split()
    for word in words:
        if len(word) >= 2 and word.lower() not in _NOT_A_NAME:
            return _titled(word if not word.isupper() else word.capitalize())

    # Username se guess: priya_23 -> Priya. Par sirf tab jab sach me naam lage.
    guess = re.split(r"[._0-9]", username or "")[0]
    if len(guess) >= 3 and guess.isalpha() and guess.lower() not in _NOT_A_NAME:
        return _titled(guess)

    return ""  # naam nahi mila, bina naam wala message jayega


def render(full_name: str, username: str, templates: Optional[list[str]] = None) -> str:
    tpl = random.choice(templates or db.get_template())
    name = pretty_name(full_name, username)
    if name:
        return tpl.replace("{name}", name)
    # Bina naam ke: "Hey {name}, f4f?" -> "Hey, f4f?" (adhoora nahi lagna chahiye)
    text = tpl.replace("{name}", "")
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def pick_target(ig: Instagram) -> Optional[tuple[int, object]]:
    """Queue se ek aisa banda dhoondo jo sach me DM ke layak ho."""
    checked = 0
    while checked < config.MAX_CANDIDATE_CHECKS:
        rows = db.next_targets(5)
        if not rows:
            return None

        progressed = False
        for row in rows:
            if checked >= config.MAX_CANDIDATE_CHECKS:
                break
            checked += 1
            pk = int(row["pk"])

            try:
                info = ig.user_info(pk)
            except (BlockSignal, ChallengeSignal, DailyCapSignal):
                raise
            except IGError as exc:
                db.skip_target(pk, str(exc)[:80])
                progressed = True
                continue

            ok, reason = passes_profile(info)
            if not ok:
                db.skip_target(pk, reason)
                progressed = True
                continue

            alive, why = is_alive(ig, pk, info)
            if not alive:
                db.skip_target(pk, why)
                progressed = True
                continue

            return pk, info

        if not progressed:
            return None
    return None


def send_one(ig: Instagram) -> bool:
    """Queue se ek target uthao aur DM bhejo. True agar sach me gaya."""
    picked = pick_target(ig)
    if picked is None:
        return False
    pk, info = picked

    text = render(info.full_name or "", info.username)
    try:
        ig.send_dm(pk, text)
    except (BlockSignal, ChallengeSignal, DailyCapSignal):
        raise
    except IGError as exc:
        db.record_send(pk, info.username, text, ok=False, error=str(exc)[:200])
        log.warning("DM fail @%s: %s", info.username, exc)
        return False

    db.record_send(pk, info.username, text, ok=True)
    log.info("DM gaya @%s", info.username)
    return True


def run_batch(ig: Instagram, notify: Notify, sleep: Callable[[float], None]) -> int:
    """Quota ya hourly budget khatam hone tak DM bhejo. Kitne gaye wo return."""
    sent = 0
    misses = 0
    while True:
        allowed, _why = scheduler.can_send_now()
        if not allowed:
            return sent

        if send_one(ig):
            sent += 1
            misses = 0
            ig.save_session()
            if scheduler.remaining_today() <= 0:
                notify(
                    copy.DAY_DONE.format(
                        ok=db.sent_count(), fail=db.failed_count(), queue=db.queue_size()
                    )
                )
                return sent
            sleep(scheduler.next_gap_seconds())
            continue

        # Kuch nahi gaya, matlab candidates filter me nikal rahe hain.
        # Do baar lagatar aisa ho to ruk jao, warna queue chhanne me hi
        # saara time aur saari API calls nikal jayengi.
        misses += 1
        if misses >= 2:
            return sent
        sleep(random.randint(20, 60))
