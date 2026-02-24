import os
import json
import asyncio
import threading
from datetime import datetime, timedelta
from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
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
    web.run(host="0.0.0.0", port=port)

def keep_alive():
    threading.Thread(target=run_web, daemon=True).start()

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
    # Replace with your API integration
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

# ================= BUTTON HANDLER =================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    db = load_db()
    user = db["users"].get(user_id)
    
    if not user or not subscription_active(user):
        await query.edit_message_text("❌ Subscription expired.\nContact admin for renewal.")
        return
    
    button_map = {
        "watch": "🔍 *WATCH*\n━━━━━━━━━━━━━━━━━━\nUse: `/watch username`",
        "ban": "🚫 *BAN*\n━━━━━━━━━━━━━━━━━━\nUse: `/ban username`",
        "status": "📊 *STATUS*\n━━━━━━━━━━━━━━━━━━\nUse: `/status username`",
        "approve": "👑 *APPROVE*\n━━━━━━━━━━━━━━━━━━\nUse: `/approve user_id days`\n*(Admin only)*",
        "addadmin": "➕ *ADD ADMIN*\n━━━━━━━━━━━━━━━━━━\nUse: `/addadmin user_id`\n*(Owner only)*",
        "broadcast": "📢 *BROADCAST*\n━━━━━━━━━━━━━━━━━━\nUse: `/broadcast message`\n*(Admin only)*",
    }
    
    if query.data in button_map:
        await query.edit_message_text(
            text=button_map[query.data],
            parse_mode='Markdown',
            reply_markup=main_menu()
        )

# ================= START =================

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

    await update.message.reply_text(
        "🔥 PROFESSIONAL MONITOR BOT\n━━━━━━━━━━━━━━━━━━\n"
        "Welcome! Use the buttons below or commands:\n"
        "/watch - Add to watchlist\n"
        "/ban - Manual ban\n"
        "/status - Check status",
        reply_markup=main_menu()
    )

# ================= WATCH =================

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /watch username")
        return

    username = context.args[0].lower()
    user_id = str(update.effective_user.id)
    db = load_db()
    
    if user_id not in db["users"]:
        await update.message.reply_text("❌ Please /start first")
        return
        
    user = db["users"][user_id]

    if not subscription_active(user):
        await update.message.reply_text("❌ Subscription expired.")
        return

    if len(user["watch"]) >= MAX_USERNAMES:
        await update.message.reply_text("⚠ Max username limit reached.")
        return

    if username not in user["watch"]:
        user["watch"].append(username)
        save_db(db)

    await update.message.reply_text(
        f"✅ USER ADDED\n━━━━━━━━━━━━━━━━━━\nUsername: {username}\nStatus: Monitoring Started"
    )

# ================= MANUAL BAN =================

async def manual_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ban username")
        return

    username = context.args[0].lower()
    user_id = str(update.effective_user.id)
    db = load_db()
    
    if user_id not in db["users"]:
        await update.message.reply_text("❌ Please /start first")
        return
        
    user = db["users"][user_id]

    if username not in user["ban"]:
        user["ban"].append(username)
        save_db(db)

    await update.message.reply_text(
        f"🚫 MANUAL BAN ADDED\n━━━━━━━━━━━━━━━━━━\nUsername: {username}"
    )

# ================= STATUS =================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /status username")
        return

    username = context.args[0].lower()
    result = await check_username(username)

    emoji = "🟢" if result == "ACTIVE" else "🔴" if result == "BANNED" else "⚪"

    await update.message.reply_text(
        f"{emoji} LIVE STATUS REPORT\n━━━━━━━━━━━━━━━━━━\nUsername: {username}\nStatus: {result}"
    )

# ================= APPROVE =================

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    if not is_admin(update.effective_user.id, db):
        await update.message.reply_text("❌ Admin only command")
        return
        
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /approve user_id days")
        return

    target = context.args[0]
    try:
        days = int(context.args[1])
    except:
        await update.message.reply_text("❌ Days must be a number")
        return

    if target in db["users"]:
        expiry = datetime.now() + timedelta(days=days)
        db["users"][target]["expiry"] = expiry.strftime("%Y-%m-%d")
        save_db(db)

        await update.message.reply_text(
            f"👑 APPROVED\n━━━━━━━━━━━━━━━━━━\nUser: {target}\nDays: {days}"
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=int(target),
                text=f"✅ Your subscription has been renewed for {days} days!"
            )
        except:
            pass
    else:
        await update.message.reply_text("❌ User not found")

# ================= ADD ADMIN =================

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Owner only command")
        return
        
    if not context.args:
        await update.message.reply_text("Usage: /addadmin user_id")
        return

    try:
        target = int(context.args[0])
    except:
        await update.message.reply_text("❌ Invalid user_id")
        return

    if target not in db["admins"]:
        db["admins"].append(target)
        save_db(db)
        await update.message.reply_text("👑 NEW ADMIN ADDED")
    else:
        await update.message.reply_text("✅ Already an admin")

# ================= BROADCAST =================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    if not is_admin(update.effective_user.id, db):
        await update.message.reply_text("❌ Admin only command")
        return
        
    if not context.args:
        await update.message.reply_text("Usage: /broadcast message")
        return

    message = " ".join(context.args)
    sent = 0

    for user_id in db["users"]:
        try:
            await context.bot.send_message(
                chat_id=user_id, 
                text=f"📢 *BROADCAST*\n\n{message}",
                parse_mode='Markdown'
            )
            sent += 1
        except:
            pass

    await update.message.reply_text(f"📢 Broadcast Sent to {sent} users")

# ================= MONITOR LOOP =================

async def monitor(app):
    while True:
        try:
            db = load_db()

            for user_id, user in db["users"].items():

                for username in list(user.get("watch", [])):
                    status = await check_username(username)

                    if status == "BANNED":
                        user["confirm"][username] = user["confirm"].get(username, 0) + 1
                    else:
                        user["confirm"][username] = 0

                    if user["confirm"].get(username, 0) >= CONFIRM_LIMIT:
                        try:
                            await app.bot.send_message(
                                chat_id=int(user_id),
                                text=f"🚫 *BANNED DETECTED*\n━━━━━━━━━━━━━━━━━━\nUsername: {username}",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
                        user["watch"].remove(username)
                        user["ban"].append(username)
                        user["confirm"][username] = 0

                for username in list(user.get("ban", [])):
                    status = await check_username(username)

                    if status == "ACTIVE":
                        user["confirm"][username] = user["confirm"].get(username, 0) + 1
                    else:
                        user["confirm"][username] = 0

                    if user["confirm"].get(username, 0) >= CONFIRM_LIMIT:
                        try:
                            await app.bot.send_message(
                                chat_id=int(user_id),
                                text=f"✅ *UNBANNED DETECTED*\n━━━━━━━━━━━━━━━━━━\nUsername: {username}",
                                parse_mode='Markdown'
                            )
                        except:
                            pass
                        user["ban"].remove(username)
                        user["watch"].append(username)
                        user["confirm"][username] = 0

            save_db(db)
        except Exception as e:
            print(f"Monitor error: {e}")
            
        await asyncio.sleep(CHECK_INTERVAL)

# ================= MAIN (FIXED) =================

async def run_bot():
    """Bot ko run karne ka sahi tarika"""
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("watch", watch))
    application.add_handler(CommandHandler("ban", manual_ban))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.create_task(monitor(application))

    keep_alive()

    print("🚀 Professional Monitor Bot Running")
    
    # 👇 YEH FIX HAI - Sahi tarike se run_polling()
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Idle while bot runs
    while True:
        await asyncio.sleep(3600)  # Sleep for an hour

if __name__ == "__main__":
    asyncio.run(run_bot())
