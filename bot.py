import os
import json
import logging
import base64
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from pymongo import MongoClient

# ========== CONFIGURATION ==========
BOT_TOKEN = "7718352742:AAG1H680asb9vpfsazZZQdp59vNkx2PjGbw"
ADMIN_ID = 1944182800

# MongoDB Config
MONGO_URI = "mongodb+srv://rishi:ipxkingyt@rishiv.ncljp.mongodb.net/?retryWrites=true&w=majority&appName=rishiv"
DB_NAME = "nexo_bot"
FILES_COLLECTION = "stored_files"

# GitHub Config
GITHUB_TOKEN = "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"
REPO_OWNER = "fghhvdty"
REPO_NAME = "Daku"
RAW_URL = f"https://raw.githubusercontent.com/fghhvdty/Daku/refs/heads/main/File.json"
GITHUB_API_URL = f"https://api.github.com/repos/fghhvdty/Daku/contents/File.json?ref=main"

# States
WAITING_FOR_FILE = 1
WAITING_FOR_IMAGE_URL = 2
WAITING_FOR_TITLE = 3

temp_upload = {}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== MONGODB ==========
def connect_mongodb():
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("✅ MongoDB Connected!")
        return client
    except Exception as e:
        print(f"❌ MongoDB Error: {e}")
        return None

client = connect_mongodb()
if client:
    db = client[DB_NAME]
    files_collection = db[FILES_COLLECTION]
    MONGODB_AVAILABLE = True
else:
    MONGODB_AVAILABLE = False
    files_db = {}

def save_file(file_key, file_data):
    if MONGODB_AVAILABLE:
        try:
            files_collection.update_one(
                {"file_key": file_key},
                {"$set": {**file_data, "created_at": datetime.now()}},
                upsert=True
            )
            return True
        except:
            return False
    else:
        files_db[file_key] = file_data
        return True

def get_file(file_key):
    if MONGODB_AVAILABLE:
        try:
            doc = files_collection.find_one({"file_key": file_key})
            return {"title": doc["title"], "file_id": doc["file_id"], "file_name": doc["file_name"]} if doc else None
        except:
            return None
    else:
        return files_db.get(file_key)

def get_all_files():
    if MONGODB_AVAILABLE:
        files = {}
        for doc in files_collection.find():
            files[doc["file_key"]] = {"title": doc["title"], "file_id": doc["file_id"], "file_name": doc["file_name"]}
        return files
    else:
        return files_db

# ========== GITHUB ==========
def update_github(products_list):
    content = json.dumps({"products": products_list}, indent=2)
    encoded = base64.b64encode(content.encode()).decode()
    
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    try:
        resp = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
        
        data = {"message": f"Update - {datetime.now()}", "content": encoded, "sha": sha}
        put_resp = requests.put(GITHUB_API_URL, headers=headers, json=data, timeout=10)
        return put_resp.status_code == 200
    except Exception as e:
        logger.error(f"GitHub error: {e}")
        return False

def get_products():
    try:
        resp = requests.get(RAW_URL, timeout=10)
        return resp.json().get("products", [])
    except:
        return []

# ========== BOT COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if args and len(args) > 0:
        file_key = args[0]
        file_data = get_file(file_key)
        
        if file_data:
            try:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file_data['file_id'],
                    caption=f"📁 {file_data['title']}\n\nSource: NEXO MODS"
                )
                return
            except Exception as e:
                await update.message.reply_text("❌ Error sending file!")
                return
    
    if user_id == ADMIN_ID:
        total_files = len(get_all_files())
        products = get_products()
        await update.message.reply_text(
            f"🎯 Admin Panel\n\n"
            f"/upload - Add product\n"
            f"/list - List products\n"
            f"/delete <pos> - Delete\n"
            f"/stats - Stats\n"
            f"/files - Show files\n\n"
            f"Files: {total_files}\n"
            f"Products: {len(products)}\n"
            f"Storage: {'MongoDB' if MONGODB_AVAILABLE else 'Local'}"
        )
    else:
        await update.message.reply_text("🤖 NEXO MODS File Bot\n\nUse app to download files!")

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    temp_upload[update.effective_user.id] = {}
    await update.message.reply_text("📤 Step 1/3: Send FILE\nSend /cancel")
    return WAITING_FOR_FILE

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    msg = update.message
    
    if msg.document:
        temp_upload[uid]['file_id'] = msg.document.file_id
        temp_upload[uid]['file_name'] = msg.document.file_name
    else:
        await update.message.reply_text("❌ Send document file!")
        return WAITING_FOR_FILE
    
    await update.message.reply_text("✅ Step 2/3: Send IMAGE URL\nSend /cancel")
    return WAITING_FOR_IMAGE_URL

async def receive_image_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    url = update.message.text.strip()
    
    if not url.startswith("http"):
        await update.message.reply_text("❌ Valid URL required!")
        return WAITING_FOR_IMAGE_URL
    
    temp_upload[uid]['image_url'] = url
    await update.message.reply_text("✅ Step 3/3: Send TITLE\nSend /cancel")
    return WAITING_FOR_TITLE

async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    title = update.message.text.strip()
    
    import time
    file_key = f"file_{int(time.time())}_{uid}"
    
    file_data = {
        "title": title,
        "file_id": temp_upload[uid]['file_id'],
        "file_name": temp_upload[uid]['file_name']
    }
    save_file(file_key, file_data)
    
    products = get_products()
    bot_info = await context.bot.get_me()
    
    new_product = {
        "title": title,
        "image_url": temp_upload[uid]['image_url'],
        "download_link": f"https://t.me/{bot_info.username}?start={file_key}"
    }
    
    products.insert(0, new_product)
    success = update_github(products)
    
    temp_upload.pop(uid, None)
    
    if success:
        await update.message.reply_text(f"✅ Added!\n\nTitle: {title}\nID: {file_key}\nTotal: {len(products)}")
    else:
        await update.message.reply_text(f"⚠️ Saved but GitHub failed!\nTitle: {title}")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp_upload.pop(update.effective_user.id, None)
    await update.message.reply_text("❌ Cancelled")
    return ConversationHandler.END

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    products = get_products()
    if not products:
        await update.message.reply_text("No products")
        return
    
    msg = "📁 Products:\n\n"
    for i, p in enumerate(products):
        msg += f"{i+1}. {p.get('title', 'No title')[:40]}\n"
    await update.message.reply_text(msg)

async def show_stored(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    files = get_all_files()
    if not files:
        await update.message.reply_text("No files")
        return
    
    msg = f"📦 Files ({len(files)}):\n\n"
    for k, v in list(files.items())[:20]:
        msg += f"• {k} - {v['title'][:30]}\n"
    await update.message.reply_text(msg)

async def delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /delete 1")
        return
    
    try:
        pos = int(args[0]) - 1
        products = get_products()
        
        if 0 <= pos < len(products):
            deleted = products.pop(pos)
            if update_github(products):
                await update.message.reply_text(f"✅ Deleted: {deleted.get('title')}")
            else:
                await update.message.reply_text("❌ Delete failed")
        else:
            await update.message.reply_text("❌ Position not found")
    except:
        await update.message.reply_text("❌ Invalid number")

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    products = get_products()
    files = get_all_files()
    await update.message.reply_text(
        f"📊 Stats\n\n"
        f"Products: {len(products)}\n"
        f"Files: {len(files)}\n"
        f"Storage: {'MongoDB' if MONGODB_AVAILABLE else 'Local'}"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# ========== MAIN ==========
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_start)],
        states={
            WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, receive_file)],
            WAITING_FOR_IMAGE_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_image_url)],
            WAITING_FOR_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_products))
    app.add_handler(CommandHandler("files", show_stored))
    app.add_handler(CommandHandler("delete", delete_product))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_error_handler(error_handler)
    
    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()