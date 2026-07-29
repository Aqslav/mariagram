import os
from telethon import TelegramClient
from dotenv import load_dotenv

this_folder = os.path.dirname(os.path.abspath(__file__))
os.chdir(this_folder)
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME")
DOWNLOAD_DIR = "media"


async def download_message_media(client: TelegramClient, chat_id: int, message_id: int):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    message = await client.get_messages(chat_id, ids=message_id)
    if message is None:
        raise ValueError("Message not found.")
    if message.media is None:
        return []
    result = await client.download_media(message, file=DOWNLOAD_DIR)
    if result is None:
        return []
    if isinstance(result, list):
        return result
    return [result]


async def main():
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        chat_id = int(input("Chat ID: "))
        while True:
            message_id = int(input("Message ID: "))
            files = await download_message_media(client, chat_id, message_id)
            if files:
                print("Downloaded:")
                for file in files:
                    print(f" - {file}")
            else:
                print("No media found.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
