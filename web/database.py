"""
Database models and initialization for MSS user accounts
"""

import sqlite3
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / 'mss_users.db'

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

def init_db():
    """Initialize database with tables"""
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            username TEXT,
            subscription_tier TEXT DEFAULT 'free',
            videos_this_month INTEGER DEFAULT 0,
            total_videos INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            stripe_customer_id TEXT,
            reset_day INTEGER DEFAULT 1
        )
    ''')

    # Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Video history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS video_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            video_filename TEXT NOT NULL,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"[DATABASE] Initialized at {DB_PATH}")

def hash_password(password):
    """Hash password with SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(email, password, username=None):
    """Create a new user"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        password_hash = hash_password(password)

        cursor.execute('''
            INSERT INTO users (email, password_hash, username)
            VALUES (?, ?, ?)
        ''', (email, password_hash, username or email.split('@')[0]))

        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        return {'success': True, 'user_id': user_id}
    except sqlite3.IntegrityError:
        return {'success': False, 'error': 'Email already registered'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def verify_user(email, password):
    """Verify user credentials"""
    conn = get_db()
    cursor = conn.cursor()

    password_hash = hash_password(password)

    cursor.execute('''
        SELECT * FROM users
        WHERE email = ? AND password_hash = ?
    ''', (email, password_hash))

    user = cursor.fetchone()
    conn.close()

    if user:
        return {'success': True, 'user': dict(user)}
    else:
        return {'success': False, 'error': 'Invalid email or password'}

def create_session(user_id, duration_days=30):
    """Create a new session for user"""
    conn = get_db()
    cursor = conn.cursor()

    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=duration_days)

    cursor.execute('''
        INSERT INTO sessions (session_id, user_id, expires_at)
        VALUES (?, ?, ?)
    ''', (session_id, user_id, expires_at))

    # Update last login
    cursor.execute('''
        UPDATE users SET last_login = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (user_id,))

    conn.commit()
    conn.close()

    return session_id

def get_session(session_id):
    """Get user from session"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT u.* FROM users u
        JOIN sessions s ON u.id = s.user_id
        WHERE s.session_id = ? AND s.expires_at > CURRENT_TIMESTAMP
    ''', (session_id,))

    user = cursor.fetchone()
    conn.close()

    if user:
        return {'success': True, 'user': dict(user)}
    else:
        return {'success': False, 'error': 'Invalid or expired session'}

def delete_session(session_id):
    """Delete a session (logout)"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))

    conn.commit()
    conn.close()

    return {'success': True}

def get_user_stats(user_id):
    """Get user statistics"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT subscription_tier, videos_this_month, total_videos, created_at
        FROM users WHERE id = ?
    ''', (user_id,))

    stats = cursor.fetchone()
    conn.close()

    if stats:
        return dict(stats)
    else:
        return None

def increment_video_count(user_id):
    """Increment user's video count"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE users
        SET videos_this_month = videos_this_month + 1,
            total_videos = total_videos + 1
        WHERE id = ?
    ''', (user_id,))

    conn.commit()
    conn.close()

    return {'success': True}

def add_video_to_history(user_id, video_filename, title):
    """Add video to user's history"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO video_history (user_id, video_filename, title)
        VALUES (?, ?, ?)
    ''', (user_id, video_filename, title))

    conn.commit()
    conn.close()

    return {'success': True}

def get_user_videos(user_id, limit=20):
    """Get user's video history"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, video_filename, title, created_at
        FROM video_history
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    ''', (user_id, limit))

    rows = cursor.fetchall()
    conn.close()

    videos = []
    for row in rows:
        videos.append({
            'id': row[0],
            'filename': row[1],
            'title': row[2],
            'created_at': row[3]
        })

    return videos

def reset_monthly_counters():
    """Reset monthly video counters (run on 1st of each month)"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('UPDATE users SET videos_this_month = 0')

    conn.commit()
    affected = cursor.rowcount
    conn.close()

    return {'success': True, 'users_reset': affected}

def can_create_video(user_id):
    """Check if user can create another video based on their tier"""
    stats = get_user_stats(user_id)
    if not stats:
        return {'allowed': False, 'reason': 'User not found'}

    tier = stats['subscription_tier']
    count = stats['videos_this_month']

    limits = {
        'free': 3,
        'starter': 30,
        'pro': 'unlimited',
        'agency': 'unlimited',
        'lifetime': 'unlimited'
    }

    limit = limits.get(tier, 0)

    if limit == 'unlimited':
        return {
            'allowed': True,
            'current': count,
            'limit': 'unlimited',
            'remaining': 'unlimited'
        }
    elif count >= limit:
        return {
            'allowed': False,
            'reason': f'{tier.capitalize()} tier limit reached ({limit} videos/month)',
            'current': count,
            'limit': limit
        }
    else:
        return {
            'allowed': True,
            'current': count,
            'limit': limit,
            'remaining': limit - count
        }

def create_password_reset_token(email):
    """Create a password reset token for a user"""
    import secrets
    from datetime import datetime, timedelta

    conn = get_db()
    cursor = conn.cursor()

    # Find user by email
    cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return {'success': False, 'error': 'User not found'}

    user_id = user[0]

    # Generate token
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(hours=1)).isoformat()

    # Save token
    cursor.execute('''
        INSERT INTO password_reset_tokens (user_id, token, expires_at)
        VALUES (?, ?, ?)
    ''', (user_id, token, expires_at))

    conn.commit()
    conn.close()

    return {'success': True, 'token': token, 'email': email}

def validate_reset_token(token):
    """Validate a password reset token"""
    from datetime import datetime

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT user_id, expires_at, used
        FROM password_reset_tokens
        WHERE token = ?
    ''', (token,))

    result = cursor.fetchone()
    conn.close()

    if not result:
        return {'valid': False, 'error': 'Invalid token'}

    user_id, expires_at, used = result

    if used:
        return {'valid': False, 'error': 'Token already used'}

    if datetime.fromisoformat(expires_at) < datetime.now():
        return {'valid': False, 'error': 'Token expired'}

    return {'valid': True, 'user_id': user_id}

def reset_password(token, new_password):
    """Reset user's password using a valid token"""
    import hashlib
    from datetime import datetime

    # Validate token first
    validation = validate_reset_token(token)
    if not validation['valid']:
        return validation

    user_id = validation['user_id']

    # Hash new password
    password_hash = hashlib.sha256(new_password.encode()).hexdigest()

    conn = get_db()
    cursor = conn.cursor()

    # Update password
    cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))

    # Mark token as used
    cursor.execute('UPDATE password_reset_tokens SET used = 1 WHERE token = ?', (token,))

    conn.commit()
    conn.close()

    return {'success': True, 'message': 'Password reset successfully'}

def get_user_by_email(email):
    """Get user by email address"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT id, email, username FROM users WHERE email = ?', (email,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return {'id': result[0], 'email': result[1], 'username': result[2]}
    return None

# ============ Usage Limits ============

# Subscription tier limits (videos per month)
USAGE_LIMITS = {
    'free': 3,
    'starter': 10,
    'pro': 50,
    'agency': 200,
    'lifetime': 999999
}

def get_usage_stats(user_id):
    """Get user's current usage statistics"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT subscription_tier, videos_this_month, total_videos, reset_day
        FROM users WHERE id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        return None

    tier = result[0] or 'free'
    videos_this_month = result[1] or 0
    total_videos = result[2] or 0
    reset_day = result[3] or 1

    limit = USAGE_LIMITS.get(tier, 3)
    remaining = max(0, limit - videos_this_month)

    return {
        'subscription_tier': tier,
        'videos_this_month': videos_this_month,
        'total_videos': total_videos,
        'monthly_limit': limit,
        'videos_remaining': remaining,
        'reset_day': reset_day,
        'at_limit': videos_this_month >= limit
    }

def _check_and_reset_monthly_usage(user_id):
    """Check if it's a new month and reset usage counter if needed"""
    from datetime import datetime

    conn = get_db()
    cursor = conn.cursor()

    # First, ensure last_reset_month column exists
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_reset_month TEXT")
        conn.commit()
    except:
        pass  # Column already exists

    # Get user's current month tracking
    cursor.execute('''
        SELECT last_reset_month, videos_this_month
        FROM users WHERE id = ?
    ''', (user_id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return

    last_reset_month = result[0]
    current_count = result[1] or 0

    # Get current month/year as string
    now = datetime.now()
    current_month_str = now.strftime('%Y-%m')  # e.g. "2025-10"

    # If last_reset_month is different from current month, reset counter
    if last_reset_month != current_month_str and current_count > 0:
        cursor.execute('''
            UPDATE users
            SET videos_this_month = 0,
                last_reset_month = ?,
                email_sent_80 = 0,
                email_sent_100 = 0
            WHERE id = ?
        ''', (current_month_str, user_id))
        conn.commit()
        print(f"[AUTO-RESET] Reset monthly usage for user {user_id} (was {current_count}, now 0)")
    elif not last_reset_month:
        # First time, just set the month
        cursor.execute('''
            UPDATE users
            SET last_reset_month = ?
            WHERE id = ?
        ''', (current_month_str, user_id))
        conn.commit()

    conn.close()

def can_create_video(user_id):
    """Check if user can create a video based on their subscription limits"""
    # Check if we need to reset monthly counter
    _check_and_reset_monthly_usage(user_id)

    stats = get_usage_stats(user_id)
    if not stats:
        return {'allowed': False, 'error': 'User not found'}

    if stats['at_limit']:
        return {
            'allowed': False,
            'error': f"Monthly limit reached ({stats['monthly_limit']} videos). Upgrade your plan for more videos.",
            'stats': stats
        }

    return {'allowed': True, 'stats': stats}

def increment_video_count(user_id):
    """Increment user's video creation count and send email notifications if needed"""
    conn = get_db()
    cursor = conn.cursor()

    # Add notification tracking column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email_sent_80 INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE users ADD COLUMN email_sent_100 INTEGER DEFAULT 0")
        conn.commit()
    except:
        pass  # Columns already exist

    cursor.execute('''
        UPDATE users
        SET videos_this_month = videos_this_month + 1,
            total_videos = total_videos + 1
        WHERE id = ?
    ''', (user_id,))

    conn.commit()

    # Get updated stats to check if we should send notification
    cursor.execute('''
        SELECT email, username, videos_this_month, subscription_tier, email_sent_80, email_sent_100
        FROM users WHERE id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        email = result[0]
        username = result[1]
        videos_this_month = result[2]
        tier = result[3] or 'free'
        email_sent_80 = result[4]
        email_sent_100 = result[5]

        # Get limit for this tier
        from database import USAGE_LIMITS
        limit = USAGE_LIMITS.get(tier, 3)
        percentage = (videos_this_month / limit) * 100
        remaining = limit - videos_this_month

        # Send warning email at 80% (only once per month)
        if percentage >= 80 and not email_sent_80:
            try:
                from email_notifications import send_usage_warning_email
                if send_usage_warning_email(email, username, videos_this_month, limit, remaining):
                    # Mark as sent
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET email_sent_80 = 1 WHERE id = ?', (user_id,))
                    conn.commit()
                    conn.close()
            except Exception as e:
                print(f"[EMAIL] Failed to send 80% warning: {e}")

        # Send limit reached email at 100% (only once per month)
        if videos_this_month >= limit and not email_sent_100:
            try:
                from email_notifications import send_limit_reached_email
                if send_limit_reached_email(email, username, limit):
                    # Mark as sent
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET email_sent_100 = 1 WHERE id = ?', (user_id,))
                    conn.commit()
                    conn.close()
            except Exception as e:
                print(f"[EMAIL] Failed to send limit reached email: {e}")

    return {'success': True}

def reset_monthly_usage():
    """Reset monthly video counts for all users (run on 1st of month)"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('UPDATE users SET videos_this_month = 0')

    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()

    return {'success': True, 'users_reset': rows_affected}

def update_subscription_tier(user_id, tier):
    """Update user's subscription tier"""
    if tier not in USAGE_LIMITS:
        return {'success': False, 'error': f'Invalid tier: {tier}'}

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE users
        SET subscription_tier = ?
        WHERE id = ?
    ''', (tier, user_id))

    conn.commit()
    conn.close()

    return {'success': True, 'tier': tier, 'new_limit': USAGE_LIMITS[tier]}

# Initialize database on import
if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")
