"""Nakli Instagram aur nakli ghadi, taki poora bot bina asli account ke chalaya ja sake."""

import datetime as _dt
from typing import Optional

from ff_bot.ig import BlockSignal, ChallengeSignal, DailyCapSignal, IGError


class Clock:
    """Nakli ghadi. Bot jab sota hai, ghadi aage kood jati hai."""

    def __init__(self, start: _dt.datetime) -> None:
        self.now = start
        self.slept = 0.0

    def advance(self, seconds: float) -> None:
        self.now += _dt.timedelta(seconds=seconds)
        self.slept += seconds


_clock: Optional[Clock] = None


def install(clock: Clock) -> None:
    """db aur scheduler ki datetime/date ko nakli se badal do."""
    global _clock
    _clock = clock

    class FakeDT(_dt.datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001
            return _clock.now

    class FakeDate(_dt.date):
        @classmethod
        def today(cls):
            return _clock.now.date()

    from ff_bot import db, scheduler

    for mod in (db, scheduler):
        mod.datetime = FakeDT
        mod.date = FakeDate


class FakeUser:
    def __init__(self, pk, username, full_name="", private=False, verified=False,
                 followers=500, following=300, posts=20, story=False, post_age=2.0):
        self.pk = pk
        self.username = username
        self.full_name = full_name
        self.is_private = private
        self.is_verified = verified
        self.profile_pic_url = "http://x/pic.jpg"
        self.follower_count = followers
        self.following_count = following
        self.media_count = posts
        self.story = story
        self.post_age = post_age


class FakeIG:
    """Asli Instagram jaisa behave karta hai, limits aur errors ke saath."""

    def __init__(self, clock: Clock, real_cap=12, universe=200, dead_ratio=0.5):
        self.clock = clock
        self.real_cap = real_cap          # Instagram ka asli chhupa hua 24h cap
        self.me_pk = 1
        self.sent: list[tuple[int, str, _dt.datetime]] = []
        self.followed: list[int] = []
        self.my_followers_map: dict[int, FakeUser] = {}  # naam `followers` nahi, wo method hai
        self.my_following_set: set[int] = set()  # naam `following` nahi, wo method hai
        self.challenge_next = False
        self.block_next = False
        self.calls = 0

        self.users: dict[int, FakeUser] = {}
        for i in range(100, 100 + universe):
            dead = (i % 2 == 0) if dead_ratio >= 0.5 else False
            self.users[i] = FakeUser(
                i, f"user{i}", ["Priya Sharma", "", "Rahul K", "Aditi 🌸"][i % 4],
                story=not dead, post_age=90.0 if dead else 2.0,
            )

    # --- ginti ---

    def _sent_last_24h(self) -> int:
        cutoff = self.clock.now - _dt.timedelta(hours=24)
        return sum(1 for _, _, when in self.sent if when >= cutoff)

    def _maybe_raise(self):
        if self.challenge_next:
            self.challenge_next = False
            raise ChallengeSignal("challenge_required")
        if self.block_next:
            self.block_next = False
            raise BlockSignal("feedback_required: spam")

    # --- API ---

    def login(self) -> str:
        self._maybe_raise()
        return "testuser"

    def save_session(self) -> None:
        pass

    def user_id(self, username):
        self.calls += 1
        # Har reference page ka alag id, taki unke followers bhi alag hon
        return 5000 + (hash(username) % 1000)

    def _slice(self, user_pk, amount, offset=0):
        # Alag ref = alag slice. Warna queue ek hi 300 logon par atak jati hai
        # aur test jhooth bolta hai ki "rest day aaye" jabki asal me targets khatam the.
        items = list(self.users.items())
        if not items:
            return {}
        start = (user_pk * 37 + offset) % len(items)
        rotated = items[start:] + items[:start]
        return dict(rotated[:amount])

    def followers(self, user_pk, amount):
        self.calls += 1
        return self._slice(user_pk, amount)

    def following(self, user_pk, amount):
        self.calls += 1
        return self._slice(user_pk, amount, offset=13)

    def user_info(self, pk):
        self.calls += 1
        self._maybe_raise()
        if pk not in self.users:
            raise IGError("account exist nahi karta")
        return self.users[pk]

    def has_story(self, pk):
        self.calls += 1
        return self.users[pk].story if pk in self.users else False

    def last_post_age_days(self, pk):
        self.calls += 1
        return self.users[pk].post_age if pk in self.users else 9999.0

    def my_followers(self, amount=0):
        self.calls += 1
        items = list(self.my_followers_map.items())
        items.reverse()  # asli Instagram naye followers sabse upar deta hai
        return dict(items[:amount] if amount else items)

    def my_following_pks(self):
        self.calls += 1
        return set(self.my_following_set)

    def send_dm(self, pk, text):
        self.calls += 1
        self._maybe_raise()
        if self._sent_last_24h() >= self.real_cap:
            raise DailyCapSignal(
                "Your message can't be delivered. There is a limit to the number of "
                "new conversations you can start every 24 hours with people who don't follow you."
            )
        self.sent.append((pk, text, self.clock.now))

    def follow(self, pk):
        self.calls += 1
        self._maybe_raise()
        self.followed.append(pk)
        self.my_following_set.add(pk)

    # --- test helper ---

    def new_follower(self, pk, username="fan"):
        self.my_followers_map[pk] = FakeUser(pk, username)
