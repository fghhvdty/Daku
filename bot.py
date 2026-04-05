import os
import json
import logging
import base64
import requests
import ssl
import asyncio
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from pymongo import MongoClient
from pymongo.errors import ConfigurationError

# ========== CONFIGURATION ==========
BOT_TOKEN = "7718352742:AAG1H680asb9vpfsazZZQdp59vNkx2PjGbw"
ADMIN_ID = 1944182800

MONGO_URI = "mongodb+srv://rishi:ipxkingyt@rishiv.ncljp.mongodb.net/?retryWrites=true&w=majority&appName=rishiv"
DB_NAME = "nexo_bot"
FILES_COLLECTION = "stored_files"

GITHUB_TOKEN = "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"
GITHUB_API_URL = f"https://api.github.com/repos/fghhvdty/Daku/contents/File.json?ref=main"
RAW_URL = f"https://raw.githubusercontent.com/fghhvdty/Daku/refs/heads/main/File.json"

# Conversation states
WAITING_FOR_FILE = 1
WAITING_FOR_IMAGE_URL = 2
WAITING_FOR_TITLE = 3

temp_upload = {}

# MongoDB Connection
def connect_mongodb():
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("✅ MongoDB Connected Successfully!")
        return client
    except:
        print("❌ MongoDB connection failed - using local storage")
        return None

client = connect_mongodb()
MONGODB_AVAILABLE = client is not None

if MONGODB_AVAILABLE:
    db = client[DB_NAME]
    files_collection = db[FILES_COLLECTION]
else:
    LOCAL_STORAGE_FILE = "local_files.json"
    def load_local_files():
        if os.path.exists(LOCAL_STORAGE_FILE):
            with open(LOCAL_STORAGE_FILE, "r") as f:
                return json.load(f)
        return {}
    
    def save_local_files(files):
        with open(LOCAL_STORAGE_FILE, "w") as f:
            json.dump(files, f, indent=2)
    
    files_db = load_local_files()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def save_file_to_db(file_key, file_data):
    if MONGODB_AVAILABLE:
        try:
            doc = {
                "file_key": file_key,
                "title": file_data["title"],
                "file_id": file_data["file_id"],
                "file_name": file_data["file_name"],
                "created_at": datetime.now()
            }
            files_collection.update_one(
                {"file_key": file_key},
                {"$set": doc},
                upsert=True
            )
            return True
        except:
            return False
    else:
        files_db[file_key] = file_data
        save_local_files(files_db)
        return True

def get_file_from_db(file_key):
    if MONGODB_AVAILABLE:
        try:
            doc = files_collection.find_one({"file_key": file_key})
            if doc:
                return {
                    "title": doc["title"],
                    "file_id": doc["file_id"],
                    "file_name": doc["file_name"]
                }
        except:
            pass
    else:
        return files_db.get(file_key)
    return None

def get_all_files():
    if MONGODB_AVAILABLE:
        try:
            files = {}
            for doc in files_collection.find():
                files[doc["file_key"]] = {
                    "title": doc["title"],
                    "file_id": doc["file_id"],
                    "file_name": doc["file_name"]
                }
            return files
        except:
            return {}
    else:
        return files_db

def update_github_file(products_list):
    content = json.dumps({"products": products_list}, indent=2)
    encoded_content = base64.b64encode(content.encode()).decode()
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        sha = None
        if response.status_code == 200:
            data = response.json()
            sha = data.get("sha")
        
        data = {
            "message": f"Update products - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": encoded_content,
            "sha": sha
        }
        
        put_response = requests.put(GITHUB_API_URL, headers=headers, json=data, timeout=10)
        return put_response.status_code == 200
    except:
        return False

def get_current_products():
    try:
        response = requests.get(RAW_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("products", [])
    except:
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    args = context.args
    if args:
        file_key = args[0]
        file_data = get_file_from_db(file_key)
        
        if file_data:
            try:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file_data['file_id'],
                    caption=f"📁 {file_data['title']}\n\nSource: NEXO MODS",
                    filename=file_data['file_name']
                )
                return
            except Exception as e:
                await update.message.reply_text("❌ Error sending file!")
                return
    
    if user_id == ADMIN_ID:
        total_files = len(get_all_files())
        products = get_current_products()
        
        await update.message.reply_text(
            f"🎯 Admin Panel\n\n"
            f"/upload - Upload product\n"
            f"/list - List products\n"
            f"/delete <pos> - Delete\n"
            f"/files - Show files\n"
            f"/stats - Stats\n\n"
            f"Files: {total_files} | Products: {len(products)}"
        )
    else:
        await update.message.reply_text("🤖 NEXO MODS File Bot")

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    temp_upload[user_id] = {}
    
    await update.message.reply_text("📤 Step 1/3: Send FILE")
    return WAITING_FOR_FILE

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if update.message.document:
        temp_upload[user_id] = {
            'file_id': update.message.document.file_id,
            'file_name': update.message.document.file_name
        }
        await update.message.reply_text(f"✅ File: {update.message.document.file_name}\nStep 2/3: Send IMAGE URL")
        return WAITING_FOR_IMAGE_URL
    
    await update.message.reply_text("❌ Send document file!")
    return WAITING_FOR_FILE

async def receive_image_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    image_url = update.message.text.strip()
    
    if image_url.startswith("http"):
        temp_upload[user_id]['image_url'] = image_url
        await update.message.reply_text("✅ Step 3/3: Send TITLE")
        return WAITING_FOR_TITLE
    
    await update.message.reply_text("❌ Valid URL!")
    return WAITING_FOR_IMAGE_URL

async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    title = update.message.text.strip()
    
    import time
    file_key = f"file_{int(time.time())}_{user_id}"
    
    file_data = {
        "title": title,
        "file_id": temp_upload[user_id]['file_id'],
        "file_name": temp_upload[user_id]['file_name']
    }
    
    db_saved = save_file_to_db(file_key, file_data)
    
    products = get_current_products()
    new_product = {
        "title": title,
        "image_url": temp_upload[user_id]['image_url'],
        "download_link": f"https://t.me/{context.bot.username}?start={file_key}"
    }
    products.insert(0, new_product)
    
    github_saved = update_github_file(products)
    del temp_upload[user_id]
    
    status = "✅" if db_saved and github_saved else "⚠️"
    await update.message.reply_text(
        f"{status} Added!\n"
        f"ID: `{file_key}`\n"
        f"DB: {'✅' if db_saved else '❌'}\n"
        f"GitHub: {'✅' if github_saved else '❌'}",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled!")
    return ConversationHandler.END

async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    products = get_current_products()
    if not products:
        await update.message.reply_text("No products!")
        return
    
    msg = "📁 Products:\n\n"
    for i, p in enumerate(products):
        msg += f"{i+1}. `{p.get('title', '')[:40]}`\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def show_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    files = get_all_files()
    if not files:
        await update.message.reply_text("No files!")
        return
    
    msg = f"📦 Files ({len(files)}):\n\n"
    for i, (key, data) in enumerate(list(files.items())[:15]):
        msg += f"{i+1}. `{key}` - {data['title'][:30]}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /delete 1")
        return
    
    try:
        pos = int(args[0]) - 1
        products = get_current_products()
        if 0 <= pos < len(products):
            deleted = products.pop(pos)
            success = update_github_file(products)
            status = "✅" if success else "❌"
            await update.message.reply_text(f"{status} Deleted: {deleted.get('title', '')}")
        else:
            await update.message.reply_text("❌ Invalid position!")
    except:
        await update.message.reply_text("❌ Invalid number!")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    products = get_current_products()
    files = len(get_all_files())
    
    await update.message.reply_text(
        f"📊 Stats:\n"
        f"Files: {files}\n"
        f"Products: {len(products)}\n"
        f"Storage: {'MongoDB' if MONGODB_AVAILABLE else 'Local'}"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

def main():
    # **FINAL FIX: Use correct v20.x syntax**
    print("🚀 Starting bot...")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_start)],
        states={
            WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, receive_file)],
            WAITING_FOR_IMAGE_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_image_url)],
            WAITING_FOR_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_files))
    app.add_handler(CommandHandler("files", show_files))
    app.add_handler(CommandHandler("delete", delete_file))
    app.add_handler(CommandHandler("stats", stats))
    app.add_error_handler(error_handler)
    
    print("✅ Bot handlers added")
    print(f"Storage: {'MongoDB' if MONGODB_AVAILABLE else 'Local'}")
    
    # **CRITICAL FIX: Use proper polling with read_timeout**
    app.run_polling(
        read_timeout=10,
        write_timeout=10,
        connect_timeout=10,
        pool_timeout=10,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()