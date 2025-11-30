"""
Quick script to upgrade a user to Pro/Admin tier
"""
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import firebase_db

def upgrade_user(email, tier='pro'):
    """Upgrade user to specified tier (pro, agency, lifetime)"""
    db = firebase_db.get_db()
    users_ref = db.collection('users')
    
    # Find user by email
    query = users_ref.where('email', '==', email).limit(1).stream()
    
    user_doc = None
    for doc in query:
        user_doc = doc
        break
        
    if user_doc:
        user_doc.reference.update({'subscription_tier': tier})
        print(f"[OK] User {email} upgraded to {tier} tier")
    else:
        print(f"[ERROR] User {email} not found")

def list_users():
    """List all users"""
    db = firebase_db.get_db()
    users = db.collection('users').stream()

    print("\n=== Current Users ===")
    for doc in users:
        data = doc.to_dict()
        email = data.get('email', 'Unknown')
        tier = data.get('subscription_tier', 'free')
        month = data.get('videos_this_month', 0)
        total = data.get('total_videos', 0)
        print(f"  {email:30} | {tier:10} | {month:2} this month | {total:3} total")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python web/create_admin.py list                    # List all users")
        print("  python web/create_admin.py <email> [tier]          # Upgrade user (default: pro)")
        print("\nTiers: free, starter, pro, agency, lifetime")
        sys.exit(1)

    if sys.argv[1] == 'list':
        list_users()
    else:
        email = sys.argv[1]
        tier = sys.argv[2] if len(sys.argv) > 2 else 'pro'
        upgrade_user(email, tier)
        list_users()
