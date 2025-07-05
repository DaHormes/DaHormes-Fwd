from telethon import TelegramClient, events
from supabase import create_client, Client
import asyncio
import os
import logging
from dotenv import load_dotenv

#To pause Service on railway
if (process.env.PAUSE === "true") {
  console.log("App is paused.");
  process.exit(0);
}

# Load environment variables
load_dotenv()
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize client
client = TelegramClient("userbot", api_id=API_ID, api_hash=API_HASH)
user_id = None
source_id = None
destination_id = None

async def fetch_config():
    global source_id, destination_id
    while True:
        try:
            if user_id:
                response = supabase.table("user_configs").select("*").eq("user_id", user_id).execute()
                if response.data:
                    source_id = response.data[0]["source_id"]
                    destination_id = response.data[0]["destination_id"]
                    # Verify chat access
                    try:
                        await client.get_entity(source_id)
                        await client.get_entity(destination_id)
                    except Exception as e:
                        logging.error(f"Cannot access chat: {e}. Ensure you are a member of both chats. Contact @YourUsername.")
        except Exception as e:
            logging.error(f"Error fetching config: {e}. Contact @DaHormes for help.")
        await asyncio.sleep(60)

@client.on(events.NewMessage)
async def handler(event):
    try:
        if source_id and destination_id and event.chat_id == source_id:
            await event.forward_to(destination_id)
    except Exception as e:
        logging.error(f"Error forwarding: {e}. Contact @DaHormes for help.")

async def main():
    global user_id
    try:
        await client.start()
        user = await client.get_me()
        user_id = user.id
        logging.info("Userbot is running...")
        client.loop.create_task(fetch_config())
        await client.run_until_disconnected()
    except Exception as e:
        logging.error(f"Login failed: {e}. Check API_ID and API_HASH. Contact @DaHormes.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with client:
        client.loop.run_until_complete(main())
