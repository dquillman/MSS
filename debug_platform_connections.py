import sqlite3
import os
import json

# Try to find the database
possible_paths = [
    "mss_users.db",
    "web/mss_users.db",
    "g:/Users/daveq/MSS/web/mss_users.db"
]

db_path = None
for path in possible_paths:
    if os.path.exists(path):
        db_path = path
        break

if not db_path:
    print("Database not found!")
    exit(1)

print(f"Using database: {db_path}")

conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='platform_connections'")
    if not c.fetchone():
        print("Table 'platform_connections' does not exist.")
    else:
        print("\n--- Platform Connections ---")
        c.execute("SELECT id, user_email, platform, status FROM platform_connections")
        rows = c.fetchall()
        if not rows:
            print("No platform connections found.")
        else:
            for row in rows:
                print(f"ID: {row[0]}, Email: {row[1]}, Platform: {row[2]}, Status: {row[3]}")

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channel_accounts'")
    if not c.fetchone():
        print("\nTable 'channel_accounts' does not exist.")
    else:
        print("\n--- Channel Accounts ---")
        c.execute("SELECT id, user_email, platform, channel_name, is_default FROM channel_accounts")
        rows = c.fetchall()
        if not rows:
            print("No channel accounts found.")
        else:
            for row in rows:
                print(f"ID: {row[0]}, Email: {row[1]}, Platform: {row[2]}, Name: {row[3]}, Default: {row[4]}")

except Exception as e:
    print(f"Error: {e}")

conn.close()
