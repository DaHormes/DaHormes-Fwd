# userbot/main.py

from telethon import TelegramClient, events
from supabase import create_client, Client
import asyncio
import os
import logging
from dotenv import load_dotenv
import sys # sys import added at the top

#To pause Service on railway
if os.getenv("PAUSE") == "true":
    print("🚧 Application is paused. Exiting now.")
    sys.exit(0)


# Set up logging for the userbot.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Telethon client.
client = TelegramClient("userbot", api_id=API_ID, api_hash=API_HASH)

# Global variables to store the fetched configuration for the current userbot instance.
current_user_id = None
current_source_id = None
current_destination_id = None
current_mode = "all"
current_keywords = []

async def fetch_config():
    """
    Periodically fetches the forwarding configuration (source, destination, mode, keywords)
    for the current userbot from Supabase.
    This function runs as a continuous background task to keep the userbot's configuration up-to-date.
    """
    global current_user_id, current_source_id, current_destination_id, current_mode, current_keywords
    
    while True:
        try:
            if current_user_id:
                response = supabase.table("user_configs").select("*").eq("user_id", current_user_id).execute()
                
                if response.data:
                    config = response.data[0]
                    
                    new_source_id = config.get("source_id")
                    new_destination_id = config.get("destination_id")
                    new_mode = str(config.get("mode", "all")).lower()
                    
                    # Robustly get keywords: ensure it's a list and contains no None values
                    raw_keywords = config.get("keywords")
                    if raw_keywords is None or not isinstance(raw_keywords, list):
                        new_keywords = []
                    else:
                        new_keywords = [str(k).lower() for k in raw_keywords if k is not None]

                    # Use sets for keyword comparison to ignore order, ensuring they are lists first
                    current_keywords_set = set(current_keywords if current_keywords is not None else [])
                    new_keywords_set = set(new_keywords)

                    # Check if any configuration value has changed before updating and logging.
                    if (current_source_id != new_source_id or
                        current_destination_id != new_destination_id or
                        current_mode != new_mode or
                        current_keywords_set != new_keywords_set):

                        current_source_id = new_source_id
                        current_destination_id = new_destination_id
                        current_mode = new_mode
                        current_keywords = new_keywords

                        logger.info(f"Configuration loaded/updated for User ID {current_user_id}:")
                        logger.info(f" Source Chat: {current_source_id}")
                        logger.info(f" Destination Chat: {current_destination_id}")
                        logger.info(f" Mode: {current_mode}")
                        if current_mode == "keywords":
                            logger.info(f" Keywords: {current_keywords}")

                        # Verify userbot's access to the source and destination chats
                        try:
                            if new_source_id:
                                await client.get_entity(new_source_id)
                                logger.info(f"Access to Source Chat {new_source_id} verified.")
                            if new_destination_id:
                                await client.get_entity(new_destination_id)
                                logger.info(f"Access to Destination Chat {new_destination_id} verified.")
                        except Exception as e:
                            logger.error(f"Cannot access chats (Source: {new_source_id}, Destination: {new_destination_id}): {e}. Ensure userbot is member of both chats and IDs are correct.")
                else:
                    # If response.data is empty, means no config in DB for this user.
                    # Reset globals to default states.
                    if current_source_id is not None or current_destination_id is not None:
                        logger.warning("Configuration not found in database. Resetting current config to awaiting setup...")
                        current_source_id = None
                        current_destination_id = None
                        current_mode = "all"
                        current_keywords = []
            else:
                logger.info("Userbot ID not yet available, skipping config fetch for now...")

        except Exception as e:
            # Added exc_info=True to print the full traceback
            logger.error(f"Error fetching config for User ID {current_user_id}: {e}. Contact @DaHormes for help.", exc_info=True)
        await asyncio.sleep(60)

@client.on(events.NewMessage)
async def handler(event):
    # Ensure config is loaded and the message is from the source chat
    if current_source_id and current_destination_id and event.chat_id == current_source_id:
        try:
            message_text = event.message.message if event.message.message else ""
            
            # Check forwarding mode
            if current_mode == "all":
                await event.forward_to(current_destination_id)
                logger.info(f"Forwarded message from {current_source_id} to {current_destination_id} (Mode: All)")
            elif current_mode == "keywords" and current_keywords:
                # Check if any keyword is present in the message text (case-insensitive)
                if any(keyword in message_text.lower() for keyword in current_keywords):
                    await event.forward_to(current_destination_id)
                    logger.info(f"Forwarded message from {current_source_id} to {current_destination_id} (Mode: Keywords - Match found)")
                else:
                    logger.info(f"Skipped message from {current_source_id} (Mode: Keywords - No match)")
            elif current_mode == "keywords" and not current_keywords:
                logger.warning(f"Keywords mode active for {current_user_id} but no keywords defined. Skipping forwarding.")
                
        except Exception as e:
            logger.error(f"Error forwarding message: {e}. Contact @DaHormes for help.")

async def main():
    """
    Main function to run the Telethon userbot.
    It logs in, fetches the user's ID, starts the config fetching task, and keeps the bot running.
    """
    global current_user_id
    try:
        logger.info("Attempting to connect to Telegram...")
        await client.start()
        
        user = await client.get_me()
        current_user_id = user.id
        logger.info(f"Userbot is running for user: {user.first_name} (ID: {current_user_id})")
        
        client.loop.create_task(fetch_config())
        
        logger.info("Userbot started. Listening for messages...")
        await client.run_until_disconnected()
    except Exception as e:
        logger.critical(f"Login failed: {e}. Please check your API_ID and API_HASH in the .env file.")
        logger.critical("Make sure they are correct and you haven't revoked your API access.")
        logger.critical("Contact @DaHormes for help if the issue persists.")

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
    logger.info("Userbot stopped.")