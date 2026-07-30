#!/usr/bin/env python3

import subprocess
from pathlib import Path
from merge import merge
import os

HOST = "DESKTOP-L96GFF9"
SHARE = "data"
USERNAME = "DESKTOP-L96GFF9/tonia"
REMOTE_FILE = "message_log_backup.db"

args = os.sys.argv[1:]
merge_flag = True
if len(args) > 0:
    if "--no-merge" in args:
        merge_flag = False

SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_DIR = SCRIPT_DIR / "data"
LOCAL_DIR.mkdir(exist_ok=True)

def fetch_file(filename: str):
    cmd = [
        "smbclient",
        f"//{HOST}/{SHARE}",
        "-U",
        USERNAME,
        "-c",
        f'cd .; lcd "{LOCAL_DIR}"; get "{filename}"'
    ]
    result = subprocess.run(cmd)
    if result.returncode == 0:
        print(f"Downloaded {filename} to {LOCAL_DIR}")
    else:
        print(f"Failed to download {filename}.")

def main():
    fetch_file(REMOTE_FILE)
    if merge_flag:
        merge()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"An error occurred: {e}")