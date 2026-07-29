import os
from telethon import TelegramClient
from dotenv import load_dotenv
from progress_bar import ProgressBar

this_folder = os.path.dirname(os.path.abspath(__file__))
os.chdir(this_folder)
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME")
DOWNLOAD_DIR = "media"

_printer = None
printer = lambda *args, end='\n': (_printer(*args, end=end) if _printer else print(*args, end=end))
label = ''

async def download_message_media(client: TelegramClient, chat_id: int, message_id: int) -> list[str]:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    message = await client.get_messages(chat_id, ids=message_id)
    if message is None:
        raise ValueError("Message not found.")
    if message.media is None:
        return []
    idx = 0
    dirname = os.path.join(DOWNLOAD_DIR, str(chat_id), f"{message_id}_{idx}")
    while os.path.exists(dirname):
        idx += 1
        dirname = os.path.join(DOWNLOAD_DIR, str(chat_id), f"{message_id}_{idx}")
    result = await client.download_media(message, file=dirname)
    if result is None:
        return []
    if isinstance(result, list):
        return result
    return [result]

async def get_messages_from_chat(client: TelegramClient, chat_id: int) -> list:
    messages = await client.get_messages(chat_id, limit=None)
    return messages

async def handle_message(client: TelegramClient, chat_id: int, message_id: int):
    try:
        message_id = int(message_id)
        chat_id = int(chat_id)
        files = await download_message_media(client, chat_id, message_id)
        if files:
            printer("Downloaded:")
            for file in files:
                printer(f" - {file}")
        else:
            printer("No media found.")
    except Exception as e:
        printer(f"Error processing message {message_id} in chat {chat_id}: {e}")

async def handle_chat(client: TelegramClient, chat_id: int):
    chat_id = int(chat_id)
    progress_bar = ProgressBar(width=os.get_terminal_size().columns)
    global _printer
    _printer = progress_bar.write
    messages = await get_messages_from_chat(client, chat_id)
    for i, message in enumerate(messages):
        await handle_message(client, chat_id, message.id)
        progress_bar.update((i + 1) / len(messages), label)

async def handle_all(client: TelegramClient):
    dialogs = await client.get_dialogs()
    async for i, dialog in enumerate(dialogs):
        chat_id = dialog.id
        printer(f"Processing chat: {dialog.name} (ID: {chat_id})")
        label = f'{i+1}/{len(dialogs)}: {dialog.name}'
        await handle_chat(client, chat_id)

async def main():
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        chat_id = input("Chat ID: ")
        if chat_id == "":
            await handle_all(client)
        else:
            message_id = input("Message ID: ")
            if message_id == "":
                global label
                label = f"{chat_id}"
                await handle_chat(client, chat_id)
            else:
                await handle_message(client, chat_id, message_id)
        input("Press Enter to exit...")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
