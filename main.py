import logging
import os
import json
import asyncio
import random
import string
import time
from datetime import timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# ===== CONFIG =====
BOT_TOKEN = "8182613736:AAESfxF6WK8srcgCYEKkJtFii4BXsD6WLXk"
STORE_CHANNEL_ID = -1002893816996
DATA_FILE = "file_data.json"
USER_DATA_FILE = "users.json"
BANNED_USERS_FILE = "banned_users.json"
USER_FILES_FILE = "user_files.json"
ADMIN_ID = 7251749429
BOT_USERNAME = "XFilesStoreBot"
DOWNLOADS_FILE = "downloads.json"

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== FILE INIT =====
for fpath, default in [
    (DATA_FILE, {}),
    (USER_DATA_FILE, []),
    (BANNED_USERS_FILE, []),
    (USER_FILES_FILE, {}),
    (DOWNLOADS_FILE, {}),
]:
    if not os.path.exists(fpath):
        with open(fpath, "w", encoding="utf-8") as fp:
            json.dump(default, fp)

# ===== HELPERS =====

def safe_load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if type(data) != type(default):
            return default
        return data
    except Exception:
        return default

def safe_save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_code(length: int = 18) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))

def add_user(user_id: int):
    users = safe_load_json(USER_DATA_FILE, [])
    if user_id not in users:
        users.append(user_id)
        safe_save_json(USER_DATA_FILE, users)

def is_banned(user_id: int) -> bool:
    banned = safe_load_json(BANNED_USERS_FILE, [])
    return user_id in banned

def ban_user(user_id: int) -> bool:
    banned = safe_load_json(BANNED_USERS_FILE, [])
    if user_id not in banned:
        banned.append(user_id)
        safe_save_json(BANNED_USERS_FILE, banned)
        return True
    return False

def unban_user(user_id: int) -> bool:
    banned = safe_load_json(BANNED_USERS_FILE, [])
    if user_id in banned:
        banned.remove(user_id)
        safe_save_json(BANNED_USERS_FILE, banned)
        return True
    return False

def save_file(code: str, info: dict):
    data = safe_load_json(DATA_FILE, {})
    data[code] = info
    safe_save_json(DATA_FILE, data)

def get_file(code):
    # Ensure code is always a string
    if isinstance(code, list):
        code = code[0] if code else None
    if not isinstance(code, str):
        return None
    data = safe_load_json(DATA_FILE, {})
    return data.get(code)

def delete_file(code: str) -> bool:
    data = safe_load_json(DATA_FILE, {})
    if code in data:
        del data[code]
        safe_save_json(DATA_FILE, data)
        return True
    return False

def count_users() -> int:
    return len(safe_load_json(USER_DATA_FILE, []))

def count_banned() -> int:
    return len(safe_load_json(BANNED_USERS_FILE, []))

def count_files() -> int:
    return len(safe_load_json(DATA_FILE, {}))

def add_file_to_user(user_id: int, file_code: str):
    user_files = safe_load_json(USER_FILES_FILE, {})
    files_list = user_files.get(str(user_id), [])
    if file_code not in files_list:
        files_list.append(file_code)
        user_files[str(user_id)] = files_list
        safe_save_json(USER_FILES_FILE, user_files)

def remove_file_from_user(user_id: int, file_code: str):
    user_files = safe_load_json(USER_FILES_FILE, {})
    files_list = user_files.get(str(user_id), [])
    if file_code in files_list:
        files_list.remove(file_code)
        user_files[str(user_id)] = files_list
        safe_save_json(USER_FILES_FILE, user_files)

def get_user_files(user_id: int):
    user_files = safe_load_json(USER_FILES_FILE, {})
    return user_files.get(str(user_id), [])

def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for u in units:
        if size < 1024 or u == "TB":
            return f"{size:.2f} {u}"
        size /= 1024.0
    return f"{size:.2f} TB"

def fmt_hhmmss(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return str(timedelta(seconds=seconds))

def build_progress_bar(percent: float) -> str:
    blocks = 10
    filled = max(0, min(blocks, int(percent // 10)))
    return "▰" * filled + "▱" * (blocks - filled)

def inc_download_count(code):
    downloads = safe_load_json(DOWNLOADS_FILE, {})
    if code not in downloads:
        downloads[code] = 0
    downloads[code] += 1
    safe_save_json(DOWNLOADS_FILE, downloads)

def get_download_count_by_code(code):
    downloads = safe_load_json(DOWNLOADS_FILE, {})
    return downloads.get(code, 0)

# ===== HANDLERS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return

    if context.args and len(context.args) > 0:
        code = context.args[0]
        await retrieve_and_send_file(update, context, code)
        return

    add_user(user_id)
    await update.message.reply_text(
        "👋 Welcome to File Store Bot!\n\n"
        "📤 Send me any file (APK, PDF, Photo, etc.) and I'll save it securely.\n"
        "🧾 I'll give you a secure file code.\n"
        "📥 Send me that code anytime to retrieve your file.\n\n"
        "📁 Use /myfiles to see all your uploaded files and their codes.\n"
        "🔎 Use /search <FileCode> to view info for a file by its code.\n"
        "📊 Use /download <FileCode> to download and check stats for a file by its code."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/myfiles - List all your uploaded files\n"
        "/search <FileCode> - Get info for a file by code\n"
        "/download <FileCode> - Download a file and see download count\n"
        "/broadcast <message> - Send message to all users (Admin only)\n"
        "/ban <user_id> - Ban a user (Admin only)\n"
        "/unban <user_id> - Unban a user (Admin only)\n"
        "/listfiles - List all stored file codes (Admin only)\n"
        "/deletefile <file_code> - Delete a file by code (Admin only)\n"
        "/stats - Show bot statistics (Admin only)\n\n"
        "To use:\n"
        "• Send any supported file to get a secure code.\n"
        "• Send the code to retrieve your file.\n"
        "• /search <FileCode> to view info for a file by code.\n"
        "• /download <FileCode> to download or check stats."
    )
    await update.message.reply_text(help_text)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    add_user(user_id)

    message = update.message
    doc = message.document
    photo = message.photo[-1] if message.photo else None
    video = message.video
    audio = message.audio
    voice = message.voice

    user_info = (
        f"👤 User: {user.first_name or ''} (@{user.username or 'NoUsername'})\n"
        f"🆔 User ID: {user_id}\n"
        f"👥 Total users: {count_users()}"
    )

    file_id = None
    file_type = None
    file_name = None

    if doc:
        file_id = doc.file_id
        file_type = "document"
        file_name = doc.file_name
    elif photo:
        file_id = photo.file_id
        file_type = "photo"
        file_name = "photo"
    elif video:
        file_id = video.file_id
        file_type = "video"
        file_name = getattr(video, "file_name", "video")
    elif audio:
        file_id = audio.file_id
        file_type = "audio"
        file_name = getattr(audio, "file_name", "audio")
    elif voice:
        file_id = voice.file_id
        file_type = "voice"
        file_name = "voice"
    else:
        await message.reply_text("❌ Unsupported file type.")
        return

    caption_text = message.caption or ""

    try:
        tfile = await context.bot.get_file(file_id)
        total_bytes = tfile.file_size or 0
    except Exception as e:
        logger.warning(f"Could not get file size: {e}")
        total_bytes = 0

    uploading_msg = await message.reply_text("📤 Uploading your file... Please wait.")
    delay_secs = random.uniform(3, 5)
    await asyncio.sleep(delay_secs)

    try:
        sent_message = None
        if file_type == "document":
            sent_message = await context.bot.send_document(
                chat_id=STORE_CHANNEL_ID, document=file_id, caption=user_info
            )
        elif file_type == "photo":
            sent_message = await context.bot.send_photo(
                chat_id=STORE_CHANNEL_ID, photo=file_id, caption=user_info
            )
        elif file_type == "video":
            sent_message = await context.bot.send_video(
                chat_id=STORE_CHANNEL_ID, video=file_id, caption=user_info
            )
        elif file_type == "audio":
            sent_message = await context.bot.send_audio(
                chat_id=STORE_CHANNEL_ID, audio=file_id, caption=user_info
            )
        elif file_type == "voice":
            sent_message = await context.bot.send_voice(
                chat_id=STORE_CHANNEL_ID, voice=file_id, caption=user_info
            )

        code = generate_code(18)
        message_id = sent_message.message_id if sent_message else None

        save_file(code, {
            "file_id": file_id,
            "type": file_type,
            "caption": caption_text,
            "user_id": user_id,
            "message_id": message_id,
            "file_name": file_name,
            "size_bytes": int(total_bytes)
        })
        add_file_to_user(user_id, code)

        link = f"https://t.me/{BOT_USERNAME}?start={code}"
        size_text = human_size(total_bytes) if total_bytes > 0 else "Unknown"
        final_text = (
            f"✅ <b>File Uploaded</b>\n"
            f"📁 <b>File Name:</b> {file_name}\n\n"
            f"🗂️ <b>File Size:</b> {size_text}\n\n"
            f"🔗 <b>File Link:</b> {link}\n\n"
            f"✅ <b>File Link (1 Tap Copy):</b> <code>{link}</code>\n\n"
            f"📮 @{BOT_USERNAME} & @R3v_X"
        )
        try:
            await uploading_msg.edit_text(final_text, parse_mode="HTML", disable_web_page_preview=True)
        except Exception:
            await update.message.reply_text(final_text, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error saving/sending to channel: {e}")
        try:
            await uploading_msg.edit_text("⚠️ Failed to save file.", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("⚠️ Failed to save file.")

async def retrieve_and_send_file(update: Update, context: ContextTypes.DEFAULT_TYPE, code):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    add_user(user_id)

    file_info = get_file(code)
    if not file_info:
        await update.message.reply_text("❌ File not found. Double-check your code.")
        return

    try:
        ftype = file_info.get("type")
        fid = file_info.get("file_id")
        caption = file_info.get("caption", None)
        inc_download_count(code)
        if ftype == "document":
            await context.bot.send_document(update.effective_chat.id, document=fid, caption=caption)
        elif ftype == "photo":
            await context.bot.send_photo(update.effective_chat.id, photo=fid, caption=caption)
        elif ftype == "video":
            await context.bot.send_video(update.effective_chat.id, video=fid, caption=caption)
        elif ftype == "audio":
            await context.bot.send_audio(update.effective_chat.id, audio=fid, caption=caption)
        elif ftype == "voice":
            await context.bot.send_voice(update.effective_chat.id, voice=fid, caption=caption)
        else:
            await update.message.reply_text("❌ Unknown file type.")
        await asyncio.sleep(0.5)
    except Exception as e:
        logger.error(f"Error retrieving file: {e}")
        await update.message.reply_text("⚠️ Failed to retrieve the file. Try again later.")

async def retrieve_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = (update.message.text or "").strip()
    if isinstance(code, list):
        code = code[0] if code else ""
    if len(code) < 10:
        await update.message.reply_text("❌ Invalid code.")
        return
    await retrieve_and_send_file(update, context, code)

async def myfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    add_user(user_id)

    codes = get_user_files(user_id)
    if not codes:
        await update.message.reply_text("ℹ️ You have no files saved.")
        return

    data = safe_load_json(DATA_FILE, {})
    lines = []
    for code in codes:
        f = data.get(code)
        if f:
            typ = f.get("type", "unknown")
            caption = f.get("caption", "")
            short_caption = (caption[:30] + "...") if caption and len(caption) > 30 else caption
            link = f"https://t.me/{BOT_USERNAME}?start={code}"
            dcount = get_download_count_by_code(code)
            lines.append(f"• <code>{code}</code> - {typ} <b>({dcount} downloads)</b>{('- ' + short_caption) if short_caption else ''}\n   🔗 {link}")
        else:
            lines.append(f"• <code>{code}</code> - [Deleted or Missing]")

    text = "📁 <b>Your Uploaded Files:</b>\n\n" + "\n".join(lines) + "\n\nSend any file code to retrieve that file."
    await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You're not authorized.")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /broadcast <message>")
        return

    text = " ".join(context.args)
    await update.message.reply_text("📢 Sending broadcast...")

    users = safe_load_json(USER_DATA_FILE, [])
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=text)
            count += 1
            await asyncio.sleep(0.07)
        except Exception as e:
            logger.error(f"Failed to send to user {uid}: {e}")
    await update.message.reply_text(f"✅ Broadcast sent to {count} users.")

async def ban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You're not authorized.")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /ban <user_id>")
        return
    try:
        uid = int(context.args[0])
    except Exception:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    if ban_user(uid):
        await update.message.reply_text(f"🚫 User {uid} banned.")
    else:
        await update.message.reply_text(f"ℹ️ User {uid} is already banned.")

async def unban_user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You're not authorized.")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /unban <user_id>")
        return
    try:
        uid = int(context.args[0])
    except Exception:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    if unban_user(uid):
        await update.message.reply_text(f"✅ User {uid} unbanned.")
    else:
        await update.message.reply_text(f"ℹ️ User {uid} was not banned.")

async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You're not authorized.")
        return
    data = safe_load_json(DATA_FILE, {})
    if not data:
        await update.message.reply_text("No files stored.")
        return
    lines = [f"• <code>{k}</code> - {v.get('type','unknown')} (User: {v.get('user_id','Unknown')})" for k, v in data.items()]
    out = "📂 <b>Stored Files:</b>\n\n" + "\n".join(lines[:50])
    await update.message.reply_text(out, parse_mode="HTML", disable_web_page_preview=True)

async def delete_file_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You're not authorized.")
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /deletefile <file_code>")
        return
    code = context.args[0]
    data = safe_load_json(DATA_FILE, {})
    owner_id = data.get(code, {}).get("user_id") if code in data else None
    if delete_file(code):
        if owner_id:
            remove_file_from_user(owner_id, code)
        await update.message.reply_text(f"✅ File <code>{code}</code> deleted.", parse_mode="HTML")
    else:
        await update.message.reply_text("❌ File code not found.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You're not authorized.")
        return
    total_users = count_users()
    total_banned = count_banned()
    total_files = count_files()
    await update.message.reply_text(
        f"📊 Bot Statistics:\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🚫 Banned Users: {total_banned}\n"
        f"📂 Stored Files: {total_files}"
    )

# NEW: /search <FileCode> COMMAND (by file code only)
async def search_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    add_user(user_id)
    if not context.args:
        await update.message.reply_text("Usage: /search <FileCode>. Please provide a file code to search.")
        return
    code = context.args[0]
    file_info = get_file(code)
    if not file_info:
        await update.message.reply_text("❌ File not found. Double-check your code.")
        return
    fname = str(file_info.get("file_name", "")).strip()
    ftype = str(file_info.get("type", "")).strip()
    caption = file_info.get("caption", "")
    size = human_size(file_info.get("size_bytes", 0))
    user_id = file_info.get("user_id")
    downloads = get_download_count_by_code(code)
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    info = (
        f"🔍 <b>File Info:</b>\n\n"
        f"• <b>File Code:</b> <code>{code}</code>\n"
        f"• <b>File Name:</b> {fname}\n"
        f"• <b>Type:</b> {ftype}\n"
        f"• <b>Size:</b> {size}\n"
        f"• <b>Uploads By User ID:</b> <code>{user_id}</code>\n"
        f"• <b>Downloads:</b> {downloads}\n"
        f"• <b>Link:</b> {link}\n"
        f"{f'• <b>Caption:</b> {caption}' if caption else ''}"
    )
    await update.message.reply_text(info, parse_mode="HTML", disable_web_page_preview=True)

# NEW: /download <FileCode> COMMAND (by file code only)
async def download_file_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_banned(user_id):
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return
    add_user(user_id)
    if not context.args:
        await update.message.reply_text("Usage: /download <FileCode>. Please provide the file code.")
        return
    code = context.args[0]
    file_info = get_file(code)
    if not file_info:
        await update.message.reply_text("❌ File not found. Double-check your code.")
        return
    downloads = get_download_count_by_code(code)
    fname = file_info.get("file_name", "unknown")
    await update.message.reply_text(f"🔄 Download requested. File <b>{fname}</b> has been downloaded <b>{downloads}</b> times.", parse_mode="HTML")
    await retrieve_and_send_file(update, context, code)

# ===== RUN BOT =====

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myfiles", myfiles))
    app.add_handler(CommandHandler("search", search_files))        # by file code
    app.add_handler(CommandHandler("download", download_file_cmd)) # by file code
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("ban", ban_user_cmd))
    app.add_handler(CommandHandler("unban", unban_user_cmd))
    app.add_handler(CommandHandler("listfiles", list_files))
    app.add_handler(CommandHandler("deletefile", delete_file_cmd))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, retrieve_file))
    print("✅ Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()

