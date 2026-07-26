"""Instagram engine. instagrapi ka wrapper, session reuse ke saath.

Error ko theek se pehchanna yahan sabse important kaam hai:
  DailyCapSignal  = Instagram ka roz ka naya-chat cap. Bura nahi, bas kal aana.
  BlockSignal     = asli spam block. Sab band karo.
  ChallengeSignal = login verify chahiye.
  IGError         = normal error, ye target chhod ke aage badho.
"""

import html
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    ClientError,
    ClientForbiddenError,
    FeedbackRequired,
    LoginRequired,
    PleaseWaitFewMinutes,
    RateLimitError,
    UserNotFound,
)

from . import config

log = logging.getLogger(__name__)

BLOCK_ERRORS = (PleaseWaitFewMinutes, FeedbackRequired, RateLimitError, ClientForbiddenError)

# Ye Instagram ka soft daily cap hai, ban nahi. Isko alag treat karna zaruri hai.
_CAP_MARKERS = (
    "1545119",
    "new conversations",
    "limit to the number of",
)


class BlockSignal(Exception):
    """Instagram ne spam block laga diya. Sab band karo."""


class DailyCapSignal(Exception):
    """Aaj ke naye chat khatam. Kal phir se."""


class ChallengeSignal(Exception):
    """Login verify chahiye. User ko app kholna padega."""


class IGError(Exception):
    """Normal error, ek target skip karo aur aage badho."""


def clean_error(raw: str) -> str:
    """IG ka JSON error insaan ke padhne layak banao."""
    text = html.unescape(raw or "")
    match = re.search(r'"client_facing_error_message"\s*:\s*"([^"]+)"', text)
    if match:
        return html.unescape(match.group(1))
    try:
        data = json.loads(text)
        for key in ("client_facing_error_message", "message", "feedback_message"):
            if data.get(key):
                return html.unescape(str(data[key]))
    except (ValueError, AttributeError):
        pass
    return text[:300]


def _wrap(exc: Exception) -> Exception:
    raw = str(exc) or exc.__class__.__name__
    low = raw.lower()

    if isinstance(exc, (ChallengeRequired, LoginRequired)):
        return ChallengeSignal(clean_error(raw))
    if any(marker in low for marker in _CAP_MARKERS):
        return DailyCapSignal(clean_error(raw))
    if isinstance(exc, BLOCK_ERRORS):
        return BlockSignal(clean_error(raw))
    return IGError(clean_error(raw))


def _age_days(taken_at) -> float:
    if not isinstance(taken_at, datetime):
        return 9999.0
    when = taken_at if taken_at.tzinfo else taken_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).total_seconds() / 86400


class Instagram:
    def __init__(self) -> None:
        self.cl = Client()
        self.cl.delay_range = [2, 6]  # instagrapi khud requests ke beech ruk jayega
        self.me_pk: Optional[int] = None

    # --- login ---

    def login(self) -> str:
        """Session file se ya password se login. Username return karta hai."""
        if config.SESSION_PATH.exists():
            try:
                self.cl.load_settings(config.SESSION_PATH)
                self.cl.login(config.IG_USERNAME, config.IG_PASSWORD)
                self.cl.get_timeline_feed()  # session sach me zinda hai?
                self.me_pk = self.cl.user_id
                # Refresh hui values wapas file me, warna session dheere dheere baasi ho jata hai
                self.cl.dump_settings(config.SESSION_PATH)
                log.info("session se login ho gaya")
                return config.IG_USERNAME
            except Exception as exc:  # noqa: BLE001
                log.warning("session kaam nahi kiya, fresh login kar raha hoon")
                log.debug("session error: %s", exc)
                self.cl = Client()
                self.cl.delay_range = [2, 6]

        try:
            self.cl.login(config.IG_USERNAME, config.IG_PASSWORD)
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.cl.dump_settings(config.SESSION_PATH)
        self.me_pk = self.cl.user_id
        return config.IG_USERNAME

    # --- reads ---

    def user_id(self, username: str) -> int:
        try:
            return int(self.cl.user_id_from_username(username))
        except UserNotFound as exc:
            raise IGError(f"@{username} mila nahi") from exc
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    def followers(self, user_pk: int, amount: int) -> dict:
        """{pk: UserShort} - reference page ko follow karne wale."""
        try:
            return self.cl.user_followers(user_pk, amount=amount)
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    def following(self, user_pk: int, amount: int) -> dict:
        """{pk: UserShort} - reference page jinko follow karta hai."""
        try:
            return self.cl.user_following(user_pk, amount=amount)
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    def user_info(self, user_pk: int):
        try:
            return self.cl.user_info(user_pk)
        except UserNotFound as exc:
            raise IGError("account exist nahi karta") from exc
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    def has_story(self, user_pk: int) -> bool:
        """Abhi koi active story hai? Zinda account ka sabse pakka signal."""
        try:
            return bool(self.cl.user_stories(user_pk, amount=1))
        except (ChallengeRequired, LoginRequired) as exc:
            raise _wrap(exc) from exc
        except Exception as exc:  # noqa: BLE001
            wrapped = _wrap(exc)
            if isinstance(wrapped, (BlockSignal, DailyCapSignal)):
                raise wrapped from exc
            return False

    def last_post_age_days(self, user_pk: int) -> float:
        """Aakhri post kitne din purani. Nahi pata chala to bada number."""
        try:
            medias = self.cl.user_medias(user_pk, amount=1)
        except (ChallengeRequired, LoginRequired) as exc:
            raise _wrap(exc) from exc
        except Exception as exc:  # noqa: BLE001
            wrapped = _wrap(exc)
            if isinstance(wrapped, (BlockSignal, DailyCapSignal)):
                raise wrapped from exc
            return 9999.0
        if not medias:
            return 9999.0
        return _age_days(getattr(medias[0], "taken_at", None))

    def my_followers(self, amount: int = 0) -> dict:
        """amount=0 matlab poori list. Roz ke check me hamesha limit do."""
        if self.me_pk is None:
            raise IGError("login nahi hua")
        try:
            return self.cl.user_followers(self.me_pk, amount=amount)
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    def my_following_pks(self) -> set[int]:
        if self.me_pk is None:
            raise IGError("login nahi hua")
        try:
            return {int(pk) for pk in self.cl.user_following(self.me_pk)}
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    # --- writes ---

    def send_dm(self, user_pk: int, text: str) -> None:
        if config.DRY_RUN:
            log.info("[DRY RUN] DM -> %s: %s", user_pk, text)
            return
        try:
            self.cl.direct_send(text, user_ids=[user_pk])
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    def follow(self, user_pk: int) -> None:
        if config.DRY_RUN:
            log.info("[DRY RUN] follow -> %s", user_pk)
            return
        try:
            self.cl.user_follow(user_pk)
        except Exception as exc:  # noqa: BLE001
            raise _wrap(exc) from exc

    def save_session(self) -> None:
        try:
            self.cl.dump_settings(config.SESSION_PATH)
        except (OSError, ClientError):
            log.warning("session save nahi hua")
