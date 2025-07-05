import logging
# Set up logging to DEBUG for detailed output in the console.
# This helps in tracking the bot's execution flow and API calls.
logging.basicConfig(level=logging.DEBUG) 
print("Telegram bot is starting...")


from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler # Ensure CallbackQueryHandler is imported for inline keyboard interactions
)
from supabase import create_client, Client # Supabase client for database operations
import os # For accessing environment variables
from dotenv import load_dotenv # To load environment variables from .env file

<<<<<<< HEAD
# Load environment variables from the .env file in the current directory
=======
#To pause Service on railway
if os.getenv("PAUSE") == "true":
    print("🚧 Application is paused. Exiting now.")
    sys.exit(0)

# Load environment variables
>>>>>>> 1f3a4119f3f73ee1fc12cc5ed5bc95745363e66e
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
# This client will interact with your Supabase database to store and retrieve configurations.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /start command.
    Welcomes the user and provides initial instructions and a placeholder deploy link.
    """
    # Create an inline keyboard with a "Deploy the Bot" button.
    # Replace "https://DaHormes-Fwd-Bot" with your actual deployment link if available.
    keyboard = [[InlineKeyboardButton("Check out DaHormes", url="https://www.dahormes.com")]] 
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Welcome to DahormesForward!\n\n"
        "Bot deployed, use /setsource and /setdestination to configure.",
        reply_markup=reply_markup
    )



async def set_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /setsource command.
    Prompts the user to forward a message from the desired source chat.
    Sets a flag in user_data to indicate what the bot is currently awaiting.
    """
    context.user_data["awaiting"] = "source" 
    await update.message.reply_text("Now forward a message from the source chat to this bot.")

async def set_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /setdestination command.
    Prompts the user to forward a message from the desired destination chat.
    Sets a flag in user_data to indicate what the bot is currently awaiting.
    """
    context.user_data["awaiting"] = "destination"
    await update.message.reply_text("Now forward a message from the destination chat to this bot.")

async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /setmode command.
    Provides inline buttons for the user to choose between "Forward All Messages" or "Forward by Keywords".
    """
    keyboard = [
        [InlineKeyboardButton("Forward All Messages", callback_data="set_mode_all")],
        [InlineKeyboardButton("Forward by Keywords", callback_data="set_mode_keywords")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose a forwarding mode:", reply_markup=reply_markup)

async def set_keywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /setkeywords command.
    Prompts the user to send a comma-separated list of keywords.
    Sets a flag in user_data indicating the bot is awaiting keyword input.
    """
    context.user_data["awaiting"] = "keywords"
    await update.message.reply_text("Please send your keywords, separated by commas (e.g., keyword1, keyword2, phrase three).")

async def handle_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles callbacks from the 'set_mode' inline keyboard buttons.
    Updates the forwarding mode in Supabase based on the user's selection.
    """
    query = update.callback_query
    user_id = query.from_user.id
    mode = query.data.replace("set_mode_", "") # Extracts 'all' or 'keywords' from the callback_data

    # Update the user's configuration in the 'user_configs' table in Supabase.
    # The 'upsert' method will insert a new row if user_id doesn't exist, or update it if it does.
    supabase.table("user_configs").upsert(
        {"user_id": user_id, "mode": mode}
    ).execute()
    
    # Edit the original message to show the selected mode.
    await query.edit_message_text(f"Forwarding mode set to: '{mode}'.")
    
    # If "keywords" mode is chosen, prompt the user to set keywords next.
    if mode == "keywords":
        await context.bot.send_message(user_id, "Now, use /setkeywords to define your keywords.")

async def handle_keywords_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles text messages specifically when the bot is awaiting keyword input.
    Parses the input, stores keywords in Supabase, and ensures the mode is 'keywords'.
    """
    user_id = update.effective_user.id
    
    # Check if the bot is specifically awaiting keyword input AND if the message contains text.
    if context.user_data.get("awaiting") == "keywords" and update.message and update.message.text:
        keywords_raw = update.message.text
        # Clean and split keywords: strip whitespace, convert to lowercase, and filter out empty strings.
        keywords_list = [k.strip().lower() for k in keywords_raw.split(',') if k.strip()]
        
        # Update the keywords in Supabase for the current user.
        supabase.table("user_configs").upsert(
            {"user_id": user_id, "keywords": keywords_list}
        ).execute()
        
        await update.message.reply_text(f"Keywords set: {', '.join(keywords_list)}. Mode set to 'keywords'.")
        context.user_data["awaiting"] = None # Clear the awaiting flag as input has been received.
        
        # Explicitly ensure the mode is set to 'keywords' if keywords are provided this way.
        supabase.table("user_configs").upsert({"user_id": user_id, "mode": "keywords"}).execute()
    
    # If awaiting keywords but a non-text message or empty text message is received.
    elif context.user_data.get("awaiting") == "keywords" and (not update.message or not update.message.text):
        await update.message.reply_text("Please send text for keywords.")
    
    # Other text messages not related to awaiting keywords will be processed by other handlers
    # (e.g., command handlers).

async def handle_forwarded_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles all incoming forwarded messages. It determines if the message is for
    setting source or destination chat IDs based on the 'awaiting' flag in user_data.
    This is the central handler for forwarding-based chat ID setting.
    """
    user_id = update.effective_user.id
    message = update.message

    # Ensure there's a message object and it has a forward_origin (i.e., it's a forwarded message).
    if not message or not message.forward_origin:
        # This case should ideally not be reached if the filter is working correctly,
        # but it adds robustness.
        await message.reply_text("Could not detect forwarded chat. Try again.")
        return

    # Extract the chat ID from the forwarded message's origin.
    # It handles different types of forwarded origins (chat, sender_chat, sender_user).
    chat_id = None
    if hasattr(message.forward_origin, "chat") and message.forward_origin.chat:
        chat_id = message.forward_origin.chat.id
    elif hasattr(message.forward_origin, "sender_chat") and message.forward_origin.sender_chat:
        chat_id = message.forward_origin.sender_chat.id
    elif hasattr(message.forward_origin, "sender_user") and message.forward_origin.sender_user:
        chat_id = message.forward_origin.sender_user.id

    if not chat_id:
        await message.reply_text("Could not detect chat ID from the forwarded message. Please ensure it's a valid chat (group, channel, or private chat) and try again.")
        return

    # Check the 'awaiting' flag to determine if the chat_id is for source or destination.
    if context.user_data.get("awaiting") == "source":
        # Store the source_id in Supabase for the current user.
        supabase.table("user_configs").upsert(
            {"user_id": user_id, "source_id": chat_id}
        ).execute()
        await message.reply_text("✅ Source chat set! Now use /setdestination.")
        context.user_data["awaiting"] = None # Clear the awaiting flag.
    elif context.user_data.get("awaiting") == "destination":
        # Store the destination_id in Supabase for the current user.
        supabase.table("user_configs").upsert(
            {"user_id": user_id, "destination_id": chat_id}
        ).execute()
        await message.reply_text("✅ Destination chat set! Your bot is now active.")
        context.user_data["awaiting"] = None # Clear the awaiting flag.
    else:
        # If a forwarded message is received but the bot isn't expecting one for setup.
        await message.reply_text("Use /setsource or /setdestination first to tell me what to do with forwarded messages.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /status command.
    Retrieves and displays the current forwarding configuration (source, destination, mode, keywords)
    for the user from Supabase.
    """
    user_id = update.effective_user.id
    # Fetch the user's configuration from Supabase.
    response = supabase.table("user_configs").select("*").eq("user_id", user_id).execute()
    
    if response.data:
        config = response.data[0] # Get the first (and only) configuration row for the user.
        mode = config.get('mode', 'all') # Get mode, default to 'all' if not set.
        # Format keywords for display: join them with commas or show "None" if empty.
        keywords = ", ".join(config.get('keywords', [])) if config.get('keywords') else "None"
        
        await update.message.reply_text(
            f"Current config:\n"
            f"Source Chat: {config.get('source_id', 'Not set')}\n"
            f"Destination Chat: {config.get('destination_id', 'Not set')}\n"
            f"Forwarding Mode: {mode}\n"
            f"Keywords (if mode is 'keywords'): {keywords}"
        )
    else:
        await update.message.reply_text("No configuration set. Use /setsource, /setdestination, /setmode.")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /reset command.
    Deletes the user's entire configuration from the 'user_configs' table in Supabase.
    """
    user_id = update.effective_user.id
    supabase.table("user_configs").delete().eq("user_id", user_id).execute()
    await update.message.reply_text("Configuration reset. Start fresh with /setsource, /setdestination, /setmode.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /help command.
    Provides a comprehensive usage guide for the bot's commands.
    """
    await update.message.reply_text(
        "📋 Usage Guide:\n"
        "/start - Get started with the bot\n"
        "/setsource - Forward a message from the source chat (where messages will be copied from)\n"
        "/setdestination - Forward a message from the target chat (where messages will be sent to)\n"
        "/setmode - Choose 'all' to forward all messages or 'keywords' to filter by keywords\n"
        "/setkeywords - Set keywords for 'keywords' mode (comma-separated)\n"
        "/status - View your current forwarding configuration\n"
        "/reset - Clear all your configuration and start fresh\n"
        "/help - Show this guide"
    )

def main():
    """
    Main function to initialize and run the Telegram bot.
    It builds the Application, registers all handlers, and starts polling for updates.
    """
    print("Initializing bot application...")
    # Create the Application instance using your bot token.
    app = Application.builder().token(BOT_TOKEN).build()
    print("Adding handlers...")

    # Register Command Handlers: These respond to specific /commands.
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setsource", set_source))
    app.add_handler(CommandHandler("setdestination", set_destination))
    app.add_handler(CommandHandler("setmode", set_mode))
    app.add_handler(CommandHandler("setkeywords", set_keywords))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("help", help_cmd))
    
    # Register Message Handlers: These respond to messages matching specific filters.
    # Order matters for MessageHandlers: More specific filters should generally come before broader ones.
    
    # This handler specifically processes all forwarded messages.
    # It must be placed carefully to ensure it catches forwarded messages before more general text handlers.
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forwarded_message))
    
    # This handler processes text messages that are NOT commands.
    # It's primarily used for capturing keyword input after /setkeywords.
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_keywords_input))
    
    # Register CallbackQueryHandler: This responds to interactions with inline keyboard buttons.
    # The pattern filters for callbacks that start with "set_mode_".
    app.add_handler(CallbackQueryHandler(handle_mode_callback, pattern="^set_mode_"))
    
    print("Bot is running. Waiting for messages...")
    # Start the bot by polling for updates. This method will block and keep the bot running indefinitely.
    app.run_polling()

if __name__ == "__main__":
    main()
