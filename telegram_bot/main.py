import logging
logging.basicConfig(level=logging.DEBUG)
print("Bot is starting...")


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("Deploy the Bot", url="https://DaHormes-Fwd-Bot")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome to DahormesForward!\n\nDeploy the bot, then use /setsource and /setdestination to configure.",
        reply_markup=reply_markup
    )

async def set_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting"] = "source"
    await update.message.reply_text("Now forward a message from the source chat to this bot.")

async def set_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting"] = "destination"
    await update.message.reply_text("Now forward a message from the destination chat to this bot.")

'''
async def set_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if update.message and update.message.forward_origin and update.message.forward_origin.chat:
        source_id = update.message.forward_origin.chat.id
        supabase.table("user_configs").upsert(
            {"user_id": user_id, "source_id": source_id}
        ).execute()
        await update.message.reply_text("Source chat set! Now use /setdestination.")
    else:
        await update.message.reply_text("Please forward a message from the source chat.")

async def set_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if update.message and update.message.forward_origin and update.message.forward_origin.chat:
        destination_id = update.message.forward_origin.chat.id
        supabase.table("user_configs").upsert(
            {"user_id": user_id, "destination_id": destination_id}
        ).execute()
        await update.message.reply_text("Destination chat set! Your bot is now active.")
    else:
        await update.message.reply_text("Please forward a message from the target chat.")
'''
        
## New Function to handle forwarded messages for source and destination
async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message

    if not message or not message.forward_origin:
        await message.reply_text("Could not detect forwarded chat. Try again.")
        return

   
    # Handle different types of forwarded messages
    chat_id = None
    if hasattr(message.forward_origin, "chat"):
        chat_id = message.forward_origin.chat.id
    elif hasattr(message.forward_origin, "sender_chat"):
        chat_id = message.forward_origin.sender_chat.id
    elif hasattr(message.forward_origin, "sender_user"):
        chat_id = message.forward_origin.sender_user.id

    if not chat_id:
        await message.reply_text("Could not detect chat ID. Try forwarding from a group, channel, or private chat.")
        return

    if context.user_data.get("awaiting") == "source":
        supabase.table("user_configs").upsert(
            {"user_id": user_id, "source_id": chat_id}
        ).execute()
        await message.reply_text("✅ Source chat set! Now use /setdestination.")
        context.user_data["awaiting"] = None
    elif context.user_data.get("awaiting") == "destination":
        supabase.table("user_configs").upsert(
            {"user_id": user_id, "destination_id": chat_id}
        ).execute()
        await message.reply_text("✅ Destination chat set! Your bot is now active.")
        context.user_data["awaiting"] = None
    else:
        await message.reply_text("Use /setsource or /setdestination first.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    response = supabase.table("user_configs").select("*").eq("user_id", user_id).execute()
    if response.data:
        config = response.data[0]
        await update.message.reply_text(
            f"Current config:\nSource Chat: {config['source_id']}\nDestination Chat: {config['destination_id']}"
        )
    else:
        await update.message.reply_text("No configuration set. Use /setsource and /setdestination.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    supabase.table("user_configs").delete().eq("user_id", user_id).execute()
    await update.message.reply_text("Configuration reset. Start fresh with /setsource.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Usage Guide:\n"
        "/start - Get started\n"
        "/setsource - Forward a message from the source chat\n"
        "/setdestination - Forward a message from the target chat\n"
        "/status - View your config\n"
        "/reset - Start fresh\n"
        "/help - Show this guide"
    )

def main():
    print("Initializing bot application...")
    app = Application.builder().token(BOT_TOKEN).build()
    print("Adding handlers...")
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setsource", set_source))
    app.add_handler(CommandHandler("setdestination", set_destination))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forwarded_message))
    app.add_handler(MessageHandler(filters.FORWARDED, set_source, block=False))
    app.add_handler(MessageHandler(filters.FORWARDED, set_destination, block=False))
    print("Bot is running. Waiting for messages...")
    app.run_polling()

if __name__ == "__main__":
    main()