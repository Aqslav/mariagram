from mariagram_lib import *
from tonia import *
from message_logger import *
import sys
import os
import asyncio
import threading
from page_writer import PageWriter
from progress_bar import ProgressBar

this_folder = os.path.dirname(os.path.abspath(__file__))
os.chdir(this_folder)

PRINT_MESSAGE_ID = True

state_lock = threading.Lock()
chosen_chat_id = None
log_db = LogDB()
writer = PageWriter(page_width=os.get_terminal_size().columns, page_height=os.get_terminal_size().lines-2)

def print_message(msg):
    side = "right" if msg["sender_id"] == str(logger.my_id) else "left"
    text = f"{msg['time_formatted']}\n"
    if PRINT_MESSAGE_ID:
        text += f"{msg['message_id']}\n"
    text += f"{msg['sender_name']}:\n{msg['message_text']}\n"
    lines = PageWriter.split_text(text, writer.page_width)
    max_length = max(len(line) for line in lines)
    text = f"{'='*max_length}\n{text}{'='*max_length}\n"
    PrettyLogger.fit(text, side=side, printer=writer.write)

def print_chat(chat_info, chat_id):
    global writer
    progress = ProgressBar(width=os.get_terminal_size().columns, accept_every=10)
    writer = PageWriter(page_width=os.get_terminal_size().columns, page_height=os.get_terminal_size().lines-3)
    writer.header = f"Messages for {chat_info['chat_name']} ({chat_info['chat_username']}, {chat_info['chat_number']}) - ID: {chat_id}"
    messages = chat_info.get("messages", [])
    for i, msg in enumerate(messages):
        print_message(msg)
        progress.update((i + 1) / len(messages), label=f"Loading messages ({i + 1}/{len(messages)})")
    writer.current_page = len(PageWriter.split_pages(writer.text, writer.page_width, writer.page_height, writer.header)) - 1
    writer.loop()

def get_preview(msg, max_len=None):
    text = f"{msg['time_formatted'][-8:-3]} {msg['sender_name']}: {msg['message_text']}"
    newline_index = text.find('\n')
    if newline_index != -1:
        cutoff = max(min(newline_index, max_len-3), 0)
        cut = True
    else:
        cutoff = max_len
        cut = False
    return text[:cutoff]+("..." if cut else "")

def get_color_for_chat_type(chat_type):
    if chat_type == "private":
        return Color.Foreground.CYAN
    elif chat_type == "group":
        return Color.Foreground.GREEN
    elif chat_type == "supergroup":
        return Color.Foreground.BLUE
    elif chat_type == "broadcast_channel":
        return Color.Foreground.YELLOW
    else:
        return Color.Foreground.RESET
def sort_chats_by_last_message(messages):
    def get_last_message_time(chat_info):
        if chat_info.get("messages") is not None and len(chat_info["messages"]) > 0:
            return chat_info["messages"][-1]["time"]
        else:
            return 0

    sorted_items = sorted(messages.items(), key=lambda item: get_last_message_time(item[1]), reverse=True)
    return dict(sorted_items)

messages = {}
choice_locked = False

def print_chats():
    global messages
    if choice_locked:
        return
    messages = sort_chats_by_last_message(log_db.get_messages())
    items = messages.items()
    text = ""
    def write_text(*texts, endswith="\n"):
        nonlocal text
        for t in texts:
            text += t
        text += endswith
    for i, (chat_id, chat_info) in enumerate(items):
        if chat_info.get("messages") is not None and len(chat_info["messages"]) > 0:
            last_msg = chat_info["messages"][-1]
            preview = get_preview(last_msg, max_len=os.get_terminal_size().columns-len(chat_info['chat_type'])-3)
            PrettyLogger.write(f"{i+1}: {chat_info['chat_name']} ({chat_info['chat_username']}, {chat_info['chat_number']}) - ID: {chat_id}\n{Color.Foreground.rgb(128,128,128)}{preview}{Color.Foreground.RESET}", f"[{chat_info['chat_type']}]", get_color_for_chat_type(chat_info['chat_type']), printer=write_text)
        else:
            PrettyLogger.write(f"{i+1}: {chat_info['chat_name']} ({chat_info['chat_username']}, {chat_info['chat_number']}) - ID: {chat_id}", f"[{chat_info['chat_type']}]", get_color_for_chat_type(chat_info['chat_type']), printer=write_text)
    if chosen_chat_id is None:
        writer.text = text
        writer.update()

def choose_chat():
    global writer, messages, choice_locked
    choice_locked = False
    progress = ProgressBar(width=os.get_terminal_size().columns, accept_every=10)
    writer = PageWriter(page_width=os.get_terminal_size().columns, page_height=os.get_terminal_size().lines-3, exit_keys=["0","1","2","3","4","5","6","7","8","9","\x1b","w","\x1b\x1b"])
    messages = sort_chats_by_last_message(log_db.get_messages())
    items = messages.items()
    for i, (chat_id, chat_info) in enumerate(items):
        progress.update((i + 1) / len(items), label=f"Loading chats ({i + 1}/{len(items)})")
        if chat_info.get("messages") is not None and len(chat_info["messages"]) > 0:
            last_msg = chat_info["messages"][-1]
            preview = get_preview(last_msg, max_len=os.get_terminal_size().columns-len(chat_info['chat_type'])-3)
            PrettyLogger.write(f"{i+1}: {chat_info['chat_name']} ({chat_info['chat_username']}, {chat_info['chat_number']}) - ID: {chat_id}\n{Color.Foreground.rgb(128,128,128)}{preview}{Color.Foreground.RESET}", f"[{chat_info['chat_type']}]", get_color_for_chat_type(chat_info['chat_type']), printer=writer.write)
        else:
            PrettyLogger.write(f"{i+1}: {chat_info['chat_name']} ({chat_info['chat_username']}, {chat_info['chat_number']}) - ID: {chat_id}", f"[{chat_info['chat_type']}]", get_color_for_chat_type(chat_info['chat_type']), printer=writer.write)
    writer.loop()
    choice_locked = True
    print("Enter the chat number to view messages (or 'q' to quit): ")
    idx = input()
    if idx.lower() == 'q':
        raise SystemExit
    if not idx.isdigit() or int(idx) < 1 or int(idx) > len(messages):
        return None, None
    chat_id = list(messages.keys())[int(idx) - 1]
    chat_info = messages[chat_id]
    return chat_info, chat_id

def on_message(info, new = True):
    with state_lock:
        current_id = chosen_chat_id
    if current_id is not None and info["chat_id"] == current_id and new:
        print_message(info)
    elif current_id is None and new:
        print_chats()


if __name__ == "__main__":
    try:
        logger = MessageLogger(API_ID, API_HASH, SESSION_NAME)
        logger.print_messages = False
        logger.backtrack = True
        logger.runtime_check = True
        logger.forward_scan = True
        logger.on_message = on_message
        logger_thread = threading.Thread(target=lambda: asyncio.run(logger.run()), daemon=True)
        logger_thread.start()
        while True:
            print("Wait a bit...")
            new_chat, new_chat_id = choose_chat()
            if new_chat is None:
                clear()
                continue
            with state_lock:
                chosen_chat_id = new_chat_id
            clear()
            logger.priority_chat = new_chat_id
            print("Wait a bit...")
            print_chat(new_chat, new_chat_id)
            with state_lock:
                chosen_chat_id = None
            logger.priority_chat = None
            clear()
    except SystemExit:
        logger.client.disconnect()
        raw_log_db.close()
        exit(0)
    except:
        import traceback
        print("An error occurred:")
        traceback.print_exc()
    finally:
        logger.client.disconnect()
        raw_log_db.close()
        input()