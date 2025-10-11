"""
Quick script to upgrade a user to Pro/Admin tier
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'mss_users.db'

def upgrade_user(email, tier='pro'):
    """Upgrade user to specified tier (pro, agency, lifetime)"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute('UPDATE users SET subscription_tier = ? WHERE email = ?', (tier, email))

    if cursor.rowcount > 0:
        conn.commit()
        print(f"[OK] User {email} upgraded to {tier} tier")
    else:
        print(f"[ERROR] User {email} not found")

    conn.close()

def list_users():
    """List all users"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute('SELECT email, subscription_tier, videos_this_month, total_videos FROM users')
    users = cursor.fetchall()

    print("\n=== Current Users ===")
    for email, tier, month, total in users:
        print(f"  {email:30} | {tier:10} | {month:2} this month | {total:3} total")

    conn.close()

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python create_admin.py list                    # List all users")
        print("  python create_admin.py <email> [tier]          # Upgrade user (default: pro)")
        print("\nTiers: free, starter, pro, agency, lifetime")
        sys.exit(1)

    if sys.argv[1] == 'list':
        list_users()
    else:
        email = sys.argv[1]
        tier = sys.argv[2] if len(sys.argv) > 2 else 'pro'
        upgrade_user(email, tier)
        list_users()
