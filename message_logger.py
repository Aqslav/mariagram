import asyncio
import json
import os
from datetime import datetime, timezone
from telethon import TelegramClient, events
from tonia import PrettyLogger, Color
from mariagram_lib import *
import asyncio
from dotenv import load_dotenv

this_folder = os.path.dirname(os.path.abspath(__file__))
os.chdir(this_folder)
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME")
STATE_FILE = "logger_state.json"
PRINT_CHANNELS = False

log_db = LogDB()
raw_log_db = RawLogDB()

class MessageLogger:    
    def __init__(self, api_id, api_hash, session_name, state_file=STATE_FILE):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.state_file = state_file
        self.last_message_time = self._load_last_message_time()
        self.on_message = None
        self.my_id = None
        self.print_messages = False
        self.backtrack = True
        self.runtime_check = True
        self.forward_scan = True
        self.priority_chat = None


    def _load_last_message_time(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                data = json.load(f)
            ts = data.get("last_message_time")
            if ts:
                return datetime.fromisoformat(ts)
        return None

    def _save_last_message_time(self, dt):
        self.last_message_time = dt
        with open(self.state_file, "w") as f:
            json.dump({"last_message_time": dt.isoformat()}, f)

    async def message_handler(self, message, new = True):   
        info = await get_info(message)
        if (PRINT_CHANNELS or get_chat_type(message) != "broadcast_channel") and self.print_messages and new:
            print_message(info)
        log_db.log_message(info)
        raw_log_db.log_message(message)
        if self.on_message:
            self.on_message(info, new)

    class DialogItem():
        def __init__(self, dialog, last_seen, count, done):
            self.dialog = dialog
            self.last_seen = last_seen
            self.count = count
            self.done = done

    async def _fill(self, since, reverse=True):
        newest_seen = since
        max_per_dialog = 50
        dialogs = await self.client.get_dialogs()
        priority_dialog = None
        for i, dialog in enumerate(dialogs):
            dialogs[i] = self.DialogItem(dialogs[i], since, 0, False)
            if dialog.id == self.priority_chat:
                priority_dialog = dialogs[i]
        while not all(dialog.done for dialog in dialogs):
            for dialog in dialogs:
                if dialog.dialog.id == self.priority_chat:
                    priority_dialog = dialog
                if self.priority_chat is not None and priority_dialog is not None and dialog.dialog.id != self.priority_chat and not priority_dialog.done:
                    continue
                iterated = False
                async for message in self.client.iter_messages(dialog.dialog.id, offset_date=dialog.last_seen, reverse=reverse):
                    iterated = True
                    try:
                        await self.message_handler(message, new=True)
                        dialog.count += 1
                        if dialog.count >= max_per_dialog:
                            dialog.last_seen = message.date
                            dialog.count = 0
                            break
                    except Exception as e:
                        print(f"Error processing message: {e}")
                        print(f"Message details: {json.dumps(message, default=str, indent=4, ensure_ascii=False)}")
                        raise
                    if message.date > newest_seen:
                        newest_seen = message.date
                if not iterated:
                    dialog.done = True
        return newest_seen

    async def process_dialog(self, dialog, max_per_dialog):
        iterated = False
        if dialog.done:
            return
        async for message in self.client.iter_messages(dialog.dialog.id, offset_date=dialog.last_seen, reverse=False):
            iterated = True
            try:
                await self.message_handler(message, new=False)
                dialog.count += 1
                if dialog.count >= max_per_dialog:
                    dialog.last_seen = message.date
                    dialog.count = 0
                    break
            except Exception as e:
                print(f"Error processing message: {e}")
                print(f"Message details: {json.dumps(message, default=str, indent=4, ensure_ascii=False)}")
                raise
            if message.date < dialog.last_seen:
                dialog.last_seen = message.date
        if not iterated:
            dialog.done = True

    async def _forward_fill(self, max_per_dialog=500):
        oldest_dates = {
            chat_id: datetime.fromisoformat(date)
            for chat_id, date in log_db.get_oldest_dates()
        }
        dialogs = [
            self.DialogItem(
                dialog=dialog,
                last_seen=oldest_dates.get(dialog.id, datetime.now(timezone.utc)),
                count=0,
                done=False,
            )
            for dialog in await self.client.get_dialogs()
        ]

        while True:
            active = [d for d in dialogs if not d.done]
            if not active:
                break
            priority_dialog = None
            for dialog in active:
                if self.priority_chat is not None:
                    if priority_dialog is None or priority_dialog.dialog.id == self.priority_chat:
                        priority_dialogs = [d for d in active if d.dialog.id == self.priority_chat]
                        if priority_dialogs:
                            priority_dialog = priority_dialogs[0]
                        else:
                            priority_dialog = None
                            self.priority_chat = None
                if self.priority_chat is not None and priority_dialog is not None:
                    await self.process_dialog(priority_dialog, max_per_dialog)
                else:
                    await self.process_dialog(dialog, max_per_dialog)

    async def _backfill(self, since):
        if since is None:
            since = datetime.now(timezone.utc)
            self._save_last_message_time(since)
        newest_seen = await self._fill(since, reverse=True)
        self._save_last_message_time(newest_seen)
        PrettyLogger.info(f"Backfill complete. Last message time updated to {newest_seen.isoformat()}")

    async def _live_handler(self, event):
        message = event.message
        try:
            await self.message_handler(message, new=True)
        except Exception as e:
            print(f"Error processing message: {e}")
            print(f"Message details: {json.dumps(message, default=str, indent=4, ensure_ascii=False)}")
            raise
        self._save_last_message_time(message.date)

    async def run(self):
        try:
            await self.client.start()
            me = await self.client.get_me()
            self.my_id = me.id
            time_set = self.last_message_time

            tasks = []
            if self.backtrack:
                tasks.append(asyncio.create_task(self._backfill(since=self.last_message_time)))
            if self.runtime_check:
                self.client.add_event_handler(
                    self._live_handler,
                    events.NewMessage(incoming=True, outgoing=True),
                )
            if self.forward_scan:
                tasks.append(asyncio.create_task(self._forward_fill(max_per_dialog=50)))

            await self.client.run_until_disconnected()
        except KeyboardInterrupt:
            PrettyLogger.info("Shutting down...")


if __name__ == "__main__":
    try:
        logger = MessageLogger(API_ID, API_HASH, SESSION_NAME)
        asyncio.run(logger.run())
    except:
        import traceback
        print("An error occurred:")
        traceback.print_exc()
    finally:
        raw_log_db.close()
        logger.client.disconnect()
