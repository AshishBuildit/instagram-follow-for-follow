"""Telegram interface. Yahi aapka control panel hai."""

import asyncio
import logging
from datetime import datetime

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import config, copy, db, scheduler, sender

log = logging.getLogger(__name__)

KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(copy.BTN_STATUS), KeyboardButton(copy.BTN_QUEUE_LABEL)],
        [KeyboardButton(copy.BTN_REFS), KeyboardButton(copy.BTN_MSG)],
        [KeyboardButton(copy.BTN_TOGGLE), KeyboardButton(copy.BTN_REPORT)],
    ],
    resize_keyboard=True,
)


class Notifier:
    """Worker thread se Telegram par message bhejne ka pul."""

    def __init__(self) -> None:
        self.app: Application | None = None
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind(self, app: Application, loop: asyncio.AbstractEventLoop) -> None:
        self.app = app
        self.loop = loop

    def send(self, text: str) -> None:
        """Thread-safe. Telegram na pahunche to bhi bot nahi rukta, log me chala jata hai."""
        if not text:
            return
        if self.app is None or self.loop is None or self.loop.is_closed():
            log.info("(notify) %s", text)
            return
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.app.bot.send_message(config.TELEGRAM_OWNER_ID, text),
                self.loop,
            )
        except RuntimeError:  # loop band ho raha hai
            log.info("(notify) %s", text)
            return

        def _check(fut) -> None:
            # Bina iske Telegram fail hone par message chupchap gayab ho jata hai
            try:
                fut.result()
            except Exception as exc:  # noqa: BLE001
                log.warning("Telegram par ye message nahi gaya (%s): %s", exc, text[:80])

        future.add_done_callback(_check)

    def shutdown(self) -> None:
        """Worker thread se poora process band karna."""
        if self.app is None or self.loop is None or self.loop.is_closed():
            return
        try:
            self.loop.call_soon_threadsafe(self.app.stop_running)
        except RuntimeError:
            pass


notifier = Notifier()


def _owner_only(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id == config.TELEGRAM_OWNER_ID)


async def _guard(update: Update) -> bool:
    if _owner_only(update):
        return update.effective_message is not None
    if update.effective_message:
        await update.effective_message.reply_text(copy.NOT_OWNER)
    return False


async def _reply(update: Update, text: str) -> None:
    # effective_message, kyunki edit kiye hue message par update.message None hota hai
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(text, reply_markup=KEYBOARD)


# --- commands ---

async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    text = copy.WELCOME
    if config.DRY_RUN:
        text += "\n\n" + copy.DRY_RUN_ON
    await _reply(update, text)


async def cmd_help(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await _reply(update, copy.HELP)


def status_text() -> str:
    sent = db.sent_count()
    allowed, why = scheduler.can_send_now()
    queue = db.queue_size()

    if why == "cooldown":
        until = db.cooldown_until()
        when = until.strftime("%d %b %H:%M") if until else ""
        if db.stop_kind() == "daily_cap":
            return copy.STATUS_CAP.format(until=when)
        return copy.STATUS_COOLDOWN.format(until=when)
    if why == "paused":
        return copy.STATUS_PAUSED.format(sent=sent)
    if why == "rest":
        return copy.STATUS_REST
    if why == "sleep":
        return copy.STATUS_SLEEP.format(
            start=config.ACTIVE_START_HOUR, end=config.ACTIVE_END_HOUR
        )
    if why == "cap24":
        return copy.STATUS_CAP24
    if why in ("done", "hourly") and scheduler.remaining_today() <= 0:
        return copy.STATUS_DONE.format(sent=sent, queue=queue)
    if why == "empty":
        return copy.QUEUE_EMPTY

    left = scheduler.remaining_today()
    mins = max(1, config.MIN_GAP_SECONDS // 60)
    out = copy.STATUS_RUNNING.format(sent=sent, left=left, mins=mins, queue=queue)
    if scheduler.is_warmup():
        out += "\n\n" + copy.WARMUP_NOTE.format(day=db.day_number(), quota=scheduler.daily_quota())
    found = db.discovered_cap()
    if found:
        out += "\n\n" + copy.CAP_NOTE.format(cap=found, target=scheduler.daily_quota())
    if config.DRY_RUN:
        out += "\n\n" + copy.DRY_RUN_ON
    if 0 < queue < config.QUEUE_REFILL_THRESHOLD:
        out += "\n\n" + copy.QUEUE_LOW.format(n=queue)
    return out


async def cmd_status(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await _reply(update, status_text())


async def cmd_refs(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    refs = db.list_refs()
    if not refs:
        await _reply(update, copy.REF_EMPTY)
        return
    lines = [
        f"@{r['username']}  ({r['found']} mile)"
        + ("" if r["last_scrape"] else "  [abhi scan nahi hua]")
        for r in refs
    ]
    await _reply(update, "Reference pages:\n" + "\n".join(lines))


async def cmd_addref(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not ctx.args:
        await _reply(update, copy.REF_USAGE)
        return
    lines = []
    for raw in ctx.args:
        u = db.clean_username(raw)
        if not u:
            lines.append(copy.REF_BAD.format(u=raw[:40]))
        elif db.add_ref(u):
            lines.append(copy.REF_ADDED.format(u=u))
        else:
            lines.append(copy.REF_EXISTS.format(u=u))
    await _reply(update, "\n".join(lines))


async def cmd_delref(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not ctx.args:
        await _reply(update, copy.REF_USAGE.replace("addref", "delref"))
        return
    u = db.clean_username(ctx.args[0]) or ctx.args[0][:40]
    ok = db.del_ref(u)
    await _reply(update, (copy.REF_DELETED if ok else copy.REF_NOT_FOUND).format(u=u))


async def cmd_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    text = " ".join(ctx.args).strip()
    if not text:
        current = " | ".join(db.get_template())
        await _reply(update, f"Abhi ka message:\n{current}\n\n{copy.MSG_USAGE}")
        return
    db.set_template(text)
    out = copy.MSG_SET.format(t=text)
    if "{name}" not in text:
        out += "\n\n" + copy.MSG_NO_NAME
    await _reply(update, out)


async def cmd_preview(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    rows = db.next_targets(3)
    templates = db.get_template()
    if rows:
        samples = [
            f"@{r['username']}  ->  {sender.render(r['full_name'] or '', r['username'], templates)}"
            for r in rows
        ]
    else:
        samples = [
            f"@{u}  ->  {sender.render(n, u, templates)}"
            for u, n in [("priya_23", "Priya Sharma"), ("rahul.k", ""), ("aditi", "Aditi 🌸")]
        ]
    await _reply(update, copy.PREVIEW.format(samples="\n".join(samples)))


async def cmd_queue(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    n = db.queue_size()
    if n == 0:
        await _reply(update, copy.QUEUE_EMPTY)
        return
    per_day = max(1, scheduler.daily_quota() or config.DAILY_DM_CEILING)
    await _reply(update, copy.QUEUE_INFO.format(n=n, days=max(1, n // per_day)))


async def cmd_pause(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if db.is_paused():
        await _reply(update, copy.ALREADY_PAUSED)
        return
    db.set_paused(True)
    await _reply(update, copy.PAUSED)


async def cmd_resume(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    was_stopped = db.is_paused() or scheduler.in_cooldown()
    db.set_paused(False)
    db.clear_cooldown()
    await _reply(update, copy.RESUMED if was_stopped else copy.ALREADY_RUNNING)


async def cmd_stop(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Poora process band. Phone par battery bachane ke liye."""
    if not await _guard(update):
        return
    await _reply(update, copy.STOPPING)
    notifier.shutdown()


async def cmd_report(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    rows = db.report_rows(7)
    if not rows:
        await _reply(update, copy.REPORT_EMPTY)
        return
    lines = [
        copy.REPORT_ROW.format(
            day=datetime.fromisoformat(r["day"]).strftime("%d %b"),
            ok=r["ok"] or 0,
            fail=r["fail"] or 0,
        )
        for r in rows
    ]
    await _reply(update, copy.REPORT_HEAD + "\n" + "\n".join(lines))


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    text = (update.message.text or "").strip()
    if text == copy.BTN_STATUS:
        await cmd_status(update, ctx)
    elif text == copy.BTN_REFS:
        await cmd_refs(update, ctx)
    elif text == copy.BTN_QUEUE_LABEL:
        await cmd_queue(update, ctx)
    elif text == copy.BTN_MSG:
        current = " | ".join(db.get_template())
        await _reply(update, f"Abhi ka message:\n{current}\n\n{copy.MSG_USAGE}")
    elif text == copy.BTN_TOGGLE:
        if db.is_paused():
            await cmd_resume(update, ctx)
        else:
            await cmd_pause(update, ctx)
    elif text == copy.BTN_REPORT:
        await cmd_report(update, ctx)
    else:
        await _reply(update, copy.HELP)


def build_app(on_ready) -> Application:
    async def _post_init(application: Application) -> None:
        notifier.bind(application, asyncio.get_running_loop())
        on_ready()

    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .post_init(_post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("refs", cmd_refs))
    app.add_handler(CommandHandler("addref", cmd_addref))
    app.add_handler(CommandHandler("delref", cmd_delref))
    app.add_handler(CommandHandler("msg", cmd_msg))
    app.add_handler(CommandHandler("preview", cmd_preview))
    app.add_handler(CommandHandler("queue", cmd_queue))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_button))
    return app
