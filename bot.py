import os
import json
import logging
import base64
import requests
import ssl
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from pymongo import MongoClient
from pymongo.errors import ConfigurationError

# ========== FIX FOR TERMUX DNS ==========
os.environ['DNS_RESOLV_CONF'] = '/data/data/com.termux/files/usr/etc/resolv.conf'

try:
    resolv_path = '/data/data/com.termux/files/usr/etc/resolv.conf'
    if not os.path.exists(resolv_path):
        with open(resolv_path, 'w') as f:
            f.write("nameserver 8.8.8.8\nnameserver 8.8.4.4\n")
        print(f"✅ Created {resolv_path}")
except:
    pass

# ========== CONFIGURATION ==========
BOT_TOKEN = "7718352742:AAG1H680asb9vpfsazZZQdp59vNkx2PjGbw"
ADMIN_ID = 1944182800

MONGO_URI = "mongodb+srv://rishi:ipxkingyt@rishiv.ncljp.mongodb.net/?retryWrites=true&w=majority&appName=rishiv"
DB_NAME = "nexo_bot"
COLLECTION_NAME = "products"
FILES_COLLECTION = "stored_files"

GITHUB_TOKEN = "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"
REPO_OWNER = "fghhvdty"
REPO_NAME = "Daku"
FILE_PATH = "File.json"
GITHUB_API_URL = f"https://api.github.com/repos/fghhvdty/Daku/contents/File.json?ref=main"
RAW_URL = f"https://raw.githubusercontent.com/fghhvdty/Daku/refs/heads/main/File.json"

# Conversation states
WAITING_FOR_FILE = 1
WAITING_FOR_IMAGE_URL = 2
WAITING_FOR_TITLE = 3

# Temp storage
temp_upload = {}

# MongoDB Connection
def connect_mongodb():
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("✅ MongoDB Connected Successfully!")
        return client
    except ConfigurationError as e:
        print(f"⚠️ DNS Error: {e}")
        try:
            client = MongoClient(
                "mongodb://rishi:ipxkingyt@rishiv.ncljp.mongodb.net:27017/?ssl=true&replicaSet=atlas-xyz&authSource=admin",
                serverSelectionTimeoutMS=5000,
                ssl=True,
                ssl_cert_reqs=ssl.CERT_NONE
            )
            client.admin.command('ping')
            print("✅ MongoDB Connected via alternative method!")
            return client
        except Exception as e2:
            print(f"❌ MongoDB connection failed: {e2}")
            return None
    except Exception as e:
        print(f"❌ MongoDB connection error: {e}")
        return None

client = connect_mongodb()

if client:
    db = client[DB_NAME]
    products_collection = db[COLLECTION_NAME]
    files_collection = db[FILES_COLLECTION]
    MONGODB_AVAILABLE = True
else:
    MONGODB_AVAILABLE = False
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
            logger.info(f"File saved to MongoDB: {file_key}")
            return True
        except Exception as e:
            logger.error(f"MongoDB save error: {e}")
            return False
    else:
        files_db[file_key] = file_data
        save_local_files(files_db)
        logger.info(f"File saved locally: {file_key}")
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
        except Exception as e:
            logger.error(f"MongoDB fetch error: {e}")
            return None
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
        except Exception as e:
            logger.error(f"MongoDB fetch all error: {e}")
            return {}
    else:
        return files_db

def delete_file_from_db(file_key):
    if MONGODB_AVAILABLE:
        try:
            result = files_collection.delete_one({"file_key": file_key})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"MongoDB delete error: {e}")
            return False
    else:
        if file_key in files_db:
            del files_db[file_key]
            save_local_files(files_db)
            return True
        return False

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
            logger.info(f"Current GitHub file SHA: {sha}")
        
        data = {
            "message": f"Update products via bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": encoded_content,
            "sha": sha
        }
        
        put_response = requests.put(GITHUB_API_URL, headers=headers, json=data, timeout=10)
        logger.info(f"GitHub PUT response: {put_response.status_code}")
        
        return put_response.status_code == 200
        
    except Exception as e:
        logger.error(f"GitHub update error: {e}")
        return False

def get_current_products():
    for attempt in range(3):
        try:
            response = requests.get(RAW_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            products = data.get("products", [])
            logger.info(f"✅ Fetched {len(products)} products from GitHub")
            return products
        except Exception as e:
            logger.error(f"GitHub fetch attempt {attempt+1} failed: {e}")
            if attempt == 2:
                return []
    return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    args = context.args
    if args and len(args) > 0:
        file_key = args[0]
        logger.info(f"Deep link detected: {file_key} for user {user_id}")
        
        file_data = get_file_from_db(file_key)
        
        if file_data:
            try:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file_data['file_id'],
                    caption=f"📁 {file_data['title']}\n\nSource: NEXO MODS\nEnjoy!",
                    filename=file_data['file_name']
                )
                logger.info(f"✅ File sent to user {user_id}: {file_key}")
                return
            except Exception as e:
                logger.error(f"❌ Error sending file {file_key}: {e}")
                await update.message.reply_text("❌ Error sending file! Please contact admin.")
                return
    
    if user_id == ADMIN_ID:
        total_files = len(get_all_files())
        products = get_current_products()
        
        await update.message.reply_text(
            f"🎯 Admin Panel Active\n\n"
            f"Commands:\n"
            f"/upload - Upload new product\n"
            f"/list - List all products\n"
            f"/delete <position> - Delete product\n"
            f"/stats - Bot statistics\n"
            f"/files - Show stored files\n\n"
            f"📊 Database Stats:\n"
            f"• Files in DB: {total_files}\n"
            f"• Products online: {len(products)}\n"
            f"• Storage: {'MongoDB' if MONGODB_AVAILABLE else 'Local File'}\n\n"
            f"Raw URL: {RAW_URL}"
        )
    else:
        await update.message.reply_text("🤖 Welcome to NEXO MODS File Bot\n\nUse app to download files!")

async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    temp_upload[user_id] = {}
    
    await update.message.reply_text(
        "📤 Upload New Product\n\n"
        "Step 1/3: Send the FILE (apk/zip/document)\n\n"
        "Send /cancel to cancel"
    )
    return WAITING_FOR_FILE

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message
    
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    else:
        await update.message.reply_text("❌ Please send a document file!")
        return WAITING_FOR_FILE
    
    temp_upload[user_id]['file_id'] = file_id
    temp_upload[user_id]['file_name'] = file_name
    
    await update.message.reply_text(
        f"✅ File received: {file_name}\n\n"
        "Step 2/3: Send the IMAGE URL (direct link from ImgBB/imgur)\n\n"
        "Example: https://i.ibb.co/xyz/image.jpg\n\n"
        "Send /cancel to cancel"
    )
    return WAITING_FOR_IMAGE_URL

async def receive_image_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    image_url = update.message.text.strip()
    
    if not image_url.startswith("http"):
        await update.message.reply_text("❌ Please send a valid URL!")
        return WAITING_FOR_IMAGE_URL
    
    temp_upload[user_id]['image_url'] = image_url
    
    await update.message.reply_text(
        "✅ Image URL received!\n\n"
        "Step 3/3: Send the TITLE for this product\n\n"
        "Example: FLASH HACKER 4.3 PVT SOURCE\n\n"
        "Send /cancel to cancel"
    )
    return WAITING_FOR_TITLE

async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    title = update.message.text.strip()
    
    temp_upload[user_id]['title'] = title
    
    import time
    file_key = f"file_{int(time.time())}_{user_id}"
    
    file_data = {
        "title": title,
        "file_id": temp_upload[user_id]['file_id'],
        "file_name": temp_upload[user_id]['file_name']
    }
    db_saved = save_file_to_db(file_key, file_data)
    
    if not db_saved:
        await update.message.reply_text("❌ Database save failed! Try again.")
        return ConversationHandler.END
    
    logger.info("Fetching current products from GitHub...")
    products = get_current_products()
    
    new_product = {
        "title": title,
        "image_url": temp_upload[user_id]['image_url'],
        "download_link": f"https://t.me/{context.bot.username}?start={file_key}"
    }
    
    products.insert(0, new_product)
    
    logger.info("Updating GitHub...")
    success = update_github_file(products)
    
    temp_upload.pop(user_id, None)
    
    if success and db_saved:
        await update.message.reply_text(
            f"✅ Product Added Successfully! 🎉\n\n"
            f"📝 Title: {title}\n"
            f"🆔 ID: `{file_key}`\n"
            f"📊 Total products: {len(products)}\n\n"
            f"✅ Database: Saved ✓\n"
            f"✅ GitHub: Updated ✓\n\n"
            f"🔗 Raw URL: {RAW_URL}",
            parse_mode="Markdown"
        )
    elif db_saved:
        await update.message.reply_text(
            f"⚠️ Database Saved but GitHub FAILED!\n\n"
            f"📝 Title: {title}\n"
            f"🆔 ID: `{file_key}`\n"
            f"✅ You can still use: https://t.me/{context.bot.username}?start={file_key}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("❌ Both Database & GitHub failed!")
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    temp_upload.pop(user_id, None)
    await update.message.reply_text("❌ Upload cancelled!")
    return ConversationHandler.END

async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    products = get_current_products()
    
    if not products:
        await update.message.reply_text("No products found!")
        return
    
    message = f"📁 Products ({len(products)} total):\n\n"
    for i, product in enumerate(products):
        title = product.get('title', 'No title')[:50]
        message += f"{i+1}. `{title}`\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def show_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    files = get_all_files()
    
    if not files:
        await update.message.reply_text("No files stored in database!")
        return
    
    message = f"📦 Stored Files ({len(files)} total, {'MongoDB' if MONGODB_AVAILABLE else 'Local'}):\n\n"
    for key, value in list(files.items())[:20]:
        message += f"• `{key}` - {value['title']}\n"
    
    if len(files) > 20:
        message += f"\n... and {len(files) - 20} more"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /delete <position_number>\nExample: /delete 1")
        return
    
    try:
        position = int(args[0]) - 1
    except:
        await update.message.reply_text("❌ Please provide a valid number!")
        return
    
    products = get_current_products()
    
    if position < 0 or position >= len(products):
        await update.message.reply_text(f"❌ Position {position+1} not found! (Total: {len(products)})")
        return
    
    deleted = products.pop(position)
    success = update_github_file(products)
    
    if success:
        await update.message.reply_text(
            f"✅ Deleted: {deleted.get('title', 'Unknown')}\n"
            f"📊 Remaining: {len(products)} products"
        )
    else:
        await update.message.reply_text("❌ Delete failed on GitHub!")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    products = get_current_products()
    total_files = len(get_all_files())
    
    await update.message.reply_text(
        f"📊 Bot Statistics\n\n"
        f"📦 Database:\n"
        f"• Total files: {total_files}\n"
        f"• Storage: {'MongoDB' if MONGODB_AVAILABLE else 'Local File'}\n\n"
        f"📁 GitHub:\n"
        f"• Products online: {len(products)}\n"
        f"• Raw URL: {RAW_URL}\n\n"
        f"🤖 Bot Active: ✅"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

def main():
    # **FIXED: Use correct v21.0+ syntax**
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("upload", upload_start)],
        states={
            WAITING_FOR_FILE: [MessageHandler(filters.Document.ALL, receive_file)],
            WAITING_FOR_IMAGE_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_image_url)],
            WAITING_FOR_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("list", list_files))
    application.add_handler(CommandHandler("files", show_files))
    application.add_handler(CommandHandler("delete", delete_file))
    application.add_handler(CommandHandler("stats", stats))
    application.add_error_handler(error_handler)
    
    print("\n🤖 Bot is running...")
    print(f"Raw URL: {RAW_URL}")
    print(f"Storage Mode: {'MongoDB' if MONGODB_AVAILABLE else 'Local File'}")
    print(f"Total files: {len(get_all_files())}")
    
    # **FIXED: Use application.run_polling()**
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()