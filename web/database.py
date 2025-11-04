"""
Database models and initialization for MSS user accounts
Supports both SQLite (local dev) and PostgreSQL (production via DATABASE_URL)
"""

import sqlite3
import hashlib  # Legacy - being replaced
import bcrypt
import secrets
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import sql
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / 'mss_users.db'
DATABASE_URL = os.getenv('DATABASE_URL')  # PostgreSQL connection string

# Detect which database to use
USE_POSTGRES = bool(DATABASE_URL and POSTGRES_AVAILABLE)

def get_db():
    """Get database connection (PostgreSQL if DATABASE_URL set, otherwise SQLite)"""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    else:
        conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn

def _sql(query):
    """Convert SQLite ? placeholders to PostgreSQL %s if needed"""
    if USE_POSTGRES:
        return query.replace('?', '%s')
    return query

def init_db():
    """Initialize database with tables"""
    conn = get_db()
    cursor = conn.cursor()

    # Users table - compatible with both SQLite and PostgreSQL
    if USE_POSTGRES:
        cursor.execute(_sql('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                username VARCHAR(100),
                subscription_tier VARCHAR(50) DEFAULT 'free',
                videos_this_month INTEGER DEFAULT 0,
                total_videos INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                stripe_customer_id VARCHAR(255),
                reset_day INTEGER DEFAULT 1
            )
        ''')
    else:
        cursor.execute(_sql('''
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
    cursor.execute(_sql('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Video history table
    cursor.execute(_sql('''
        CREATE TABLE IF NOT EXISTS video_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            video_filename TEXT NOT NULL,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute(_sql('''
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

    # Avatars table - store avatar metadata and file paths
    cursor.execute(_sql('''
        CREATE TABLE IF NOT EXISTS avatars (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT DEFAULT 'image',
            image_url TEXT,
            video_url TEXT,
            filename TEXT NOT NULL,
            position TEXT DEFAULT 'bottom-right',
            scale INTEGER DEFAULT 18,
            opacity INTEGER DEFAULT 100,
            gender TEXT DEFAULT 'female',
            voice TEXT DEFAULT 'en-US-Neural2-F',
            active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Logos table - store logo metadata and file paths
    cursor.execute(_sql('''
        CREATE TABLE IF NOT EXISTS logos (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            filename TEXT NOT NULL,
            url TEXT NOT NULL,
            active BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Performance: Add indexes for faster queries
    cursor.execute(_sql('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute(_sql('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)')
    cursor.execute(_sql('CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)')
    cursor.execute(_sql('CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)')
    cursor.execute(_sql('CREATE INDEX IF NOT EXISTS idx_video_history_user_id ON video_history(user_id)')
    cursor.execute(_sql('CREATE INDEX IF NOT EXISTS idx_video_history_created ON video_history(created_at)')
    cursor.execute(_sql('CREATE INDEX IF NOT EXISTS idx_avatars_active ON avatars(active)')
    cursor.execute(_sql('CREATE INDEX IF NOT EXISTS idx_logos_active ON logos(active)')
    
    conn.commit()
    conn.close()
    print(f"[DATABASE] Initialized at {DB_PATH}")

def hash_password(password):
    """Hash password with bcrypt (secure)"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_hash, provided_password):
    """Verify password against bcrypt hash, with migration support for old SHA-256 hashes"""
    try:
        # Try bcrypt first (newer, secure method)
        if bcrypt.checkpw(provided_password.encode('utf-8'), stored_hash.encode('utf-8')):
            return True
    except (ValueError, TypeError):
        # Invalid bcrypt hash format - might be old SHA-256 hash
        pass
    
    # Fallback: check if it's old SHA-256 hash (for migration)
    # This is less secure but needed for existing users
    old_hash = hashlib.sha256(provided_password.encode()).hexdigest()
    if stored_hash == old_hash:
        # Password verified with old hash - should be migrated on next login
        # Note: Migration should happen in the verify_user function
        return True
    
    return False

def create_user(email, password, username=None):
    """Create a new user"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        password_hash = hash_password(password)

        cursor.execute(_sql('''
            INSERT INTO users (email, password_hash, username)
            VALUES (?, ?, ?)
        ''')), (email, password_hash, username or email.split('@')[0]))

        conn.commit()
        
        if USE_POSTGRES:
            cursor.execute(_sql('SELECT lastval()')
            user_id = cursor.fetchone()[0]
        else:
            user_id = cursor.lastrowid
            
        conn.close()

        return {'success': True, 'user_id': user_id}
    except Exception as e:
        error_str = str(e).lower()
        if 'unique' in error_str or 'duplicate' in error_str or 'already' in error_str:
            return {'success': False, 'error': 'Email already registered'}
        return {'success': False, 'error': str(e)}

def verify_user(email, password):
    """Verify user credentials"""
    conn = get_db()
    cursor = conn.cursor()

    # Fetch user by email first
    cursor.execute(_sql('''
        SELECT * FROM users
        WHERE email = ?
    ''')), (email,))

    user = cursor.fetchone()

    if not user:
        conn.close()
        return {'success': False, 'error': 'Invalid email or password'}

    # Verify password using the new verify_password function
    stored_hash = user['password_hash']
    password_valid = verify_password(stored_hash, password)
    
    # If password is valid and it was using old SHA-256 hash, migrate to bcrypt
    if password_valid:
        # Check if it's an old SHA-256 hash (64 char hex string, not bcrypt format)
        # Bcrypt hashes start with $2b$ and are 60 chars long
        if len(stored_hash) == 64 and all(c in '0123456789abcdef' for c in stored_hash.lower()):
            # This is an old SHA-256 hash - migrate to bcrypt
            new_hash = hash_password(password)
            cursor.execute(_sql('''
                UPDATE users
                SET password_hash = ?
                WHERE id = ?
            ''')), (new_hash, user['id']))
            conn.commit()
            logger.info(f"[SECURITY] Migrated password hash for user {email} from SHA-256 to bcrypt")
        
        conn.close()
        return {'success': True, 'user': dict(user)}
    else:
        conn.close()
        return {'success': False, 'error': 'Invalid email or password'}

def create_session(user_id, duration_days=7, remember_me=False):
    """Create a new session for user
    
    Args:
        user_id: User ID
        duration_days: Session duration (default: 7 days)
        remember_me: If True, extends to 30 days (default: False)
    """
    conn = get_db()
    cursor = conn.cursor()

    session_id = secrets.token_urlsafe(32)
    # Use 30 days if "Remember Me" is checked, otherwise 7 days
    actual_duration = 30 if remember_me else duration_days
    expires_at = datetime.now() + timedelta(days=actual_duration)

    cursor.execute(_sql('''
        INSERT INTO sessions (session_id, user_id, expires_at)
        VALUES (?, ?, ?)
    ''', (session_id, user_id, expires_at))

    # Update last login
    cursor.execute(_sql('''
        UPDATE users SET last_login = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (user_id,))

    conn.commit()
    conn.close()

    return session_id

def get_session(session_id):
    """Get user from session with Redis caching for performance"""
    # Performance: Check cache first
    try:
        from web.cache import get_cached_user_session, cache_user_session
        cached = get_cached_user_session(session_id)
        if cached:
            return {'success': True, 'user': cached}
    except Exception:
        pass  # Cache unavailable, fall back to database
    
    # Database lookup
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(_sql('''
        SELECT u.* FROM users u
        JOIN sessions s ON u.id = s.user_id
        WHERE s.session_id = ? AND s.expires_at > CURRENT_TIMESTAMP
    ''', (session_id,))

    user = cursor.fetchone()
    conn.close()

    if user:
        user_dict = dict(user)
        # Performance: Cache the session for faster future lookups
        try:
            from web.cache import cache_user_session
            # Cache for remaining session duration (default 7 days)
            cache_user_session(session_id, user_dict, ttl=604800)
        except Exception:
            pass  # Cache unavailable
        
        return {'success': True, 'user': user_dict}
    else:
        return {'success': False, 'error': 'Invalid or expired session'}

def delete_session(session_id):
    """Delete a session (logout)"""
    # Performance: Invalidate cached session
    try:
        from web.cache import invalidate_user_session
        invalidate_user_session(session_id)
    except Exception:
        pass  # Cache unavailable, continue with DB deletion
    
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(_sql('DELETE FROM sessions WHERE session_id = ?', (session_id,))

    conn.commit()
    conn.close()

    return {'success': True}

def get_user_stats(user_id):
    """Get user statistics"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(_sql('''
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

    cursor.execute(_sql('''
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

    cursor.execute(_sql('''
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

    cursor.execute(_sql('''
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

    cursor.execute(_sql('UPDATE users SET videos_this_month = 0')

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
    cursor.execute(_sql('SELECT id FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return {'success': False, 'error': 'User not found'}

    user_id = user[0]

    # Generate token
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now() + timedelta(hours=1)).isoformat()

    # Save token
    cursor.execute(_sql('''
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

    cursor.execute(_sql('''
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
    import hashlib  # Legacy - being replaced
    import bcrypt
    from datetime import datetime

    # Validate token first
    validation = validate_reset_token(token)
    if not validation['valid']:
        return validation

    user_id = validation['user_id']

    # Hash new password
    password_hash = hash_password(new_password)

    conn = get_db()
    cursor = conn.cursor()

    # Update password
    cursor.execute(_sql('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))

    # Mark token as used
    cursor.execute(_sql('UPDATE password_reset_tokens SET used = 1 WHERE token = ?', (token,))

    conn.commit()
    conn.close()

    return {'success': True, 'message': 'Password reset successfully'}

def get_user_by_email(email):
    """Get user by email address"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(_sql('SELECT id, email, username FROM users WHERE email = ?', (email,))
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

    cursor.execute(_sql('''
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
    cursor.execute(_sql('''
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
        cursor.execute(_sql('''
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
        cursor.execute(_sql('''
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

    cursor.execute(_sql('''
        UPDATE users
        SET videos_this_month = videos_this_month + 1,
            total_videos = total_videos + 1
        WHERE id = ?
    ''', (user_id,))

    conn.commit()

    # Get updated stats to check if we should send notification
    cursor.execute(_sql('''
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
                    cursor.execute(_sql('UPDATE users SET email_sent_80 = 1 WHERE id = ?', (user_id,))
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
                    cursor.execute(_sql('UPDATE users SET email_sent_100 = 1 WHERE id = ?', (user_id,))
                    conn.commit()
                    conn.close()
            except Exception as e:
                print(f"[EMAIL] Failed to send limit reached email: {e}")

    return {'success': True}

def reset_monthly_usage():
    """Reset monthly video counts for all users (run on 1st of month)"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(_sql('UPDATE users SET videos_this_month = 0')

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

    cursor.execute(_sql('''
        UPDATE users
        SET subscription_tier = ?
        WHERE id = ?
    ''', (tier, user_id))

    conn.commit()
    conn.close()

    return {'success': True, 'tier': tier, 'new_limit': USAGE_LIMITS[tier]}

# ============================================================================
# Avatar and Logo Database Functions
# ============================================================================

def get_all_avatars():
    """Get all avatars from database"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql('''
        SELECT id, name, type, image_url, video_url, filename, position, 
               scale, opacity, gender, voice, active, created_at, updated_at
        FROM avatars
        ORDER BY created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    avatars = []
    for row in rows:
        avatars.append({
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'image_url': row[3],
            'video_url': row[4],
            'filename': row[5],
            'position': row[6],
            'scale': row[7],
            'opacity': row[8],
            'gender': row[9],
            'voice': row[10],
            'active': bool(row[11]),
            'created_at': row[12],
            'updated_at': row[13]
        })
    return avatars

def get_active_avatar():
    """Get the currently active avatar"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql('''
        SELECT id, name, type, image_url, video_url, filename, position, 
               scale, opacity, gender, voice, active
        FROM avatars
        WHERE active = 1
        LIMIT 1
    ''')
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        'id': row[0],
        'name': row[1],
        'type': row[2],
        'image_url': row[3],
        'video_url': row[4],
        'filename': row[5],
        'position': row[6],
        'scale': row[7],
        'opacity': row[8],
        'gender': row[9],
        'voice': row[10],
        'active': bool(row[11])
    }

def save_avatar_to_db(avatar_data):
    """Save or update an avatar in the database"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if avatar exists
    cursor.execute(_sql('SELECT id FROM avatars WHERE id = ?', (avatar_data['id'],))
    exists = cursor.fetchone()
    
    if exists:
        # Update existing avatar
        cursor.execute(_sql('''
            UPDATE avatars
            SET name = ?, type = ?, image_url = ?, video_url = ?, filename = ?,
                position = ?, scale = ?, opacity = ?, gender = ?, voice = ?,
                active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            avatar_data.get('name'),
            avatar_data.get('type', 'image'),
            avatar_data.get('image_url'),
            avatar_data.get('video_url', ''),
            avatar_data.get('filename'),
            avatar_data.get('position', 'bottom-right'),
            avatar_data.get('scale', 18),
            avatar_data.get('opacity', 100),
            avatar_data.get('gender', 'female'),
            avatar_data.get('voice', 'en-US-Neural2-F'),
            avatar_data.get('active', False),
            avatar_data['id']
        ))
    else:
        # Insert new avatar
        cursor.execute(_sql('''
            INSERT INTO avatars 
            (id, name, type, image_url, video_url, filename, position, scale, opacity, gender, voice, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            avatar_data['id'],
            avatar_data.get('name'),
            avatar_data.get('type', 'image'),
            avatar_data.get('image_url'),
            avatar_data.get('video_url', ''),
            avatar_data.get('filename'),
            avatar_data.get('position', 'bottom-right'),
            avatar_data.get('scale', 18),
            avatar_data.get('opacity', 100),
            avatar_data.get('gender', 'female'),
            avatar_data.get('voice', 'en-US-Neural2-F'),
            avatar_data.get('active', False)
        ))
    
    conn.commit()
    conn.close()
    return True

def set_active_avatar_in_db(avatar_id):
    """Set an avatar as active (and deactivate all others)"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Set all to inactive
    cursor.execute(_sql('UPDATE avatars SET active = 0')
    
    # Set the selected one to active
    cursor.execute(_sql('UPDATE avatars SET active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (avatar_id,))
    
    conn.commit()
    conn.close()
    return True

def get_all_logos():
    """Get all logos from database"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql('''
        SELECT id, name, filename, url, active, created_at, updated_at
        FROM logos
        ORDER BY created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    logos = []
    for row in rows:
        logos.append({
            'id': row[0],
            'name': row[1],
            'filename': row[2],
            'url': row[3],
            'active': bool(row[4]),
            'created_at': row[5],
            'updated_at': row[6]
        })
    return logos

def get_active_logo():
    """Get the currently active logo"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql('''
        SELECT id, name, filename, url, active
        FROM logos
        WHERE active = 1
        LIMIT 1
    ''')
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return {
        'id': row[0],
        'name': row[1],
        'filename': row[2],
        'url': row[3],
        'active': bool(row[4])
    }

def save_logo_to_db(logo_data):
    """Save or update a logo in the database"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if logo exists
    cursor.execute(_sql('SELECT id FROM logos WHERE id = ?', (logo_data['id'],))
    exists = cursor.fetchone()
    
    if exists:
        # Update existing logo
        cursor.execute(_sql('''
            UPDATE logos
            SET name = ?, filename = ?, url = ?, active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            logo_data.get('name'),
            logo_data.get('filename'),
            logo_data.get('url'),
            logo_data.get('active', False),
            logo_data['id']
        ))
    else:
        # Insert new logo
        cursor.execute(_sql('''
            INSERT INTO logos (id, name, filename, url, active)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            logo_data['id'],
            logo_data.get('name'),
            logo_data.get('filename'),
            logo_data.get('url'),
            logo_data.get('active', False)
        ))
    
    conn.commit()
    conn.close()
    return True

def set_active_logo_in_db(logo_id):
    """Set a logo as active (and deactivate all others)"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Set all to inactive
    cursor.execute(_sql('UPDATE logos SET active = 0')
    
    # Set the selected one to active
    cursor.execute(_sql('UPDATE logos SET active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (logo_id,))
    
    conn.commit()
    conn.close()
    return True

def delete_logo_from_db(logo_id):
    """Delete a logo from the database"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(_sql('DELETE FROM logos WHERE id = ?', (logo_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

# Initialize database on import
if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")
