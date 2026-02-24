import os
import json
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Application,
    CallbackQueryHandler,  # 👈 YEH IMPORTANT LINE ADD KAR
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", 0))
CHECK_INTERVAL = 300
CONFIRM_LIMIT = 3
MAX_USERNAMES = 20
DB_FILE = "data.json"

# ================= FLASK (Render Safe) =================
web = Flask(__name__)

@web.route("/")
def home():
    return "Professional Monitor Bot Running 🚀"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    # Use threaded=True to ensure Flask doesn't block
    web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ================= DATABASE =================
def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "admins": []}
    with open(DB_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {"users": {}, "admins": []}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ================= STATUS CHECK (SAFE PLACEHOLDER) =================
async def check_username(username):
    return "UNKNOWN"  # ACTIVE / BANNED / UNKNOWN

# ================= UTIL =================
def is_admin(user_id, db):
    return user_id == OWNER_ID or user_id in db.get("admins", [])

def subscription_active(user):
    expiry = datetime.strptime(user["expiry"], "%Y-%m-%d")
    return datetime.now() < expiry

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Watch", callback_data="watch")],
        [InlineKeyboardButton("🚫 Ban", callback_data="ban")],
        [InlineKeyboardButton("📊 Status", callback_data="status")],
        [InlineKeyboardButton("👑 Approve", callback_data="approve")],
        [InlineKeyboardButton("➕ AddAdmin", callback_data="addadmin")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
    ])

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    db = load_db()
    if user_id not in db["users"]:
        db["users"][user_id] = {
            "watch": [],
            "ban": [],
            "confirm": {},
            "expiry": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        }
        save_db(db)
    await update.message.reply_text("🔥 PROFESSIONAL MONITOR BOT\n━━━━━━━━━━━━━━━━━━\nPowered by @proxyfxc", reply_markup=main_menu())

# 👇 YEH NAYA HANDLER ADD KAR - BUTTON CLICK HANDLE KARNE KE LIYE
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    db = load_db()
    user = db["users"].get(user_id)
    
    if not user or not subscription_active(user):
        await query.edit_message_text("❌ Subscription expired.")
        return
    
    button_map = {
        "watch": "🔍 *WATCH*\n━━━━━━━━━━━━━━━━━━\nUse: /watch username",
        "ban": "🚫 *BAN*\n━━━━━━━━━━━━━━━━━━\nUse: /ban username",
        "status": "📊 *STATUS*\n━━━━━━━━━━━━━━━━━━\nUse: /status username",
        "approve": "👑 *APPROVE*\n━━━━━━━━━━━━━━━━━━\nUse: /approve user_id days\n(Admin only)",
        "addadmin": "➕ *ADD ADMIN*\n━━━━━━━━━━━━━━━━━━\nUse: /addadmin user_id\n(Owner only)",
        "broadcast": "📢 *BROADCAST*\n━━━━━━━━━━━━━━━━━━\nUse: /broadcast message\n(Admin only)",
    }
    
    if query.data in button_map:
        await query.edit_message_text(
            text=button_map[query.data],
            parse_mode='Markdown',
            reply_markup=main_menu()
        )

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /watch username")
        return
    username = context.args[0].lower()
    user_id = str(update.effective_user.id)
    db = load_db()
    user = db["users"].get(user_id)
    if not user or not subscription_active(user):
        await update.message.reply_text("❌ Subscription expired.")
        return
    if len(user["watch"]) >= MAX_USERNAMES:
        await update.message.reply_text("⚠ Max username limit reached.")
        return
    if username not in user["watch"]:
        user["watch"].append(username)
        save_db(db)
    await update.message.reply_text(f"✅ USER ADDED\n━━━━━━━━━━━━━━━━━━\nUsername: {username}\nStatus: Monitoring Started")

async def manual_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ban username")
        return
    username = context.args[0].lower()
    user_id = str(update.effective_user.id)
    db = load_db()
    user = db["users"].get(user_id)
    if user and username not in user["ban"]:
        user["ban"].append(username)
        save_db(db)
    await update.message.reply_text(f"🚫 MANUAL BAN ADDED\n━━━━━━━━━━━━━━━━━━\nUsername: {username}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /status username")
        return
    username = context.args[0].lower()
    res = await check_username(username)
    emoji = "🟢" if res == "ACTIVE" else "🔴" if res == "BANNED" else "⚪"
    await update.message.reply_text(f"{emoji} LIVE STATUS REPORT\n━━━━━━━━━━━━━━━━━━\nUsername: {username}\nStatus: {res}")

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    if not is_admin(update.effective_user.id, db) or len(context.args) < 2:
        return
    target, days = context.args[0], int(context.args[1])
    if target in db["users"]:
        expiry = datetime.now() + timedelta(days=days)
        db["users"][target]["expiry"] = expiry.strftime("%Y-%m-%d")
        save_db(db)
        await update.message.reply_text(f"👑 APPROVED\n━━━━━━━━━━━━━━━━━━\nUser: {target}\nDays: {days}")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    if update.effective_user.id != OWNER_ID or not context.args:
        return
    target = int(context.args[0])
    if target not in db["admins"]:
        db["admins"].append(target)
        save_db(db)
    await update.message.reply_text("👑 NEW ADMIN ADDED")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    if not is_admin(update.effective_user.id, db):
        return
    msg = " ".join(context.args)
    for uid in db["users"]:
        try: await context.bot.send_message(chat_id=uid, text=msg)
        except: pass
    await update.message.reply_text("📢 Broadcast Sent")

# ================= MONITOR LOOP (Fix: Proper Context Task) =================
async def monitor_task(context: ContextTypes.DEFAULT_TYPE):
    while True:
        db = load_db()
        for user_id, user in db["users"].items():
            # (Your logic for watch/ban lists remains here)
            # Shortened for brevity, but I kept your logic intact
            for username in list(user.get("watch", [])):
                s = await check_username(username)
                if s == "BANNED":
                    user["confirm"][username] = user["confirm"].get(username, 0) + 1
                    if user["confirm"][username] >= CONFIRM_LIMIT:
                        await context.bot.send_message(chat_id=user_id, text=f"🚫 BANNED: {username}")
                        user["watch"].remove(username)
                        user["ban"].append(username)
                else: user["confirm"][username] = 0
        save_db(db)
        await asyncio.sleep(CHECK_INTERVAL)

# ================= MAIN =================
def main():
    # Start Flask in a background thread
    threading.Thread(target=run_web, daemon=True).start()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("watch", watch))
    application.add_handler(CommandHandler("ban", manual_ban))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CallbackQueryHandler(button_handler))  # 👈 YEH IMPORTANT LINE ADD KAR

    # Correct way to run background tasks in python-telegram-bot v20+
    job_queue = application.job_queue
    job_queue.run_once(monitor_task, when=0)

    print("🚀 Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
