# userbot/main.py

from telethon import TelegramClient, events # Import TelegramClient for userbot operations and events for message handling
from supabase import create_client, Client # Import Supabase client for database interaction
import asyncio # For asynchronous operations like sleep and creating background tasks
import os # For accessing environment variables
import logging # For logging events and debugging purposes
from dotenv import load_dotenv # To load environment variables from .env file

# Set up logging for the userbot.
# Level set to INFO to see important operational messages, DEBUG can be used for more verbosity.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Get a logger instance specific to this module

# Load environment variables from the .env file in the current directory
load_dotenv()
API_ID = int(os.getenv("API_ID")) # Your Telegram API ID (must be an integer)
API_HASH = os.getenv("API_HASH") # Your Telegram API Hash
SUPABASE_URL = os.getenv("SUPABASE_URL") # Supabase project URL
SUPABASE_KEY = os.getenv("SUPABASE_KEY") # Supabase public (anon) key

# Initialize Supabase client
# This client will interact with your Supabase database to fetch forwarding configurations.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Telethon client.
# "userbot" is the session name; Telethon will create/use 'userbot.session' file for authentication.
client = TelegramClient("userbot", api_id=API_ID, api_hash=API_HASH)

# Global variables to store the fetched configuration for the current userbot instance.
# These variables will be updated periodically by the `fetch_config` background task.
current_user_id = None # Stores the ID of the Telegram user account this userbot is logged in as.
current_source_id = None # Stores the chat ID from which messages should be forwarded.
current_destination_id = None # Stores the chat ID to which messages should be forwarded.
current_mode = "all" # Default forwarding mode: "all" (forward everything) or "keywords" (forward filtered by keywords).
current_keywords = [] # List of keywords to filter by if current_mode is "keywords".

async def fetch_config():
    """
    Periodically fetches the forwarding configuration (source, destination, mode, keywords)
    for the current userbot from Supabase.
    This function runs as a continuous background task to keep the userbot's configuration up-to-date.
    """
    global current_user_id, current_source_id, current_destination_id, current_mode, current_keywords
    
    while True: # Loop indefinitely to periodically fetch configuration
        try:
            if current_user_id: # Only attempt to fetch config if the userbot's own ID is known (after login).
                # Query the 'user_configs' table for the current user's settings.
                # 'eq("user_id", current_user_id)' ensures we fetch only the relevant configuration.
                response = supabase.table("user_configs").select("*").eq("user_id", current_user_id).execute()
                
                if response.data: # If configuration data is found for this user
                    config = response.data[0] # Get the first (and typically only) configuration row.
                    
                    # Extract new configuration values, providing default values if keys are missing.
                    new_source_id = config.get("source_id")
                    new_destination_id = config.get("destination_id")
                    new_mode = str(config.get("mode", "all").lower()) # Get mode, default to 'all', convert to lowercase.
                     # Get keywords; if `None` or not a list, default to empty list.
                    # Then filter out any `None` values within the list before converting to lowercase.
                    raw_keywords = config.get("keywords")
                    if raw_keywords is None or not isinstance(raw_keywords, list):
                        new_keywords = []
                    else:
                        new_keywords = [str(k).lower() for k in raw_keywords if k is not None]

                    # Check if any configuration value has changed before updating and logging.
                    # This prevents spamming logs if the config hasn't been modified in Supabase.
                    if (current_source_id != new_source_id or
                        current_destination_id != new_destination_id or
                        current_mode != new_mode or
                        set(current_keywords) != set(new_keywords)): # Use sets for keyword comparison to ignore order.

                        # Update global variables with the newly fetched configuration.
                        current_source_id = new_source_id
                        current_destination_id = new_destination_id
                        current_mode = new_mode
                        current_keywords = new_keywords
                        
                        # Log the updated configuration details.
                        logger.info(f"Configuration loaded/updated for User ID {current_user_id}:")
                        logger.info(f"  Source Chat: {current_source_id}")
                        logger.info(f"  Destination Chat: {current_destination_id}")
                        logger.info(f"  Mode: {current_mode}")
                        if current_mode == "keywords": # Only log keywords if in "keywords" mode.
                            logger.info(f"  Keywords: {current_keywords}")
                    
                    # Verify userbot's access to source and destination chats.
                    # This is crucial for successful forwarding and identifies permission issues early.
                    try:
                        if current_source_id:
                            await client.get_entity(current_source_id)
                        if current_destination_id:
                            await client.get_entity(current_destination_id)
                    except Exception as e:
                        # Log a critical error if chats are inaccessible.
                        logger.error(f"Cannot access one or both configured chats: {e}.")
                        logger.error("Ensure the userbot is a member of both the source and destination chats.")
                        logger.error("If the chats are private, you must first join them manually with the userbot's account.")
                        logger.error("Contact @dahormes for help.")
                else:
                    # If no configuration is found for the user in Supabase.
                    # Reset local variables if a previous config was loaded but is now missing.
                    if current_source_id or current_destination_id or current_mode != "all" or current_keywords:
                        logger.warning(f"Configuration not found for User ID {current_user_id} in database. Waiting for setup...")
                        current_source_id, current_destination_id, current_mode, current_keywords = None, None, "all", []
        except Exception as e:
            # Catch and log any errors that occur during the configuration fetching process.
            logger.error(f"Error fetching config for User ID {current_user_id}: {e}. Contact @DaHormes for help.")
        
        await asyncio.sleep(60) # Wait for 60 seconds before fetching the configuration again.

@client.on(events.NewMessage)
async def message_handler(event):
    """
    Handles all incoming messages received by the userbot.
    This function implements the core forwarding logic based on the fetched configuration.
    """
    # Ensure a valid source and destination configuration is loaded before attempting to process messages.
    if not (current_source_id and current_destination_id):
        # logger.debug("Ignoring message: Configuration not fully set.") # Uncomment for more verbose debugging.
        return # Exit if configuration is incomplete.

    # 1. Check if the incoming message is from the configured source chat.
    if event.chat_id != current_source_id:
        # logger.debug(f"Ignoring message from non-source chat: {event.chat_id}") # Uncomment for more verbose debugging.
        return # Exit if the message is not from the source chat.
    
    logger.info(f"Message received from source chat: {event.chat_id} (Type: {event.chat.__class__.__name__})")

    # 2. Apply forwarding mode logic based on `current_mode`.
    should_forward = False # Initialize flag to determine if the message should be forwarded.
    if current_mode == "all":
        # If mode is 'all', every message from the source chat should be forwarded.
        should_forward = True
        logger.info(f"Mode 'all': Message from {event.chat_id} will be forwarded.")
    elif current_mode == "keywords":
        # If mode is 'keywords', check if the message text contains any of the defined keywords.
        if event.text: # Ensure the message has text content to perform keyword matching.
            message_text_lower = event.text.lower() # Convert message text to lowercase for case-insensitive matching.
            
            # Check if any keyword from `current_keywords` is present in the message text.
            if any(keyword in message_text_lower for keyword in current_keywords):
                should_forward = True # Set flag to True if a keyword is found.
                logger.info(f"Mode 'keywords': Found keyword in message from {event.chat_id}. Will be forwarded.")
            else:
                logger.info(f"Mode 'keywords': No keyword found in message from {event.chat_id}. Ignoring.")
        else:
            # If in 'keywords' mode but the message has no text (e.g., photo, sticker, voice message), ignore it.
            logger.info(f"Mode 'keywords': Message from {event.chat_id} has no text content. Ignoring.")
    else:
        # Handle cases where an unknown or invalid mode is specified in the database.
        logger.warning(f"Unknown mode '{current_mode}' specified in database for user {current_user_id}. Message will not be forwarded.")
        return # Exit if the mode is unrecognized.

    # 3. Forward the message if `should_forward` flag is True.
    if should_forward:
        try:
            # Use event.forward_to() for convenient and efficient forwarding in Telethon.
            await event.forward_to(current_destination_id)
            logger.info(f"Successfully forwarded message {event.id} from {event.chat_id} to {current_destination_id}.")
        except Exception as e:
            # Log any errors that occur during the forwarding process (e.g., permission issues).
            logger.error(f"Failed to forward message {event.id} from {event.chat_id} to {current_destination_id}: {e}")
            logger.error("Please ensure the userbot has permission to send messages to the destination chat.")

async def main():
    """
    Main function to start the Telethon userbot.
    It handles userbot login, retrieves its own ID, starts the config fetching task,
    and keeps the bot running until disconnected.
    """
    global current_user_id # Declare global to modify the current_user_id variable.
    try:
        logger.info("Attempting to connect to Telegram...")
        await client.start() # Connect and log in as the userbot (creates/uses userbot.session).
        
        user = await client.get_me() # Get details of the logged-in user (the userbot itself).
        current_user_id = user.id # Store the userbot's own Telegram ID globally.
        logger.info(f"Userbot is running for user: {user.first_name} (ID: {current_user_id})")
        
        # Start the background task for fetching configuration from Supabase.
        # This task will run concurrently with the message handling.
        client.loop.create_task(fetch_config())
        
        logger.info("Userbot started. Listening for messages...")
        # Keep the client running indefinitely until it's explicitly disconnected (e.g., Ctrl+C).
        await client.run_until_disconnected() 
    except Exception as e:
        # Log critical errors if the userbot fails to log in.
        logger.critical(f"Login failed: {e}. Please check your API_ID and API_HASH in the .env file.")
        logger.critical("Make sure they are correct and you haven't revoked your API access.")
        logger.critical("Contact @DaHormes for help if the issue persists.")

if __name__ == "__main__":
    # Ensure the asyncio event loop is run properly for the Telethon client.
    # The 'with client:' block ensures proper session saving and cleanup when the script exits.
    with client:
        client.loop.run_until_complete(main())
    logger.info("Userbot stopped.") # This message will appear when the bot is gracefully stopped.
    