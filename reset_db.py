"""
Utility script to clear all data and re-initialize the database from scratch.
Usage: python reset_db.py
"""

import os
import sys

# Configure UTF-8 stdout if needed
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config import settings
import database as db


def reset_database():
    db_file = settings.DATABASE_PATH
    print(f"[RESET] Clearing bot data for: {db_file}")

    # Remove main db file and any WAL / SHM files
    for ext in ["", "-wal", "-shm", "-journal"]:
        fpath = f"{db_file}{ext}"
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
                print(f"  - Removed: {fpath}")
            except Exception as e:
                print(f"  ! Could not remove {fpath}: {e}")

    # Re-initialize clean tables
    db.init_db()
    stats = db.get_system_stats()
    print("[SUCCESS] Database re-initialized with completely clean tables!")
    print(f"[STATUS] 0 registered users, {stats['remaining_seats']}/{settings.MAX_SEATS} seats available.")


if __name__ == "__main__":
    reset_database()
