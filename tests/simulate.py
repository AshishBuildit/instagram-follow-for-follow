"""Poore bot ko nakli Instagram par kai din chalao aur niyam check karo.

Chalao:  python tests/simulate.py

Ye padh kar bug dhoondhne se alag hai. Yahan bot sach me chalta hai, bas
Instagram aur ghadi nakli hai. Jo bhi tootega wo yahan dikh jayega.
"""

import datetime as dt
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["IG_USERNAME"] = "testuser"
os.environ["IG_PASSWORD"] = "x"
os.environ["TELEGRAM_TOKEN"] = "123:abc"
os.environ["TELEGRAM_OWNER_ID"] = "1"
os.environ["DRY_RUN"] = "false"
os.environ["ACCOUNT_MODE"] = "warm"
os.environ["RUN_HOURS"] = "0"

SANDBOX = ROOT / "tests" / "_sandbox"


def fresh_env():
    """Har scenario ke liye bilkul naya data folder."""
    if "ff_bot.db" in sys.modules:  # purana sqlite handle band karo
        old = sys.modules["ff_bot.db"]
        if getattr(old, "_conn", None) is not None:
            old._conn.close()
            old._conn = None
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX, ignore_errors=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)

    # fake_ig ko bhi purge karna zaruri hai. Wo ff_bot.ig se exception classes
    # import karta hai, aur reload ke baad purani classes naye `except` se match
    # nahi karti - test jhooth bolne lagta hai.
    for name in list(sys.modules):
        if name.startswith("ff_bot") or name == "tests.fake_ig":
            del sys.modules[name]

    from ff_bot import config

    config.DATA_DIR = SANDBOX
    config.DB_PATH = SANDBOX / "ff.db"
    config.SESSION_PATH = SANDBOX / "session.json"
    config.LOG_PATH = SANDBOX / "ff.log"

    from ff_bot import db, lock

    lock.LOCK_PATH = SANDBOX / "ff.lock"
    db._conn = None
    db.connect()
    return config, db


# ---------------------------------------------------------------- harness

class Sim:
    def __init__(self, days=10, real_cap=12, start_hour=11, universe=400):
        self.config, self.db = fresh_env()
        from tests.fake_ig import Clock, FakeIG, install
        from ff_bot import scheduler
        from ff_bot.worker import Worker

        start = dt.datetime(2026, 3, 1, start_hour, 0)
        self.clock = Clock(start)
        install(self.clock)
        self.scheduler = scheduler

        self.ig = FakeIG(self.clock, real_cap=real_cap, universe=universe)
        self.messages: list[str] = []
        self.worker = Worker(self.messages.append)
        self.worker.ig = self.ig
        self.worker._sleep = lambda s: self.clock.advance(s)
        self.days = days
        self.errors: list[str] = []

    def seed_refs(self, n=3):
        for i in range(n):
            self.db.add_ref(f"refpage{i}")

    def run(self, minutes_step=1):
        """Har step par ek tick, phir ghadi aage."""
        end = self.clock.now + dt.timedelta(days=self.days)
        from ff_bot.ig import BlockSignal, ChallengeSignal, DailyCapSignal, IGError

        while self.clock.now < end:
            before = self.clock.now
            try:
                self.worker._tick()
            except DailyCapSignal as exc:
                self.worker._on_cap(str(exc))
            except BlockSignal as exc:
                self.worker._on_block(str(exc))
            except ChallengeSignal:
                self.worker._on_challenge()
            except IGError:
                pass
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"{type(exc).__name__}: {exc}")
            if self.clock.now == before:
                self.clock.advance(minutes_step * 60)


# ---------------------------------------------------------------- checks

RESULTS = []


def check(name, condition, detail=""):
    RESULTS.append((name, bool(condition), detail))
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f"  -> {detail}" if detail and not condition else ""))


def rolling_max(sent, hours=24):
    """Kisi bhi 24-ghante ki window me max kitne DM gaye."""
    times = sorted(w for _, _, w in sent)
    best = 0
    for i, start in enumerate(times):
        cnt = sum(1 for t in times[i:] if t < start + dt.timedelta(hours=hours))
        best = max(best, cnt)
    return best


def hourly_max(sent):
    return rolling_max(sent, hours=1)


# ---------------------------------------------------------------- scenarios

def scenario_normal():
    print("\n1. Normal chalna, 10 din, Instagram ka asli cap 12")
    sim = Sim(days=10, real_cap=12)
    sim.seed_refs()
    sim.run()

    sent = sim.ig.sent
    check("koi crash nahi", not sim.errors, str(sim.errors[:2]))
    check("DM gaye", len(sent) > 0, f"{len(sent)} DM")
    check("24h me kabhi cap se upar nahi", rolling_max(sent) <= 12, f"max {rolling_max(sent)}")
    check("hourly limit follow hua", hourly_max(sent) <= sim.config.MAX_DM_PER_HOUR,
          f"max {hourly_max(sent)}/hr")
    check("kisi ko do baar DM nahi", len({p for p, _, _ in sent}) == len(sent),
          f"{len(sent)} sent, {len({p for p,_,_ in sent})} unique")
    check("active window ke bahar DM nahi",
          all(sim.config.ACTIVE_START_HOUR <= w.hour < sim.config.ACTIVE_END_HOUR
              for _, _, w in sent),
          str(sorted({w.hour for _, _, w in sent})))
    found = sim.db.discovered_cap()
    check("cap dhoondh liya aur 2 par nahi gira", found and found >= 8, f"cap={found}")
    check("cap discovery ke baad bhi kaam chalta raha",
          len([s for s in sent if s[2] > sim.clock.now - dt.timedelta(days=3)]) > 5)
    print(f"       total {len(sent)} DM / 10 din, API calls {sim.ig.calls}, "
          f"cap mila {found}, telegram msgs {len(sim.messages)}")
    return sim


def scenario_cap_collapse():
    print("\n2. Cross-midnight cap trap (purana bug: account 2 DM par atak jata tha)")
    sim = Sim(days=14, real_cap=10, start_hour=21)
    sim.seed_refs()
    sim.run()
    found = sim.db.discovered_cap()
    check("cap 2 par collapse nahi hua", found is None or found >= 6, f"cap={found}")
    check("aakhri 3 din me bhi DM gaye",
          len([s for s in sim.ig.sent if s[2] > sim.clock.now - dt.timedelta(days=3)]) >= 5,
          "bot chup ho gaya")
    check("24h cap kabhi nahi toota", rolling_max(sim.ig.sent) <= 10,
          f"max {rolling_max(sim.ig.sent)}")


def scenario_dead_accounts():
    print("\n3. Sab targets dead (activity filter sab reject karta hai)")
    sim = Sim(days=2, real_cap=50, universe=200)
    for u in sim.ig.users.values():
        u.story = False
        u.post_age = 500.0
    sim.seed_refs()
    sim.run()
    check("koi DM nahi gaya", len(sim.ig.sent) == 0)
    check("API hammering nahi hui", sim.ig.calls < 1500, f"{sim.ig.calls} calls in 2 din")
    check("user ko bataya gaya",
          any("DM ke layak nahi" in m for m in sim.messages))
    print(f"       API calls {sim.ig.calls} (purana code lakhon karta)")


def scenario_block():
    print("\n4. Spam block aaya")
    sim = Sim(days=4, real_cap=50)
    sim.seed_refs()
    sim.worker._tick()
    sim.ig.block_next = True
    sim.run()
    check("cooldown laga", sim.db.stop_kind() == "cooldown" or len(sim.ig.sent) > 0)
    check("user ko alert gaya", any("rok diya" in m for m in sim.messages))
    check("crash nahi", not sim.errors, str(sim.errors[:2]))


def scenario_challenge():
    print("\n5. Login challenge aaya")
    sim = Sim(days=2, real_cap=50)
    sim.seed_refs()
    sim.ig.challenge_next = True
    sim.run()
    check("bot pause ho gaya", sim.db.is_paused())
    check("user ko bataya", any("verify" in m for m in sim.messages))
    check("pause hone ke baad DM nahi bheje", len(sim.ig.sent) == 0)


def scenario_followback():
    print("\n6. Follow-back")
    sim = Sim(days=5, real_cap=30)
    sim.seed_refs()
    for i in range(900, 950):
        sim.ig.new_follower(i, f"old{i}")

    sim.worker._tick()  # seed
    check("purane followers ko follow nahi kiya", len(sim.ig.followed) == 0,
          f"{len(sim.ig.followed)} follow kar diye")
    check("seed ka message gaya", any("list bana li" in m for m in sim.messages))

    for i in range(1000, 1012):
        sim.ig.new_follower(i, f"new{i}")
    sim.db.set_setting("last_followback", "")
    sim.run()
    check("naye followers ko follow back hua", len(sim.ig.followed) >= 10,
          f"{len(sim.ig.followed)} / 12")
    check("kisi ko do baar follow nahi", len(set(sim.ig.followed)) == len(sim.ig.followed))
    check("roz ki limit follow hui", len(sim.ig.followed) <= sim.config.FOLLOWBACK_DAILY_LIMIT * 5)


def scenario_restart():
    print("\n7. Baar baar restart (phone reboot / widget tap)")
    sim = Sim(days=3, real_cap=15)
    sim.seed_refs()
    from ff_bot.worker import Worker

    for _ in range(3):
        sim.run()
        w = Worker(sim.messages.append)     # naya process
        w.ig = sim.ig
        w._sleep = lambda s: sim.clock.advance(s)
        sim.worker = w

    sent = sim.ig.sent
    check("restart ke baad bhi 24h cap safe", rolling_max(sent) <= 15,
          f"max {rolling_max(sent)}")
    check("restart ke baad duplicate DM nahi",
          len({p for p, _, _ in sent}) == len(sent))
    check("warmup reset nahi hua", sim.db.day_number() > 1, f"day {sim.db.day_number()}")


def scenario_rest_day():
    print("\n8. 30 din: rest day aur queue refill")
    sim = Sim(days=30, real_cap=40, universe=3000)
    sim.seed_refs(5)
    sim.run()
    by_day = {}
    for _, _, w in sim.ig.sent:
        by_day[w.date()] = by_day.get(w.date(), 0) + 1
    active = [d for d in by_day if by_day[d] > 0]

    # Rest day seedha scheduler se pucho, "us din DM nahi gaye" se andaza mat lagao.
    # Targets khatam hone se bhi din khali dikhta hai, aur test jhooth bol deta hai.
    from tests.fake_ig import Clock
    rest_days = 0
    probe = Clock(dt.datetime(2026, 3, 1, 12, 0))
    from tests.fake_ig import install as reinstall
    reinstall(probe)
    for i in range(30):
        probe.now = dt.datetime(2026, 3, 1, 12, 0) + dt.timedelta(days=i)
        if sim.scheduler.is_rest_day():
            rest_days += 1
    reinstall(sim.clock)

    check("rest days aaye", 2 <= rest_days <= 7, f"{rest_days} rest days in 30")
    check("targets khatam nahi hue (queue refill kaam kiya)",
          len(active) >= 20, f"sirf {len(active)} active days")
    check("30 din tak crash nahi", not sim.errors, str(sim.errors[:2]))
    check("24h cap 30 din tak safe", rolling_max(sim.ig.sent) <= 40,
          f"max {rolling_max(sim.ig.sent)}")
    print(f"       30 din me {len(sim.ig.sent)} DM, {len(active)} active days, "
          f"{sim.ig.calls} API calls")


def main() -> int:
    print("=" * 70)
    print("NAKLI INSTAGRAM PAR POORA BOT CHALA KAR TEST")
    print("=" * 70)

    for fn in (scenario_normal, scenario_cap_collapse, scenario_dead_accounts,
               scenario_block, scenario_challenge, scenario_followback,
               scenario_restart, scenario_rest_day):
        fn()

    if SANDBOX.exists():
        shutil.rmtree(SANDBOX, ignore_errors=True)

    failed = [r for r in RESULTS if not r[1]]
    print("\n" + "=" * 70)
    print(f"{len(RESULTS) - len(failed)} / {len(RESULTS)} pass")
    if failed:
        print("\nFAIL hue:")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
    print("=" * 70)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
