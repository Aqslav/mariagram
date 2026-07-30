import sqlite3
from mariagram_lib import LogDB
import os
this_folder = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.join(this_folder, "data"))

def merge():
    db_paths = os.listdir(".")
    log_conn = sqlite3.connect("message_log.db")
    log_cursor = log_conn.cursor()

    for db_path in db_paths:
        if db_path.endswith(".db") and db_path != "message_log.db":
            print(f"Processing {db_path}...")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages")
            messages = cursor.fetchall()
            cursor.execute("SELECT * FROM senders")
            senders = cursor.fetchall()
            cursor.execute("SELECT * FROM chats")
            chats = cursor.fetchall()
            for sender in senders:
                log_cursor.execute('''
                    INSERT OR IGNORE INTO senders (id, name, username, number)
                    VALUES (?, ?, ?, ?)
                ''', sender)
            for chat in chats:
                log_cursor.execute('''
                    INSERT OR IGNORE INTO chats (id, name, number, username, type)
                    VALUES (?, ?, ?, ?, ?)
                ''', chat)
            for message in messages:
                log_cursor.execute('''
                    INSERT OR IGNORE INTO messages (id, chat_id, sender_id, time, time_in_zone, time_formatted, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', message)
            log_conn.commit()
            conn.close()
    log_conn.close()

if __name__ == "__main__":
    merge()
