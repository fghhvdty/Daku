import os
import json
import logging
import base64
import requests
import ssl
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ========== CONFIGURATION ==========
BOT_TOKEN = "7718352742:AAG1H680asb9vpfsazZZQdp59vNkx2PjGbw"
ADMIN_ID = 1944182800

# Local storage config
LOCAL_STORAGE_FILE = "local_files.json"
files_db = {}

# Load local files
def load_local_files():
    global files_db
    if os.path.exists(LOCAL_STORAGE_FILE):
        try:
            with open(LOCAL_STORAGE_FILE, "r") as f:
                files_db = json.load(f)
        except:
            files_db = {}
    else:
        files_db = {}

# Save local files
def save_local_files():
    try:
        with open(LOCAL_STORAGE_FILE, "w") as f:
            json.dump(files_db, f, indent=2)
    except Exception as e:
        print(f"Local save error: {e}")

# Initialize local storage
load_local_files()

# GitHub Repository Config
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== LOCAL STORAGE FUNCTIONS ==========
def save_file_to_db(file_key, file_data):
    """Save file mapping to local file"""
    try:
        files_db[file_key] = file_data
        save_local_files()
        logger.info(f"File saved locally: {file_key}")
        return True
    except Exception as e:
        logger.error(f"Local save error: {e}")
        return False

def get_file_from_db(file_key):
    """Get file mapping from local file"""
    return files_db.get(file_key)

def get_all_files():
    """Get all files from local file"""
    return files_db.copy()

def delete_file_from_db(file_key):
    """Delete file from local file"""
    if file_key in files_db:
        del files_db[file_key]
        save_local_files()
        return True
    return False

# ========== GITHUB FUNCTIONS ==========
def update_github_file(products_list):
    """Update File.json on GitHub"""
    content = json.dumps({"products": products_list}, indent=2)
    encoded_content = base64.b64encode(content.encode()).decode()
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        # Get current file SHA - CRITICAL FOR UPDATES
        response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        sha = None
        if response.status_code == 200:
            data = response.json()
            sha = data.get("sha")
            logger.info(f"Current GitHub file SHA: {sha}")
        else:
            logger.warning(f"GitHub GET failed: {response.status_code} - {response.text}")
        
        # Update file with proper SHA
        data = {
            "message": f"Update products via bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "content": encoded_content,
            "sha": sha  # This is CRITICAL - without SHA it overwrites
        }
        
        put_response = requests.put(GITHUB_API_URL, headers=headers, json=data, timeout=10)
        logger.info(f"GitHub PUT response: {put_response.status_code} - {put_response.text[:200]}")
        
        if put_response.status_code == 200:
            logger.info("✅ GitHub file updated successfully!")
            return True
        elif put_response.status_code == 422:
            logger.error("❌ GitHub SHA mismatch - file might have changed externally")
        else:
            logger.error(f"❌ GitHub update failed: {put_response.status_code}")
        
        return put_response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ GitHub network error: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ GitHub update error: {e}")
        return False

def get_current_products():
    """Fetch current products from GitHub raw URL with retry"""
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
                logger.error("❌ All GitHub fetch attempts failed")
                return []
    return []

# ========== BOT COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if this is a deep link with file_key (CRITICAL FIX)
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
                return  # Exit early after sending file
            except Exception as e:
                logger.error(f"❌ Error sending file {file_key}: {e}")
                await update.message.reply_text("❌ Error sending file! Please contact admin.")
                return
    
    # Normal start command for admin/non-deep-link users
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
            f"• Storage: Local File\n\n"
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
    
    # Generate unique file key
    import time
    file_key = f"file_{int(time.time())}_{user_id}"
    
    # Save to database FIRST
    file_data = {
        "title": title,
        "file_id": temp_upload[user_id]['file_id'],
        "file_name": temp_upload[user_id]['file_name']
    }
    db_saved = save_file_to_db(file_key, file_data)
    
    if not db_saved:
        await update.message.reply_text("❌ Database save failed! Try again.")
        return ConversationHandler.END
    
    # Get current products from GitHub - CRITICAL
    logger.info("Fetching current products from GitHub...")
    products = get_current_products()
    logger.info(f"Found {len(products)} existing products")
    
    # Create new product
    new_product = {
        "title": title,
        "image_url": temp_upload[user_id]['image_url'],
        "download_link": f"https://t.me/{context.bot.username}?start={file_key}"
    }
    
    # Add at TOP (index 0) - NEW ITEM FIRST
    products.insert(0, new_product)
    logger.info(f"Added new product. Total now: {len(products)}")
    
    # Update GitHub - CRITICAL STEP
    logger.info("Updating GitHub...")
    success = update_github_file(products)
    
    # Clear temp
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
        link = product.get('download_link', 'No link')
        message += f"{i+1}. `{title}`\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def show_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all stored files from database"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only!")
        return
    
    files = get_all_files()
    
    if not files:
        await update.message.reply_text("No files stored in database!")
        return
    
    message = f"📦 Stored Files ({len(files)} total, Local):\n\n"
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
        f"• Storage: Local File\n\n"
        f"📁 GitHub:\n"
        f"• Products online: {len(products)}\n"
        f"• Raw URL: {RAW_URL}\n\n"
        f"🤖 Bot Active: ✅"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# ========== MAIN ==========
def main():
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
    
    # CRITICAL: Proper handler order
    app.add_handler(conv_handler)  # Conversation first
    app.add_handler(CommandHandler("start", start))  # Start handles deep links
    app.add_handler(CommandHandler("list", list_files))
    app.add_handler(CommandHandler("files", show_files))
    app.add_handler(CommandHandler("delete", delete_file))
    app.add_handler(CommandHandler("stats", stats))
    app.add_error_handler(error_handler)
    
    print("\n🤖 Bot is running...")
    print(f"Raw URL: {RAW_URL}")
    print(f"Storage Mode: Local File")
    print(f"Total files: {len(get_all_files())}")
    
    app.run_polling()

if __name__ == "__main__":
    main()