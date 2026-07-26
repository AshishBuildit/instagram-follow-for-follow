"""Background loop. Login, scrape, DM, follow-back, repeat."""

import logging
import threading
import time
from datetime import date

from . import config, copy, db, followback, scheduler, scraper, sender
from .ig import BlockSignal, ChallengeSignal, DailyCapSignal, IGError, Instagram

log = logging.getLogger(__name__)

IDLE_SLEEP = 60


class Worker(threading.Thread):
    def __init__(self, notify, shutdown=None) -> None:
        super().__init__(daemon=True, name="ff-worker")
        self.notify = notify
        self.shutdown = shutdown or (lambda: None)
        self.ig = Instagram()
        self.stop_flag = threading.Event()
        self.active_seconds = 0.0  # sirf wo waqt jab bot sach me kaam kar sakta tha
        self._last_mark = time.monotonic()
        self._logged_in = False
        self._announced_day: date | None = None

    # sleep jo stop hone par turant toot jaye
    def _sleep(self, seconds: float) -> None:
        self.stop_flag.wait(seconds)

    def stop(self) -> None:
        self.stop_flag.set()

    # --- error handling ---

    def _on_cap(self, reason: str) -> None:
        """Instagram ka rolling 24-ghante ka naya-chat cap. Ban nahi hai.

        Ginti rolling 24 ghante ki hoti hai, aaj ki nahi. Kal raat 12 DM bhej ke
        cap laga tha, aur aaj subah pehle hi DM par phir laga, to "aaj 0 gaye"
        maan lena galat hoga - us hisaab se cap 1 record ho jata aur account
        hamesha ke liye 2 DM par atak jata.
        """
        window = db.sent_last_24h()
        until = scheduler.next_active_start()
        db.stop_until(until, "daily_cap", reason)

        if window <= 0:
            # Kuch bheje bina hi cap. Purana cap chhedna nahi hai.
            db.log_event("cap", "bina bheje cap laga, cap number nahi badla")
            self.notify(copy.DAILY_CAP_EARLY.format(until=until.strftime("%d %b, %H:%M")))
            return

        found = db.record_cap_hit(window)
        self.notify(
            copy.DAILY_CAP.format(
                sent=window,
                cap=max(2, found - config.CAP_SAFETY_MARGIN),
                until=until.strftime("%d %b, %H:%M"),
            )
        )

    def _on_block(self, reason: str) -> None:
        db.start_cooldown(config.COOLDOWN_HOURS, reason)
        self.notify(copy.COOLDOWN_HIT.format(hours=config.COOLDOWN_HOURS, reason=reason))

    def _on_challenge(self) -> None:
        self._logged_in = False
        db.set_paused(True)
        self.notify(copy.CHALLENGE)

    # --- steps ---

    def _ensure_login(self) -> bool:
        if self._logged_in:
            return True
        try:
            user = self.ig.login()
        except ChallengeSignal:
            self._on_challenge()
            return False
        except DailyCapSignal as exc:
            self._on_cap(str(exc))
            return False
        except BlockSignal as exc:
            self._on_block(str(exc))
            return False
        except Exception as exc:  # noqa: BLE001
            self.notify(copy.LOGIN_FAILED.format(reason=exc))
            db.set_paused(True)
            return False
        self._logged_in = True
        log.info("logged in as @%s", user)
        return True

    def _announce_day(self) -> None:
        today = date.today()
        if self._announced_day == today:
            return
        self._announced_day = today
        if scheduler.is_rest_day():
            self.notify(copy.REST_DAY)
        else:
            self.notify(copy.STARTED.format(day=db.day_number(), quota=scheduler.daily_quota()))

    def _maybe_followback(self) -> None:
        """Din me ek baar. Restart ke baad dobara na chale isliye DB me yaad rehta hai."""
        if not config.FOLLOWBACK_ENABLED:
            return
        mins = db.minutes_since("last_followback")
        if mins is not None and mins < config.FOLLOWBACK_EVERY_MINUTES:
            return
        db.set_time("last_followback")
        followback.run(self.ig, self.notify, self._sleep)

    def _maybe_refill(self) -> None:
        """Queue bharo, par gap ke saath.

        Bina gap ke ye har 60 second par har reference page ka poora followers
        crawl kar deta tha. Wahi cheez Instagram ko sabse pehle dikhti hai.
        """
        if db.queue_size() >= config.QUEUE_REFILL_THRESHOLD:
            return
        if not db.list_refs():
            self._warn_once("no_refs", copy.REF_EMPTY)
            return

        mins = db.minutes_since("last_refill")
        gap = (
            config.REFILL_BACKOFF_MINUTES
            if db.get_setting("last_refill_empty") == "1"
            else config.REFILL_GAP_MINUTES
        )
        if mins is not None and mins < gap:
            return

        db.set_time("last_refill")
        added = scraper.refill_queue(self.ig, self.notify, self._sleep)
        db.set_setting("last_refill_empty", "1" if added <= 0 else "0")
        if added <= 0 and db.queue_size() == 0:
            self._warn_once("refs_dry", copy.REFS_DRY)

    def _warn_once(self, key: str, text: str) -> None:
        """Ek hi warning baar baar Telegram par mat bhejo."""
        mins = db.minutes_since(f"warned_{key}")
        if mins is not None and mins < config.WARN_REPEAT_MINUTES:
            return
        db.set_time(f"warned_{key}")
        self.notify(text)

    def _mark_time(self) -> None:
        """RUN_HOURS sirf kaam ka waqt gine.

        Raat 3 baje phone restart hua to bot 3 ghante khali baith ke exit na kar jaye.
        Sote hue, rest day par, ya cooldown me clock nahi chalta.
        """
        now = time.monotonic()
        elapsed = now - self._last_mark
        self._last_mark = now
        if scheduler.in_active_window() and not scheduler.in_cooldown() and not db.is_paused():
            self.active_seconds += elapsed

    def _time_up(self) -> tuple[bool, str]:
        """(band karein?, kyun). RUN_HOURS = 0 matlab kabhi nahi."""
        if config.RUN_HOURS <= 0:
            return False, ""
        if self.active_seconds >= config.RUN_HOURS * 3600:
            return True, "hours"
        # Kaam shuru ho chuka tha aur ab active window khatam ho gaya.
        # Raat bhar khali chalte rehna phone ki battery kha jata hai.
        if self.active_seconds > 0 and not scheduler.in_active_window():
            return True, "window"
        return False, ""

    # --- main loop ---

    def run(self) -> None:
        db.first_run_date()
        while not self.stop_flag.is_set():
            self._mark_time()
            done, why = self._time_up()
            if done:
                text = copy.SESSION_OVER if why == "hours" else copy.SESSION_WINDOW_OVER
                self.notify(
                    text.format(hours=config.RUN_HOURS, sent=db.sent_count())
                )
                self.shutdown()
                return
            try:
                self._tick()
            except DailyCapSignal as exc:
                self._on_cap(str(exc))
            except BlockSignal as exc:
                self._on_block(str(exc))
            except ChallengeSignal:
                self._on_challenge()
            except IGError as exc:
                log.warning("skip: %s", exc)
            except Exception as exc:  # noqa: BLE001
                log.exception("worker me error")
                db.log_event("error", str(exc)[:300])
            self._sleep(IDLE_SLEEP)

    def _tick(self) -> None:
        if db.is_paused() or scheduler.in_cooldown():
            return
        if not self._ensure_login():
            return

        self._announce_day()

        if scheduler.is_rest_day() or not scheduler.in_active_window():
            return

        self._maybe_followback()
        self._maybe_refill()

        allowed, why = scheduler.can_send_now()
        if not allowed:
            if why == "empty":
                self._warn_once("queue_empty", copy.QUEUE_EMPTY)
            return

        # Pichhli baar poori batch me ek bhi DM nahi gaya (sab filter me nikal gaye).
        # Turant dobara koshish karna matlab har minute 24 profile check karna,
        # jo khud sabse bada bot signal hai.
        mins = db.minutes_since("last_dry_batch")
        if mins is not None and mins < config.DRY_BATCH_BACKOFF_MINUTES:
            return

        sent = sender.run_batch(self.ig, self.notify, self._sleep)
        if sent == 0:
            db.set_time("last_dry_batch")
            self._warn_once("all_filtered", copy.ALL_FILTERED)
        else:
            db.set_setting("last_dry_batch", "")
