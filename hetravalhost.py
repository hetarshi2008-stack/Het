"""
HET HOSTING BOT
Upload .py files → bot runs them 24/7, auto-restarts on crash.
Made by Het 🎀
"""

import asyncio
import os
import sys
import time
import subprocess
import signal
from collections import deque
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.error import RetryAfter

# ─────────────────────────────────────────────
# CONFIG  ← put your values here
# ─────────────────────────────────────────────
BOT_TOKEN   = "8949072053:AAGzWqFE2w9H1J-7W_rX-buPBrqwxVV6oHY"
OWNER_ID    = 6266857011          # your Telegram user ID
UPLOAD_DIR  = "hosted_bots"      # folder where uploaded scripts are saved
MAX_LOGS    = 200                 # lines kept per bot in memory
# ─────────────────────────────────────────────

os.makedirs(UPLOAD_DIR, exist_ok=True)
START_TIME = time.time()

# name → {"proc": Popen, "logs": deque, "started": timestamp, "restarts": int, "running": bool}
hosted: dict = {}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def uptime_str() -> str:
    secs = int(time.time() - START_TIME)
    h, r = divmod(secs, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"


def fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d/%m %H:%M:%S")


async def read_output(name: str, stream):
    """Continuously read stdout/stderr of a subprocess and store last MAX_LOGS lines."""
    logs: deque = hosted[name]["logs"]
    try:
        async for line in stream:
            logs.append(line.decode(errors="replace").rstrip())
    except Exception:
        pass


async def run_bot(name: str, path: str):
    """Start a script and restart it if it dies, forever."""
    hosted[name]["running"] = True
    while hosted[name].get("running"):
        proc = await asyncio.create_subprocess_exec(
            sys.executable, path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=UPLOAD_DIR,
        )
        hosted[name]["proc"]    = proc
        hosted[name]["pid"]     = proc.pid
        hosted[name]["started"] = time.time()

        await read_output(name, proc.stdout)
        await proc.wait()

        if not hosted[name].get("running"):
            break

        hosted[name]["restarts"] = hosted[name].get("restarts", 0) + 1
        hosted[name]["logs"].append(
            f"[HOST] ⚠️ Crashed — restarting in 3s "
            f"(restart #{hosted[name]['restarts']})"
        )
        await asyncio.sleep(3)


# ─────────────────────────────────────────────
# ADMIN CHECK
# ─────────────────────────────────────────────
def is_owner(update: Update) -> bool:
    return update.effective_user.id == OWNER_ID


def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_owner(update):
            await update.message.reply_text("❌ Owner only.")
            return
        return await func(update, context)
    return wrapper


# ─────────────────────────────────────────────
# COMMANDS
# ─────────────────────────────────────────────
@owner_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎀 *HET HOSTING BOT* 🎀\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ _Made by Het_\n\n"
        "Send a `.py` file to upload and run it 24/7.\n\n"
        "📋 *Commands:*\n"
        "▸ /list — all uploaded bots\n"
        "▸ /status — running bots\n"
        "▸ /logs `<name>` — last 20 log lines\n"
        "▸ /stop `<name>` — stop a bot\n"
        "▸ /restart `<name>` — restart a bot\n"
        "▸ /delete `<name>` — stop + delete a bot\n"
        "▸ /ping — latency check\n"
        "▸ /uptime — host uptime\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🎀 *HET HOSTING BOT* — Always Online",
        parse_mode="Markdown"
    )


@owner_only
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    ms = int((time.time() - t) * 1000)
    await msg.edit_text(
        f"🎀 *HET HOSTING BOT*\n"
        f"🏓 Pong! ⚡ `{ms}ms`\n"
        f"🕐 Uptime: `{uptime_str()}`\n"
        f"_Made by Het_",
        parse_mode="Markdown"
    )


@owner_only
async def cmd_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🕐 Host bot uptime: `{uptime_str()}`", parse_mode="Markdown")


@owner_only
async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".py")]
    if not files:
        return await update.message.reply_text("📂 No bots uploaded yet.\nSend a `.py` file to get started.")
    lines = []
    for f in sorted(files):
        name = f[:-3]
        info = hosted.get(name)
        if info and info.get("running"):
            restarts = info.get("restarts", 0)
            lines.append(f"🟢 `{name}` — running | restarts: {restarts}")
        else:
            lines.append(f"🔴 `{name}` — stopped")
    await update.message.reply_text("📋 *Uploaded Bots:*\n\n" + "\n".join(lines), parse_mode="Markdown")


@owner_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    running = {k: v for k, v in hosted.items() if v.get("running")}
    if not running:
        return await update.message.reply_text("📊 No bots currently running.")
    lines = []
    for name, info in running.items():
        age = int(time.time() - info.get("started", time.time()))
        h, r = divmod(age, 3600)
        m, s = divmod(r, 60)
        lines.append(
            f"🟢 *{name}*\n"
            f"   PID: `{info.get('pid','?')}` | Up: `{h}h{m}m{s}s` | Restarts: `{info.get('restarts',0)}`"
        )
    await update.message.reply_text("📊 *Running Bots:*\n\n" + "\n\n".join(lines), parse_mode="Markdown")


@owner_only
async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /logs `<name>`", parse_mode="Markdown")
    name = context.args[0].replace(".py", "")
    if name not in hosted:
        return await update.message.reply_text(f"❌ `{name}` not found or never started.", parse_mode="Markdown")
    logs = list(hosted[name]["logs"])[-20:]
    text = "\n".join(logs) if logs else "(no output yet)"
    await update.message.reply_text(
        f"📄 *Logs for* `{name}`:\n```\n{text[:3500]}\n```",
        parse_mode="Markdown"
    )


@owner_only
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /stop `<name>`", parse_mode="Markdown")
    name = context.args[0].replace(".py", "")
    if name not in hosted or not hosted[name].get("running"):
        return await update.message.reply_text(f"❌ `{name}` is not running.", parse_mode="Markdown")
    hosted[name]["running"] = False
    proc = hosted[name].get("proc")
    if proc:
        try:
            proc.terminate()
            await asyncio.sleep(1)
            if proc.returncode is None:
                proc.kill()
        except Exception:
            pass
    await update.message.reply_text(f"⏹ `{name}` stopped.", parse_mode="Markdown")


@owner_only
async def cmd_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /restart `<name>`", parse_mode="Markdown")
    name = context.args[0].replace(".py", "")
    path = os.path.join(UPLOAD_DIR, f"{name}.py")
    if not os.path.exists(path):
        return await update.message.reply_text(f"❌ `{name}.py` not found.", parse_mode="Markdown")

    # stop if running
    if name in hosted and hosted[name].get("running"):
        hosted[name]["running"] = False
        proc = hosted[name].get("proc")
        if proc:
            try:
                proc.terminate()
                await asyncio.sleep(1)
                if proc.returncode is None:
                    proc.kill()
            except Exception:
                pass
        await asyncio.sleep(1)

    # fresh entry
    hosted[name] = {"logs": deque(maxlen=MAX_LOGS), "restarts": 0, "running": False}
    asyncio.create_task(run_bot(name, path))
    await update.message.reply_text(f"🔄 `{name}` restarted.", parse_mode="Markdown")


@owner_only
async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /delete `<name>`", parse_mode="Markdown")
    name = context.args[0].replace(".py", "")
    path = os.path.join(UPLOAD_DIR, f"{name}.py")

    if name in hosted and hosted[name].get("running"):
        hosted[name]["running"] = False
        proc = hosted[name].get("proc")
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
        del hosted[name]

    if os.path.exists(path):
        os.remove(path)
        await update.message.reply_text(f"🗑 `{name}` deleted.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ `{name}.py` not found.", parse_mode="Markdown")


# ─────────────────────────────────────────────
# FILE UPLOAD HANDLER
# ─────────────────────────────────────────────
@owner_only
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".py"):
        return await update.message.reply_text("❌ Please send a `.py` file.")

    name = doc.file_name[:-3]
    path = os.path.join(UPLOAD_DIR, doc.file_name)

    msg = await update.message.reply_text(f"⬇️ Downloading `{doc.file_name}`...", parse_mode="Markdown")

    file = await doc.get_file()
    await file.download_to_drive(path)

    # stop old instance if running
    if name in hosted and hosted[name].get("running"):
        hosted[name]["running"] = False
        proc = hosted[name].get("proc")
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
        await asyncio.sleep(1)

    hosted[name] = {"logs": deque(maxlen=MAX_LOGS), "restarts": 0, "running": False}
    asyncio.create_task(run_bot(name, path))

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📄 Logs",    callback_data=f"logs:{name}"),
            InlineKeyboardButton("⏹ Stop",    callback_data=f"stop:{name}"),
            InlineKeyboardButton("🔄 Restart", callback_data=f"restart:{name}"),
        ]
    ])
    await msg.edit_text(
        f"🎀 *HET HOSTING BOT*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✅ `{name}` is now running 24/7!\n\n"
        f"🔁 Auto-restarts if it crashes.\n"
        f"📄 Use /logs `{name}` to see output.\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ _Made by Het_",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ─────────────────────────────────────────────
# INLINE BUTTON CALLBACKS
# ─────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != OWNER_ID:
        return await query.answer("Owner only.", show_alert=True)

    action, name = query.data.split(":", 1)

    if action == "logs":
        if name not in hosted:
            return await query.answer("Not found.", show_alert=True)
        logs = list(hosted[name]["logs"])[-20:]
        text = "\n".join(logs) if logs else "(no output yet)"
        await query.message.reply_text(
            f"📄 *Logs for* `{name}`:\n```\n{text[:3500]}\n```",
            parse_mode="Markdown"
        )

    elif action == "stop":
        if name in hosted and hosted[name].get("running"):
            hosted[name]["running"] = False
            proc = hosted[name].get("proc")
            if proc:
                try:
                    proc.terminate()
                except Exception:
                    pass
            await query.message.reply_text(f"⏹ `{name}` stopped.", parse_mode="Markdown")
        else:
            await query.answer("Not running.", show_alert=True)

    elif action == "restart":
        path = os.path.join(UPLOAD_DIR, f"{name}.py")
        if not os.path.exists(path):
            return await query.answer("File not found.", show_alert=True)
        if name in hosted and hosted[name].get("running"):
            hosted[name]["running"] = False
            proc = hosted[name].get("proc")
            if proc:
                try:
                    proc.terminate()
                except Exception:
                    pass
            await asyncio.sleep(1)
        hosted[name] = {"logs": deque(maxlen=MAX_LOGS), "restarts": 0, "running": False}
        asyncio.create_task(run_bot(name, path))
        await query.message.reply_text(f"🔄 `{name}` restarted.", parse_mode="Markdown")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("ping",    cmd_ping))
    app.add_handler(CommandHandler("uptime",  cmd_uptime))
    app.add_handler(CommandHandler("list",    cmd_list))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("logs",    cmd_logs))
    app.add_handler(CommandHandler("stop",    cmd_stop))
    app.add_handler(CommandHandler("restart", cmd_restart))
    app.add_handler(CommandHandler("delete",  cmd_delete))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🎀 HET HOSTING BOT is running — Made by Het")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
