"""Entry point: python -m ff_bot"""

import logging
import logging.handlers
import sys

from . import config, copy, db, lock
from .telegram import build_app, notifier
from .worker import Worker

# Ye libraries bahut bakwas likhti hain. Terminal saaf rakhna hai.
NOISY = (
    "instagrapi",
    "public_request",
    "private_request",
    "urllib3",
    "httpx",
    "httpcore",
    "telegram",
    "telegram.ext",
    "apscheduler",
    "asyncio",
)


def setup_logging() -> None:
    # Windows console default me emoji nahi print kar pata aur crash ho jata hai.
    # Instagram ke naamon me emoji common hai, isliye ye zaruri hai.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Terminal par sirf kaam ki baat
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M"))
    root.addHandler(console)

    # Poori detail file me, taki kuch toote to dekh sakein
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    fileh = logging.handlers.RotatingFileHandler(
        config.LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    fileh.setLevel(logging.DEBUG)
    fileh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    root.addHandler(fileh)

    for name in NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)


def main() -> int:
    setup_logging()
    log = logging.getLogger("ff_bot")

    missing = config.missing_env()
    if missing:
        print(copy.ENV_MISSING.format(keys=", ".join(missing)))
        print("\n.env.example ko copy karke .env banao aur values bharo.")
        return 1

    if config.bad_hours():
        print(copy.CONFIG_BAD_HOURS)
        return 1

    existing = lock.running_pid()
    if existing:
        print(copy.ALREADY_RUNNING_PROC.format(pid=existing))
        return 2

    with lock.Lock():
        db.connect()

        worker = Worker(notifier.send, notifier.shutdown)

        def on_ready() -> None:
            log.info("Telegram jud gaya. Instagram par kaam shuru.")
            worker.start()

        app = build_app(on_ready)

        print(f"Mode: {config.ACCOUNT_MODE}  |  DRY_RUN: {config.DRY_RUN}", end="")
        print(f"  |  Auto-stop: {config.RUN_HOURS}h" if config.RUN_HOURS else "")
        print("Telegram kholo aur /status bhejo. Band karne ke liye Ctrl+C ya /stop.\n")

        try:
            app.run_polling(drop_pending_updates=True, stop_signals=None)
        except KeyboardInterrupt:
            print("\nBand kar raha hoon...")
        finally:
            worker.stop()
            logging.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
