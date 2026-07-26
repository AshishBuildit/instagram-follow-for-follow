"""SQLite storage. Ek hi connection, thread-safe lock ke saath."""

import re
import sqlite3
import threading
from datetime import date, datetime, timedelta
from typing import Any, Optional

from . import config

_lock = threading.RLock()
_conn: Optional[sqlite3.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS refs (
    username    TEXT PRIMARY KEY,
    added_at    TEXT NOT NULL,
    last_scrape TEXT,
    found       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS targets (
    pk          INTEGER PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    full_name   TEXT,
    source_ref  TEXT,
    status      TEXT NOT NULL DEFAULT 'new',   -- new | sent | skipped | failed
    reason      TEXT,
    added_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_targets_status ON targets(status);

CREATE TABLE IF NOT EXISTS sent_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pk        INTEGER,
    username  TEXT NOT NULL,
    message   TEXT,
    ok        INTEGER NOT NULL,
    error     TEXT,
    sent_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sent_at ON sent_log(sent_at);

CREATE TABLE IF NOT EXISTS followers_snapshot (
    pk           INTEGER PRIMARY KEY,
    username     TEXT,
    seen_at      TEXT NOT NULL,
    followed_back INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    kind     TEXT NOT NULL,
    detail   TEXT,
    at       TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            fresh = not config.DB_PATH.exists()
            _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.executescript(SCHEMA)
            _conn.commit()
            if fresh and config.DRY_RUN:
                _seed_dryrun_from_real()
        return _conn


def _seed_dryrun_from_real() -> None:
    """Dry run me reference pages aur message dobara na daalne pade."""
    real = config.DATA_DIR / "ff.db"
    if not real.exists():
        return
    try:
        src = sqlite3.connect(real)
        src.row_factory = sqlite3.Row
        refs = src.execute("SELECT username, added_at FROM refs").fetchall()
        tpl = src.execute("SELECT value FROM settings WHERE key = 'template'").fetchone()
        src.close()
    except sqlite3.Error:
        return

    for row in refs:
        _conn.execute(
            "INSERT OR IGNORE INTO refs(username, added_at) VALUES(?, ?)",
            (row["username"], row["added_at"]),
        )
    if tpl:
        _conn.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES('template', ?)", (tpl["value"],)
        )
    _conn.commit()


def _exec(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    with _lock:
        cur = connect().execute(sql, params)
        connect().commit()
        return cur


def _all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        return connect().execute(sql, params).fetchall()


def _one(sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    with _lock:
        return connect().execute(sql, params).fetchone()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# --- settings ---

def get_setting(key: str, default: Any = None) -> Any:
    row = _one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: Any) -> None:
    _exec(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


def get_template() -> list[str]:
    """Message variations ki list. `|` se separated store hoti hai."""
    raw = get_setting("template", config.DEFAULT_TEMPLATE)
    parts = [p.strip() for p in str(raw).split("|") if p.strip()]
    return parts or [config.DEFAULT_TEMPLATE]


def set_template(text: str) -> None:
    set_setting("template", text)


def is_paused() -> bool:
    return get_setting("paused", "0") == "1"


def set_paused(paused: bool) -> None:
    set_setting("paused", "1" if paused else "0")


def cooldown_until() -> Optional[datetime]:
    raw = get_setting("cooldown_until")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def stop_until(until: datetime, kind: str, reason: str) -> datetime:
    set_setting("cooldown_until", until.isoformat(timespec="seconds"))
    set_setting("stop_kind", kind)
    log_event(kind, f"{reason} | until {until:%d %b %H:%M}")
    return until


def start_cooldown(hours: int, reason: str) -> datetime:
    return stop_until(datetime.now() + timedelta(hours=hours), "cooldown", reason)


def stop_kind() -> str:
    return str(get_setting("stop_kind", "cooldown"))


def clear_cooldown() -> None:
    _exec("DELETE FROM settings WHERE key IN ('cooldown_until', 'stop_kind')")


# --- Instagram ka chhupa hua daily cap ---

def record_cap_hit(sent_today: int) -> int:
    """Cap laga. Aaj kitne gaye the wo yaad rakho."""
    known = get_setting("discovered_cap")
    value = min(int(known), sent_today) if known else sent_today
    set_setting("discovered_cap", max(1, value))
    set_setting("cap_hit_date", date.today().isoformat())
    log_event("cap", f"{sent_today} par cap laga")
    return max(1, value)


def discovered_cap() -> Optional[int]:
    raw = get_setting("discovered_cap")
    return int(raw) if raw else None


def days_since_cap_hit() -> Optional[int]:
    raw = get_setting("cap_hit_date")
    if not raw:
        return None
    return (date.today() - date.fromisoformat(raw)).days


def first_run_date() -> date:
    raw = get_setting("first_run_date")
    if not raw:
        today = date.today()
        set_setting("first_run_date", today.isoformat())
        return today
    return date.fromisoformat(raw)


def day_number() -> int:
    """Bot ka konsa din chal raha hai (1 se shuru)."""
    return (date.today() - first_run_date()).days + 1


# --- refs ---

_USERNAME_OK = re.compile(r"^[a-z0-9._]{1,30}$")


def clean_username(raw: str) -> str:
    """Link, @, spaces, query string sab hata ke sirf username."""
    text = (raw or "").strip().lower()
    if "instagram.com" in text:
        text = text.split("instagram.com", 1)[1].lstrip("/")
    text = text.split("?", 1)[0].split("/", 1)[0]
    text = text.lstrip("@").strip()
    return text if _USERNAME_OK.match(text) else ""


def add_ref(username: str) -> bool:
    username = clean_username(username)
    if not username:
        return False
    if _one("SELECT 1 FROM refs WHERE username = ?", (username,)):
        return False
    _exec("INSERT INTO refs(username, added_at) VALUES(?, ?)", (username, _now()))
    return True


def del_ref(username: str) -> bool:
    username = clean_username(username)
    cur = _exec("DELETE FROM refs WHERE username = ?", (username,))
    return cur.rowcount > 0


def list_refs() -> list[sqlite3.Row]:
    return _all("SELECT * FROM refs ORDER BY added_at")


def mark_ref_scraped(username: str, found: int) -> None:
    _exec(
        "UPDATE refs SET last_scrape = ?, found = found + ? WHERE username = ?",
        (_now(), found, username),
    )


# --- targets ---

def target_exists(pk: int) -> bool:
    return _one("SELECT 1 FROM targets WHERE pk = ?", (pk,)) is not None


def add_target(pk: int, username: str, full_name: str, source_ref: str) -> bool:
    if target_exists(pk):
        return False
    try:
        _exec(
            "INSERT INTO targets(pk, username, full_name, source_ref, added_at) "
            "VALUES(?, ?, ?, ?, ?)",
            (pk, username, full_name or "", source_ref, _now()),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def skip_target(pk: int, reason: str) -> None:
    _exec("UPDATE targets SET status = 'skipped', reason = ? WHERE pk = ?", (reason, pk))


def next_targets(limit: int) -> list[sqlite3.Row]:
    """Queue se agle targets, reference pages me round-robin karke."""
    rows = _all(
        "SELECT * FROM targets WHERE status = 'new' ORDER BY added_at LIMIT ?",
        (limit * 10,),
    )
    buckets: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        buckets.setdefault(row["source_ref"] or "", []).append(row)

    out: list[sqlite3.Row] = []
    while len(out) < limit and any(buckets.values()):
        for key in list(buckets):
            if not buckets[key]:
                del buckets[key]
                continue
            out.append(buckets[key].pop(0))
            if len(out) >= limit:
                break
    return out


def queue_size() -> int:
    row = _one("SELECT COUNT(*) AS c FROM targets WHERE status = 'new'")
    return row["c"] if row else 0


def record_send(pk: int, username: str, message: str, ok: bool, error: str = "") -> None:
    _exec(
        "INSERT INTO sent_log(pk, username, message, ok, error, sent_at) "
        "VALUES(?, ?, ?, ?, ?, ?)",
        (pk, username, message, 1 if ok else 0, error, _now()),
    )
    _exec(
        "UPDATE targets SET status = ?, reason = ? WHERE pk = ?",
        ("sent" if ok else "failed", error, pk),
    )


def sent_count(day: Optional[date] = None) -> int:
    day = day or date.today()
    row = _one(
        "SELECT COUNT(*) AS c FROM sent_log WHERE ok = 1 AND sent_at LIKE ?",
        (f"{day.isoformat()}%",),
    )
    return row["c"] if row else 0


def failed_count(day: Optional[date] = None) -> int:
    day = day or date.today()
    row = _one(
        "SELECT COUNT(*) AS c FROM sent_log WHERE ok = 0 AND sent_at LIKE ?",
        (f"{day.isoformat()}%",),
    )
    return row["c"] if row else 0


def sent_last_hour() -> int:
    return sent_since(timedelta(hours=1))


def sent_last_24h() -> int:
    """Instagram apna cap rolling 24 ghante par ginta hai, calendar din par nahi."""
    return sent_since(timedelta(hours=24))


def sent_since(delta: timedelta) -> int:
    since = (datetime.now() - delta).isoformat(timespec="seconds")
    row = _one("SELECT COUNT(*) AS c FROM sent_log WHERE ok = 1 AND sent_at >= ?", (since,))
    return row["c"] if row else 0


# --- time stamps (refill, followback wagairah) ---

def get_time(key: str) -> Optional[datetime]:
    raw = get_setting(key)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def set_time(key: str, when: Optional[datetime] = None) -> None:
    set_setting(key, (when or datetime.now()).isoformat(timespec="seconds"))


def minutes_since(key: str) -> Optional[float]:
    when = get_time(key)
    if when is None:
        return None
    return (datetime.now() - when).total_seconds() / 60


def report_rows(days: int = 7) -> list[sqlite3.Row]:
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    return _all(
        "SELECT substr(sent_at, 1, 10) AS day, "
        "SUM(ok) AS ok, SUM(1 - ok) AS fail "
        "FROM sent_log WHERE sent_at >= ? GROUP BY day ORDER BY day DESC",
        (since,),
    )


# --- followers / follow-back ---

def known_follower_pks() -> set[int]:
    return {r["pk"] for r in _all("SELECT pk FROM followers_snapshot")}


def add_follower(pk: int, username: str) -> None:
    _exec(
        "INSERT OR IGNORE INTO followers_snapshot(pk, username, seen_at) VALUES(?, ?, ?)",
        (pk, username, _now()),
    )


def mark_followed_back(pk: int) -> None:
    _exec("UPDATE followers_snapshot SET followed_back = 1 WHERE pk = ?", (pk,))


def pending_followbacks(limit: int) -> list[sqlite3.Row]:
    return _all(
        "SELECT * FROM followers_snapshot WHERE followed_back = 0 ORDER BY seen_at LIMIT ?",
        (limit,),
    )


def followbacks_today() -> int:
    row = _one(
        "SELECT COUNT(*) AS c FROM events WHERE kind = 'followback' AND at LIKE ?",
        (f"{date.today().isoformat()}%",),
    )
    return row["c"] if row else 0


# --- events ---

def log_event(kind: str, detail: str = "") -> None:
    _exec("INSERT INTO events(kind, detail, at) VALUES(?, ?, ?)", (kind, detail, _now()))


def recent_events(limit: int = 10) -> list[sqlite3.Row]:
    return _all("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
