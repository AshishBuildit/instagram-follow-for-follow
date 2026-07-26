"""Ek waqt me sirf ek bot chale.

Do bar widget daba diya to do process chalu ho jate hain. Uska matlab:
  - double speed se DM, limit turant paar
  - Telegram dono se getUpdates maangta hai, 409 error aur bot pagal ho jata hai
Isliye lock file.
"""

import logging
import os
from typing import Optional

from . import config

log = logging.getLogger(__name__)

LOCK_PATH = config.DATA_DIR / "ff.lock"


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import subprocess

        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return False
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def running_pid() -> Optional[int]:
    """Agar koi bot pehle se chal raha hai to uska PID."""
    try:
        pid = int(LOCK_PATH.read_text().strip())
    except (OSError, ValueError):
        return None
    if _alive(pid):
        return pid
    LOCK_PATH.unlink(missing_ok=True)  # purana kachra
    return None


def acquire() -> bool:
    """Lock lo. False matlab koi aur pehle se chal raha hai."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if running_pid() is not None:
        return False
    try:
        LOCK_PATH.write_text(str(os.getpid()))
    except OSError as exc:
        log.warning("lock file nahi bani: %s", exc)
    return True


def release() -> None:
    try:
        if LOCK_PATH.exists() and LOCK_PATH.read_text().strip() == str(os.getpid()):
            LOCK_PATH.unlink()
    except OSError:
        pass


class Lock:
    def __enter__(self) -> bool:
        self.ok = acquire()
        return self.ok

    def __exit__(self, *_exc) -> None:
        if getattr(self, "ok", False):
            release()
