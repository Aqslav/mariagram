import os
from tonia import PrettyLogger, Color
import sqlite3
try:
    from pymongo import MongoClient
    use_mongo = True
except:
    use_mongo = False
    PrettyLogger.warning("pymongo is not installed. Raw message logging to MongoDB will be disabled.")
from subprocess import DEVNULL, Popen
import os
import time
import threading

def get_message_text(message):
    parts = []
    text = message.message or message.text
    if text:
        parts.append(text)
    if message.photo:
        parts.append("[photo]")
    if message.video and not message.video_note:
        parts.append("[video]")
    if message.video_note:
        parts.append("[video circle]")
    if message.voice:
        parts.append("[voice]")
    if message.audio:
        parts.append("[audio]")
    if message.gif:
        parts.append("[gif]")
    if message.sticker:
        parts.append("[sticker]")
    if message.document and not any([
        message.gif, message.sticker, message.voice,
        message.audio, message.video, message.video_note
    ]):
        parts.append("[file]")
    if message.contact:
        parts.append("[contact]")
    if message.geo:
        parts.append("[location]")
    if message.venue:
        parts.append("[venue]")
    if message.poll:
        parts.append("[poll]")
    if message.game:
        parts.append("[game]")
    if message.web_preview:
        parts.append("[web preview]")
    return " ".join(parts) if parts else "[phone call]"

async def get_info(message):
    info = {}
    info["chat_id"] = str(message.chat_id) if message.chat_id is not None else ""

    chat = await message.get_chat()
    if chat:
        first = getattr(chat, 'first_name', None) or ""
        last = getattr(chat, 'last_name', None) or ""
        title = getattr(chat, 'title', None) or ""
        info["chat_name"] = f"{first}{(' ' + last if last else '')}".strip() if first else title
        info["chat_number"] = f"+{chat.phone}" if getattr(chat, 'phone', None) else ""
        info["chat_username"] = f"@{chat.username}" if getattr(chat, 'username', None) else ""
    else:
        info["chat_name"] = ""
        info["chat_number"] = ""
        info["chat_username"] = ""

    sender = await message.get_sender()
    if sender:
        first = getattr(sender, 'first_name', None) or ""
        last = getattr(sender, 'last_name', None) or ""
        title = getattr(sender, 'title', None) or ""
        info["sender_name"] = f"{first}{(' ' + last if last else '')}".strip() if first else title
        info["sender_username"] = f"@{sender.username}" if getattr(sender, 'username', None) else ""
        info["sender_number"] = f"+{sender.phone}" if getattr(sender, 'phone', None) else ""
        info["sender_id"] = str(message.sender_id) if message.sender_id is not None else ""
    else:
        info["sender_name"] = ""
        info["sender_username"] = ""
        info["sender_number"] = ""
        info["sender_id"] = ""

    info["chat_type"] = get_chat_type(message)
    info["message_id"] = str(message.id) if message.id is not None else ""
    info["time"] = message.date if hasattr(message, 'date') and message.date else None
    info["time_in_zone"] = info["time"].astimezone() if info["time"] else None
    info["time_formatted"] = info["time_in_zone"].strftime("%Y-%m-%d %H:%M:%S") if info["time_in_zone"] else ""
    info["message_text"] = get_message_text(message)
    return info

last_chat_id = None

def print_message(info):
    global last_chat_id
    if last_chat_id != info["chat_id"]:
        last_chat_id = info["chat_id"]
        print("\n" + "╠" + "═" * (os.get_terminal_size().columns - 2) + "╣")
        PrettyLogger.write(f"{info['chat_name']} ({info['chat_username']}, {info['chat_number']}) {info['chat_id']}", "[CHAT]", Color.Foreground.MAGENTA)
    print(f"{info['time_formatted']} {info['sender_name']} ({info['sender_username']}, {info['sender_number']}): {info['message_text']}")

class LogDB:
    def __init__(self, log_file="data/message_log.db"):
        self.log_file = log_file
        self.lock = threading.Lock()

    def _initialize_db(self):
        if not os.path.exists(os.path.dirname(self.log_file)):
            os.makedirs(os.path.dirname(self.log_file))
        conn = sqlite3.connect(
            self.log_file,
            check_same_thread=False
        )        
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                name TEXT,
                number TEXT,
                username TEXT,
                type TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS senders (
                id TEXT PRIMARY KEY,
                name TEXT,
                username TEXT,
                number TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT,
                chat_id TEXT,
                sender_id TEXT,
                time TIMESTAMP,
                time_in_zone TIMESTAMP,
                time_formatted TEXT,
                text TEXT,
                PRIMARY KEY (id, chat_id),
                FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                FOREIGN KEY (sender_id) REFERENCES senders(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        return conn, cursor
    
    @staticmethod
    def _ensure_chat_exists(cursor, info):
        cursor.execute('''
            INSERT OR IGNORE INTO chats (id, name, number, username, type)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            info["chat_id"],
            info.get("chat_name"),
            info.get("chat_number"),
            info.get("chat_username"),
            info.get("chat_type")
        ))
        cursor.execute('''
            UPDATE chats
            SET name = COALESCE(?, name),
                number = COALESCE(?, number),
                username = COALESCE(?, username),
                type = COALESCE(?, type)
            WHERE id = ?
        ''',(
            info.get("chat_name"),
            info.get("chat_number"),
            info.get("chat_username"),
            info.get("chat_type"),
            info["chat_id"]
        ))

    @staticmethod
    def _ensure_sender_exists(cursor, info):
        cursor.execute('''
            INSERT OR IGNORE INTO senders (id, name, username, number)
            VALUES (?, ?, ?, ?)
        ''', (
            info["sender_id"],
            info.get("sender_name"),
            info.get("sender_username"),
            info.get("sender_number")
        ))
        cursor.execute('''
            UPDATE senders
            SET name = COALESCE(?, name),
                username = COALESCE(?, username),
                number = COALESCE(?, number)
            WHERE id = ?
        ''',(
            info.get("sender_name"),
            info.get("sender_username"),
            info.get("sender_number"),
            info["sender_id"]
        ))

    @staticmethod
    def _insert_message(cursor, info):
        cursor.execute('''
            INSERT OR IGNORE INTO messages (id, chat_id, sender_id, time, time_in_zone, time_formatted, text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            info["message_id"],
            info["chat_id"],
            info["sender_id"],
            info.get("time"),
            info.get("time_in_zone"),
            info.get("time_formatted"),
            info.get("message_text")
        ))
    @staticmethod
    def _atomic_copy(log_file: str, backup_file: str, tmp_file: str):
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
        src = sqlite3.connect(f"file:{log_file}?mode=ro", uri=True)
        dst = sqlite3.connect(tmp_file)
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
            src.close()
        os.replace(tmp_file, backup_file)

    def log_message(self, info):
        with self.lock:
            conn, cursor = self._initialize_db()
            LogDB._ensure_chat_exists(cursor, info)
            LogDB._ensure_sender_exists(cursor, info)
            LogDB._insert_message(cursor, info)
            conn.commit()
            LogDB._atomic_copy(self.log_file, self.log_file.replace(".db", "_backup.db"), self.log_file.replace(".db", "_tmp.db"))
            conn.close()

    def get_oldest_dates(self):
        with self.lock:
            conn, cursor = self._initialize_db()
            cursor.execute('''
                SELECT chat_id, MIN(time) FROM messages
                GROUP BY chat_id
            ''')
            result = cursor.fetchall()
            conn.close()
        return result

    def get_messages(self, chat_id=None, sender_id=None):
        with self.lock:
            conn, cursor = self._initialize_db()
            query = "SELECT * FROM messages"
            params = []

            if chat_id is not None and sender_id is not None:
                query += " WHERE chat_id = ? AND sender_id = ?"
                params.extend([chat_id, sender_id])
            elif chat_id is not None:
                query += " WHERE chat_id = ?"
                params.append(chat_id)
            elif sender_id is not None:
                query += " WHERE sender_id = ?"
                params.append(sender_id)

            query += " ORDER BY time ASC"
            cursor.execute(query, params)
            messages = cursor.fetchall()

            if chat_id is not None:
                cursor.execute(
                    "SELECT id, name, number, username, type FROM chats WHERE id = ?",
                    (chat_id,),
                )
            else:
                cursor.execute(
                    "SELECT id, name, number, username, type FROM chats"
                )

            chats = {
                row[0]: {
                    "chat_name": row[1],
                    "chat_number": row[2],
                    "chat_username": row[3],
                    "chat_type": row[4],
                    "messages": [],
                }
                for row in cursor.fetchall()
            }

            if sender_id is not None:
                cursor.execute(
                    "SELECT id, name, username, number FROM senders WHERE id = ?",
                    (sender_id,),
                )
            else:
                cursor.execute(
                    "SELECT id, name, username, number FROM senders"
                )

            senders = {
                row[0]: {
                    "name": row[1],
                    "username": row[2],
                    "number": row[3],
                }
                for row in cursor.fetchall()
            }

            for msg in messages:
                (
                    message_id,
                    msg_chat_id,
                    msg_sender_id,
                    time,
                    time_in_zone,
                    time_formatted,
                    text,
                ) = msg
                sender = senders[msg_sender_id]
                chats[msg_chat_id]["messages"].append(
                    {
                        "time": time,
                        "time_in_zone": time_in_zone,
                        "time_formatted": time_formatted,
                        "sender_name": sender["name"],
                        "sender_username": sender["username"],
                        "sender_number": sender["number"],
                        "sender_id": msg_sender_id,
                        "message_text": text,
                        "message_id": message_id,
                    }
                )
            conn.close()
        return {str(k): v for k, v in chats.items()}

class MongoServer:
    def __init__(self, mongod_path=r"D:\MongoDB\bin\mongod.exe", db_path=r"D:\MongoDB\data\db"):
        self.mongod_path = mongod_path
        self.db_path = db_path
        self.process = None

    def start(self):
        os.makedirs(self.db_path, exist_ok=True)
        self.process = Popen(
            [
                self.mongod_path,
                "--dbpath",
                self.db_path
            ],
            stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL
        )
        time.sleep(2)

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            self.process.wait()

class RawLogDB:
    def __init__(self, url = "mongodb://localhost:27017/"):
        self.url = url
        global use_mongo
        if use_mongo:
            try:
                self.mongo_server = MongoServer()
                self.mongo_server.start()
                self.client = MongoClient(self.url)
                self.db = self.client["raw_message_log"]
                self.collection = self.db["messages"]
            except Exception as e:
                PrettyLogger.error(f"Failed to connect to MongoDB: {e}")
                self.client = None
                self.db = None
                self.collection = None
                self.mongo_server.stop()
                use_mongo = False
        else:
            self.client = None
            self.db = None
            self.collection = None
            self.mongo_server = None

    def check_if_up(self):
        if self.mongo_server and self.mongo_server.process:
            if self.mongo_server.process.poll() is not None:
                PrettyLogger.error("MongoDB server stopped unexpectedly.")
                global use_mongo
                use_mongo = False
                self.collection = None
                return False
            else:
                return True
        else:
            PrettyLogger.error("MongoDB server is not running.")
            return False
            
    def log_message(self, message):
        if not use_mongo:
            return
        self.check_if_up()
        dict_msg = message.to_dict()
        dict_msg["date"] = str(dict_msg.get("date", ""))
        if self.collection.find_one({"id": dict_msg.get("id")}):
            return
        self.collection.insert_one(dict_msg)

    def get_messages(self, chat_id=None):
        if not use_mongo:
            return list()
        self.check_if_up()
        if chat_id is not None:
            return list(self.collection.find({"chat_id": chat_id}))
        else:
            return list(self.collection.find())

    def get_message(self, message_id):
        if not use_mongo:
            return list()
        self.check_if_up()
        return self.collection.find_one({"id": int(message_id)})

    def close(self):
        self.check_if_up()
        if self.client:
            self.client.close()
        if self.mongo_server:
            self.mongo_server.stop()

def get_chat_type(message):
    if message.is_private:
        return "private"
    elif message.is_group:
        return "group"
    elif message.is_channel:
        return "broadcast_channel" if message.chat.broadcast else "supergroup"
    return "unknown"
import os
from tonia import PrettyLogger, Color
import sqlite3
try:
    from pymongo import MongoClient
    use_mongo = True
except:
    use_mongo = False
    PrettyLogger.warning("pymongo is not installed. Raw message logging to MongoDB will be disabled.")
from subprocess import DEVNULL, Popen
import os
import time
import threading

def get_message_text(message):
    parts = []
    text = message.message or message.text
    if text:
        parts.append(text)
    if message.photo:
        parts.append("[photo]")
    if message.video and not message.video_note:
        parts.append("[video]")
    if message.video_note:
        parts.append("[video circle]")
    if message.voice:
        parts.append("[voice]")
    if message.audio:
        parts.append("[audio]")
    if message.gif:
        parts.append("[gif]")
    if message.sticker:
        parts.append("[sticker]")
    if message.document and not any([
        message.gif, message.sticker, message.voice,
        message.audio, message.video, message.video_note
    ]):
        parts.append("[file]")
    if message.contact:
        parts.append("[contact]")
    if message.geo:
        parts.append("[location]")
    if message.venue:
        parts.append("[venue]")
    if message.poll:
        parts.append("[poll]")
    if message.game:
        parts.append("[game]")
    if message.web_preview:
        parts.append("[web preview]")
    return " ".join(parts) if parts else "[phone call]"

async def get_info(message):
    info = {}
    info["chat_id"] = str(message.chat_id) if message.chat_id is not None else ""

    chat = await message.get_chat()
    if chat:
        first = getattr(chat, 'first_name', None) or ""
        last = getattr(chat, 'last_name', None) or ""
        title = getattr(chat, 'title', None) or ""
        info["chat_name"] = f"{first}{(' ' + last if last else '')}".strip() if first else title
        info["chat_number"] = f"+{chat.phone}" if getattr(chat, 'phone', None) else ""
        info["chat_username"] = f"@{chat.username}" if getattr(chat, 'username', None) else ""
    else:
        info["chat_name"] = ""
        info["chat_number"] = ""
        info["chat_username"] = ""

    sender = await message.get_sender()
    if sender:
        first = getattr(sender, 'first_name', None) or ""
        last = getattr(sender, 'last_name', None) or ""
        title = getattr(sender, 'title', None) or ""
        info["sender_name"] = f"{first}{(' ' + last if last else '')}".strip() if first else title
        info["sender_username"] = f"@{sender.username}" if getattr(sender, 'username', None) else ""
        info["sender_number"] = f"+{sender.phone}" if getattr(sender, 'phone', None) else ""
        info["sender_id"] = str(message.sender_id) if message.sender_id is not None else ""
    else:
        info["sender_name"] = ""
        info["sender_username"] = ""
        info["sender_number"] = ""
        info["sender_id"] = ""

    info["chat_type"] = get_chat_type(message)
    info["message_id"] = str(message.id) if message.id is not None else ""
    info["time"] = message.date if hasattr(message, 'date') and message.date else None
    info["time_in_zone"] = info["time"].astimezone() if info["time"] else None
    info["time_formatted"] = info["time_in_zone"].strftime("%Y-%m-%d %H:%M:%S") if info["time_in_zone"] else ""
    info["message_text"] = get_message_text(message)
    return info

last_chat_id = None

def print_message(info):
    global last_chat_id
    if last_chat_id != info["chat_id"]:
        last_chat_id = info["chat_id"]
        print("\n" + "╠" + "═" * (os.get_terminal_size().columns - 2) + "╣")
        PrettyLogger.write(f"{info['chat_name']} ({info['chat_username']}, {info['chat_number']}) {info['chat_id']}", "[CHAT]", Color.Foreground.MAGENTA)
    print(f"{info['time_formatted']} {info['sender_name']} ({info['sender_username']}, {info['sender_number']}): {info['message_text']}")

class LogDB:
    def __init__(self, log_file="data/message_log.db"):
        self.log_file = log_file
        self.lock = threading.Lock()

    def _initialize_db(self):
        if not os.path.exists(os.path.dirname(self.log_file)):
            os.makedirs(os.path.dirname(self.log_file))
        conn = sqlite3.connect(
            self.log_file,
            check_same_thread=False
        )        
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                name TEXT,
                number TEXT,
                username TEXT,
                type TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS senders (
                id TEXT PRIMARY KEY,
                name TEXT,
                username TEXT,
                number TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT,
                chat_id TEXT,
                sender_id TEXT,
                time TIMESTAMP,
                time_in_zone TIMESTAMP,
                time_formatted TEXT,
                text TEXT,
                PRIMARY KEY (id, chat_id),
                FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
                FOREIGN KEY (sender_id) REFERENCES senders(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()
        return conn, cursor
    
    @staticmethod
    def _ensure_chat_exists(cursor, info):
        cursor.execute('''
            INSERT OR IGNORE INTO chats (id, name, number, username, type)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            info["chat_id"],
            info.get("chat_name"),
            info.get("chat_number"),
            info.get("chat_username"),
            info.get("chat_type")
        ))
        cursor.execute('''
            UPDATE chats
            SET name = COALESCE(?, name),
                number = COALESCE(?, number),
                username = COALESCE(?, username),
                type = COALESCE(?, type)
            WHERE id = ?
        ''',(
            info.get("chat_name"),
            info.get("chat_number"),
            info.get("chat_username"),
            info.get("chat_type"),
            info["chat_id"]
        ))

    @staticmethod
    def _ensure_sender_exists(cursor, info):
        cursor.execute('''
            INSERT OR IGNORE INTO senders (id, name, username, number)
            VALUES (?, ?, ?, ?)
        ''', (
            info["sender_id"],
            info.get("sender_name"),
            info.get("sender_username"),
            info.get("sender_number")
        ))
        cursor.execute('''
            UPDATE senders
            SET name = COALESCE(?, name),
                username = COALESCE(?, username),
                number = COALESCE(?, number)
            WHERE id = ?
        ''',(
            info.get("sender_name"),
            info.get("sender_username"),
            info.get("sender_number"),
            info["sender_id"]
        ))

    @staticmethod
    def _insert_message(cursor, info):
        cursor.execute('''
            INSERT OR IGNORE INTO messages (id, chat_id, sender_id, time, time_in_zone, time_formatted, text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            info["message_id"],
            info["chat_id"],
            info["sender_id"],
            info.get("time"),
            info.get("time_in_zone"),
            info.get("time_formatted"),
            info.get("message_text")
        ))

    def log_message(self, info):
        with self.lock:
            conn, cursor = self._initialize_db()
            LogDB._ensure_chat_exists(cursor, info)
            LogDB._ensure_sender_exists(cursor, info)
            LogDB._insert_message(cursor, info)
            conn.commit()
            conn.close()

    def get_oldest_dates(self):
        with self.lock:
            conn, cursor = self._initialize_db()
            cursor.execute('''
                SELECT chat_id, MIN(time) FROM messages
                GROUP BY chat_id
            ''')
            result = cursor.fetchall()
            conn.close()
        return result

    def get_messages(self, chat_id=None, sender_id=None):
        with self.lock:
            conn, cursor = self._initialize_db()
            query = "SELECT * FROM messages"
            params = []

            if chat_id is not None and sender_id is not None:
                query += " WHERE chat_id = ? AND sender_id = ?"
                params.extend([chat_id, sender_id])
            elif chat_id is not None:
                query += " WHERE chat_id = ?"
                params.append(chat_id)
            elif sender_id is not None:
                query += " WHERE sender_id = ?"
                params.append(sender_id)

            query += " ORDER BY time ASC"
            cursor.execute(query, params)
            messages = cursor.fetchall()

            if chat_id is not None:
                cursor.execute(
                    "SELECT id, name, number, username, type FROM chats WHERE id = ?",
                    (chat_id,),
                )
            else:
                cursor.execute(
                    "SELECT id, name, number, username, type FROM chats"
                )

            chats = {
                row[0]: {
                    "chat_name": row[1],
                    "chat_number": row[2],
                    "chat_username": row[3],
                    "chat_type": row[4],
                    "messages": [],
                }
                for row in cursor.fetchall()
            }

            if sender_id is not None:
                cursor.execute(
                    "SELECT id, name, username, number FROM senders WHERE id = ?",
                    (sender_id,),
                )
            else:
                cursor.execute(
                    "SELECT id, name, username, number FROM senders"
                )

            senders = {
                row[0]: {
                    "name": row[1],
                    "username": row[2],
                    "number": row[3],
                }
                for row in cursor.fetchall()
            }

            for msg in messages:
                (
                    message_id,
                    msg_chat_id,
                    msg_sender_id,
                    time,
                    time_in_zone,
                    time_formatted,
                    text,
                ) = msg
                sender = senders[msg_sender_id]
                chats[msg_chat_id]["messages"].append(
                    {
                        "time": time,
                        "time_in_zone": time_in_zone,
                        "time_formatted": time_formatted,
                        "sender_name": sender["name"],
                        "sender_username": sender["username"],
                        "sender_number": sender["number"],
                        "sender_id": msg_sender_id,
                        "message_text": text,
                        "message_id": message_id,
                    }
                )
            conn.close()
        return {str(k): v for k, v in chats.items()}

class MongoServer:
    def __init__(self, mongod_path=r"D:\MongoDB\bin\mongod.exe", db_path=r"D:\MongoDB\data\db"):
        self.mongod_path = mongod_path
        self.db_path = db_path
        self.process = None

    def start(self):
        os.makedirs(self.db_path, exist_ok=True)
        self.process = Popen(
            [
                self.mongod_path,
                "--dbpath",
                self.db_path
            ],
            stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL
        )
        time.sleep(2)

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            self.process.wait()

class RawLogDB:
    def __init__(self, url = "mongodb://localhost:27017/"):
        self.url = url
        global use_mongo
        if use_mongo:
            try:
                self.mongo_server = MongoServer()
                self.mongo_server.start()
                self.client = MongoClient(self.url)
                self.db = self.client["raw_message_log"]
                self.collection = self.db["messages"]
            except Exception as e:
                PrettyLogger.error(f"Failed to connect to MongoDB: {e}")
                self.client = None
                self.db = None
                self.collection = None
                self.mongo_server.stop()
                use_mongo = False
        else:
            self.client = None
            self.db = None
            self.collection = None
            self.mongo_server = None

    def check_if_up(self):
        if self.mongo_server and self.mongo_server.process:
            if self.mongo_server.process.poll() is not None:
                PrettyLogger.error("MongoDB server stopped unexpectedly.")
                global use_mongo
                use_mongo = False
                self.collection = None
                return False
            else:
                return True
        else:
            PrettyLogger.error("MongoDB server is not running.")
            return False
            
    def log_message(self, message):
        if not use_mongo:
            return
        self.check_if_up()
        dict_msg = message.to_dict()
        dict_msg["date"] = str(dict_msg.get("date", ""))
        if self.collection.find_one({"id": dict_msg.get("id")}):
            return
        self.collection.insert_one(dict_msg)

    def get_messages(self, chat_id=None):
        if not use_mongo:
            return list()
        self.check_if_up()
        if chat_id is not None:
            return list(self.collection.find({"chat_id": chat_id}))
        else:
            return list(self.collection.find())

    def get_message(self, message_id):
        if not use_mongo:
            return list()
        self.check_if_up()
        return self.collection.find_one({"id": int(message_id)})

    def close(self):
        self.check_if_up()
        if self.client:
            self.client.close()
        if self.mongo_server:
            self.mongo_server.stop()

def get_chat_type(message):
    if message.is_private:
        return "private"
    elif message.is_group:
        return "group"
    elif message.is_channel:
        return "broadcast_channel" if message.chat.broadcast else "supergroup"
    return "unknown"