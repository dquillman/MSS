"""
Database access helpers for MSS.

Provides a unified API that works with SQLite for local development and
PostgreSQL when the `DATABASE_URL` environment variable is configured.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

import bcrypt

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import errors as psycopg2_errors

    POSTGRES_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    psycopg2 = None  # type: ignore[assignment]
    psycopg2_extras = None  # type: ignore[assignment]
    psycopg2_errors = None  # type: ignore[assignment]
    POSTGRES_AVAILABLE = False

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "mss_users.db"
DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL and POSTGRES_AVAILABLE)

if DATABASE_URL and not POSTGRES_AVAILABLE:
    logger.warning(
        "[DATABASE] DATABASE_URL provided but psycopg2 is not installed. "
        "Falling back to SQLite at %s",
        DB_PATH,
    )

UNIQUE_EXCEPTIONS: Sequence[type[Exception]] = (sqlite3.IntegrityError,)
if POSTGRES_AVAILABLE:
    UNIQUE_EXCEPTIONS = UNIQUE_EXCEPTIONS + (psycopg2_errors.UniqueViolation,)  # type: ignore[attr-defined]


def get_db():
    """Return a database connection."""
    if USE_POSTGRES:
        assert psycopg2 is not None
        assert psycopg2_extras is not None
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2_extras.RealDictCursor,
        )
    else:
        conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
        conn.row_factory = sqlite3.Row
    return conn


def _sql(query: str) -> str:
    """Convert SQLite-style placeholders to PostgreSQL placeholders when needed."""
    return query.replace("?", "%s") if USE_POSTGRES else query


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(row)


def init_db() -> None:
    """Initialise required tables and indexes."""
    # Ensure database directory exists (for SQLite)
    if not USE_POSTGRES:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = get_db()
    try:
        cursor = conn.cursor()

        def ensure_column(table: str, column: str, definition: str) -> None:
            try:
                cursor.execute(_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
                conn.commit()
            except Exception as exc:  # pragma: no cover - depends on existing schema
                message = str(exc).lower()
                if "duplicate column" in message or "already exists" in message:
                    conn.rollback()
                else:
                    raise

        if USE_POSTGRES:
            cursor.execute(
                _sql(
                    """
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
                        reset_day INTEGER DEFAULT 1,
                        last_reset_month TEXT,
                        email_sent_80 INTEGER DEFAULT 0,
                        email_sent_100 INTEGER DEFAULT 0
                    )
                    """
                )
            )
        else:
            cursor.execute(
                _sql(
                    """
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
                        reset_day INTEGER DEFAULT 1,
                        last_reset_month TEXT,
                        email_sent_80 INTEGER DEFAULT 0,
                        email_sent_100 INTEGER DEFAULT 0
                    )
                    """
                )
            )

        cursor.execute(
            _sql(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
        )

        cursor.execute(
            _sql(
                """
                CREATE TABLE IF NOT EXISTS video_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    video_filename TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
        )

        cursor.execute(
            _sql(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """
            )
        )

        cursor.execute(
            _sql(
                """
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
                """
            )
        )

        cursor.execute(
            _sql(
                """
                CREATE TABLE IF NOT EXISTS logos (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    url TEXT NOT NULL,
                    active BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

        cursor.execute(_sql("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"))
        cursor.execute(_sql("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)"))
        cursor.execute(_sql("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)"))
        cursor.execute(_sql("CREATE INDEX IF NOT EXISTS idx_video_history_user_id ON video_history(user_id)"))
        cursor.execute(_sql("CREATE INDEX IF NOT EXISTS idx_video_history_created ON video_history(created_at)"))
        cursor.execute(_sql("CREATE INDEX IF NOT EXISTS idx_avatars_active ON avatars(active)"))
        cursor.execute(_sql("CREATE INDEX IF NOT EXISTS idx_logos_active ON logos(active)"))

        # Backfill columns that might be missing from older databases.
        ensure_column("users", "last_reset_month", "TEXT")
        ensure_column("users", "email_sent_80", "INTEGER DEFAULT 0")
        ensure_column("users", "email_sent_100", "INTEGER DEFAULT 0")

        conn.commit()
        logger.info("[DATABASE] Initialized at %s (postgres=%s)", DB_PATH, USE_POSTGRES)
    finally:
        conn.close()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(stored_hash: str, provided_password: str) -> bool:
    try:
        if bcrypt.checkpw(provided_password.encode("utf-8"), stored_hash.encode("utf-8")):
            return True
    except (ValueError, TypeError):
        pass

    legacy_hash = hashlib.sha256(provided_password.encode("utf-8")).hexdigest()
    return stored_hash == legacy_hash


def create_user(email: str, password: str, username: Optional[str] = None) -> Dict[str, Any]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        password_hash = hash_password(password)
        clean_email = email.strip().lower()
        clean_username = username or clean_email.split("@")[0]

        if USE_POSTGRES:
            cursor.execute(
                _sql(
                    """
                    INSERT INTO users (email, password_hash, username)
                    VALUES (?, ?, ?)
                    RETURNING id
                    """
                ),
                (clean_email, password_hash, clean_username),
            )
            user_id = cursor.fetchone()["id"]
        else:
            cursor.execute(
                _sql(
                    """
                    INSERT INTO users (email, password_hash, username)
                    VALUES (?, ?, ?)
                    """
                ),
                (clean_email, password_hash, clean_username),
            )
            user_id = cursor.lastrowid

        conn.commit()
        return {"success": True, "user_id": user_id}
    except UNIQUE_EXCEPTIONS:
        conn.rollback()
        return {"success": False, "error": "Email already registered"}
    except Exception as exc:  # pragma: no cover - defensive fallback
        conn.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


def verify_user(email: str, password: str) -> Dict[str, Any]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                SELECT * FROM users
                WHERE email = ?
                """
            ),
            (email.strip().lower(),),
        )
        user = cursor.fetchone()
        if not user:
            return {"success": False, "error": "Invalid email or password"}

        user_dict = _row_to_dict(user)
        stored_hash = user_dict.get("password_hash") or ""

        if not verify_password(stored_hash, password):
            return {"success": False, "error": "Invalid email or password"}

        # migrate legacy SHA256 hashes to bcrypt on successful login
        if len(stored_hash) == 64 and stored_hash == hashlib.sha256(password.encode("utf-8")).hexdigest():
            new_hash = hash_password(password)
            cursor.execute(
                _sql("UPDATE users SET password_hash = ? WHERE id = ?"),
                (new_hash, user_dict["id"]),
            )
            conn.commit()
            logger.info("[SECURITY] Migrated password hash for %s to bcrypt", email)

        user_dict.pop("password_hash", None)
        return {"success": True, "user": user_dict}
    except Exception as exc:  # pragma: no cover - defensive fallback
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


def create_session(user_id: int, duration_days: int = 7, remember_me: bool = False) -> str:
    conn = get_db()
    try:
        cursor = conn.cursor()
        session_id = secrets.token_urlsafe(32)
        actual_days = 30 if remember_me else duration_days
        expires_at = datetime.utcnow() + timedelta(days=actual_days)
        expires_value = expires_at if USE_POSTGRES else expires_at.isoformat()

        cursor.execute(
            _sql(
                """
                INSERT INTO sessions (session_id, user_id, expires_at)
                VALUES (?, ?, ?)
                """
            ),
            (session_id, user_id, expires_value),
        )
        cursor.execute(
            _sql("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?"),
            (user_id,),
        )
        conn.commit()
        return session_id
    finally:
        conn.close()


def get_session(session_id: str) -> Dict[str, Any]:
    try:
        from web.cache import cache_user_session, get_cached_user_session
    except Exception:  # pragma: no cover - cache is optional
        cache_user_session = None
        get_cached_user_session = None

    if get_cached_user_session:
        cached = get_cached_user_session(session_id)
        if cached:
            return {"success": True, "user": cached}

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                SELECT u.*
                FROM users u
                JOIN sessions s ON u.id = s.user_id
                WHERE s.session_id = ? AND s.expires_at > CURRENT_TIMESTAMP
                """
            ),
            (session_id,),
        )
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": "Invalid or expired session"}

        user = _row_to_dict(row)
        user.pop("password_hash", None)

        if cache_user_session:
            try:
                cache_user_session(session_id, user, ttl=604800)
            except Exception:
                pass

        return {"success": True, "user": user}
    finally:
        conn.close()


def delete_session(session_id: str) -> Dict[str, Any]:
    try:
        from web.cache import invalidate_user_session

        invalidate_user_session(session_id)
    except Exception:
        pass

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql("DELETE FROM sessions WHERE session_id = ?"),
            (session_id,),
        )
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def get_user_stats(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                SELECT subscription_tier, videos_this_month, total_videos, created_at
                FROM users
                WHERE id = ?
                """
            ),
            (user_id,),
        )
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def add_video_to_history(user_id: int, video_filename: str, title: Optional[str]) -> Dict[str, Any]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                INSERT INTO video_history (user_id, video_filename, title)
                VALUES (?, ?, ?)
                """
            ),
            (user_id, video_filename, title),
        )
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def get_user_videos(user_id: int, limit: int = 20) -> Iterable[Dict[str, Any]]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                SELECT id, video_filename, title, created_at
                FROM video_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """
            ),
            (user_id, limit),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row["id"] if isinstance(row, dict) else row[0],
                "filename": row["video_filename"] if isinstance(row, dict) else row[1],
                "title": row["title"] if isinstance(row, dict) else row[2],
                "created_at": row["created_at"] if isinstance(row, dict) else row[3],
            }
            for row in rows or []
        ]
    finally:
        conn.close()


def reset_monthly_counters() -> Dict[str, Any]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(_sql("UPDATE users SET videos_this_month = 0"))
        conn.commit()
        return {"success": True, "users_reset": cursor.rowcount}
    finally:
        conn.close()


USAGE_LIMITS: Dict[str, Optional[int]] = {
    "free": 3,
    "starter": 10,
    "pro": None,
    "agency": None,
    "lifetime": None,
}


def get_usage_stats(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                SELECT subscription_tier, videos_this_month, total_videos, reset_day,
                       COALESCE(last_reset_month, '') AS last_reset_month,
                       COALESCE(email_sent_80, 0) AS email_sent_80,
                       COALESCE(email_sent_100, 0) AS email_sent_100
                FROM users
                WHERE id = ?
                """
            ),
            (user_id,),
        )
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def _check_and_reset_monthly_usage(user_id: int) -> None:
    stats = get_usage_stats(user_id)
    if not stats:
        return

    now = datetime.utcnow()
    current_month = now.strftime("%Y-%m")
    last_reset = stats.get("last_reset_month")

    if last_reset != current_month:
        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                _sql(
                    """
                    UPDATE users
                    SET videos_this_month = 0,
                        last_reset_month = ?,
                        email_sent_80 = 0,
                        email_sent_100 = 0
                    WHERE id = ?
                    """
                ),
                (current_month, user_id),
            )
            conn.commit()
        finally:
            conn.close()


def can_create_video(user_id: int) -> Dict[str, Any]:
    _check_and_reset_monthly_usage(user_id)
    stats = get_usage_stats(user_id)
    if not stats:
        return {"allowed": False, "error": "User not found"}

    tier = stats.get("subscription_tier") or "free"
    limit = USAGE_LIMITS.get(tier, 0)
    used = stats.get("videos_this_month", 0)

    if limit is None:
        return {"allowed": True, "stats": stats, "remaining": "unlimited"}

    remaining = max(0, limit - used)
    if remaining <= 0:
        return {
            "allowed": False,
            "error": f"Monthly limit reached ({limit} videos). Upgrade your plan for more videos.",
            "stats": stats,
        }

    return {"allowed": True, "stats": stats, "remaining": remaining}


def increment_video_count(user_id: int) -> Dict[str, Any]:
    _check_and_reset_monthly_usage(user_id)

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                UPDATE users
                SET videos_this_month = videos_this_month + 1,
                    total_videos = total_videos + 1
                WHERE id = ?
                """
            ),
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()

    stats = get_usage_stats(user_id)
    if not stats:
        return {"success": False, "error": "User not found"}

    tier = stats.get("subscription_tier") or "free"
    limit = USAGE_LIMITS.get(tier)

    if not limit or limit <= 0:
        return {"success": True}

    used = stats.get("videos_this_month", 0)
    percentage = (used / limit) * 100 if limit else 0

    try:
        from . import email_notifications as email_utils
    except Exception:
        email_utils = None

    if email_utils and percentage >= 80 and not stats.get("email_sent_80"):
        try:
            if email_utils.send_usage_warning_email(
                stats.get("email"),
                stats.get("username"),
                used,
                limit,
                limit - used,
            ):
                _mark_email_flag(user_id, flag="email_sent_80")
        except Exception as exc:
            logger.warning("[EMAIL] Failed to send 80%% warning: %s", exc)

    if email_utils and used >= limit and not stats.get("email_sent_100"):
        try:
            if email_utils.send_limit_reached_email(
                stats.get("email"),
                stats.get("username"),
                limit,
            ):
                _mark_email_flag(user_id, flag="email_sent_100")
        except Exception as exc:
            logger.warning("[EMAIL] Failed to send limit reached email: %s", exc)

    return {"success": True}


def _mark_email_flag(user_id: int, flag: str) -> None:
    """Mark an email flag for a user. Flag must be a whitelisted column name."""
    # Security: Whitelist allowed flag names to prevent SQL injection
    ALLOWED_FLAGS = {"email_sent_80", "email_sent_100"}
    if flag not in ALLOWED_FLAGS:
        logger.warning(f"[SECURITY] Attempted to set invalid flag: {flag}")
        return
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        # Use parameterized query with whitelisted column name
        cursor.execute(
            _sql(f"UPDATE users SET {flag} = 1 WHERE id = ?"),
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def reset_monthly_usage() -> Dict[str, Any]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                UPDATE users
                SET videos_this_month = 0,
                    email_sent_80 = 0,
                    email_sent_100 = 0,
                    last_reset_month = ?
                """
            ),
            (datetime.utcnow().strftime("%Y-%m"),),
        )
        conn.commit()
        return {"success": True, "users_reset": cursor.rowcount}
    finally:
        conn.close()


def update_subscription_tier(user_id: int, tier: str) -> Dict[str, Any]:
    if tier not in USAGE_LIMITS:
        return {"success": False, "error": f"Invalid tier: {tier}"}

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                UPDATE users
                SET subscription_tier = ?
                WHERE id = ?
                """
            ),
            (tier, user_id),
        )
        conn.commit()
        return {"success": True, "tier": tier, "new_limit": USAGE_LIMITS[tier]}
    finally:
        conn.close()


def create_password_reset_token(email: str) -> Dict[str, Any]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql("SELECT id FROM users WHERE email = ?"),
            (email.strip().lower(),),
        )
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": "User not found"}

        user_id = row["id"] if isinstance(row, dict) else row[0]
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)
        expires_value = expires_at if USE_POSTGRES else expires_at.isoformat()

        cursor.execute(
            _sql(
                """
                INSERT INTO password_reset_tokens (user_id, token, expires_at)
                VALUES (?, ?, ?)
                """
            ),
            (user_id, token, expires_value),
        )
        conn.commit()
        return {"success": True, "token": token, "email": email}
    finally:
        conn.close()


def validate_reset_token(token: str) -> Dict[str, Any]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                SELECT user_id, expires_at, used
                FROM password_reset_tokens
                WHERE token = ?
                """
            ),
            (token,),
        )
        row = cursor.fetchone()
        if not row:
            return {"valid": False, "error": "Invalid token"}

        user_id, expires_at, used = (
            row["user_id"] if isinstance(row, dict) else row[0],
            row["expires_at"] if isinstance(row, dict) else row[1],
            row["used"] if isinstance(row, dict) else row[2],
        )

        if used:
            return {"valid": False, "error": "Token already used"}

        expiry = expires_at if isinstance(expires_at, datetime) else datetime.fromisoformat(expires_at)
        if expiry < datetime.utcnow():
            return {"valid": False, "error": "Token expired"}

        return {"valid": True, "user_id": user_id}
    finally:
        conn.close()


def reset_password(token: str, new_password: str) -> Dict[str, Any]:
    validation = validate_reset_token(token)
    if not validation.get("valid"):
        return validation

    user_id = validation["user_id"]
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql("UPDATE users SET password_hash = ? WHERE id = ?"),
            (hash_password(new_password), user_id),
        )
        cursor.execute(
            _sql("UPDATE password_reset_tokens SET used = 1 WHERE token = ?"),
            (token,),
        )
        conn.commit()
        return {"success": True, "message": "Password reset successfully"}
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql("SELECT id, email, username FROM users WHERE email = ?"),
            (email.strip().lower(),),
        )
        row = cursor.fetchone()
        if not row:
            return None
        data = _row_to_dict(row)
        return {"id": data.get("id"), "email": data.get("email"), "username": data.get("username")}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Avatar & Logo helpers
# ---------------------------------------------------------------------------

def get_all_avatars() -> Iterable[Dict[str, Any]]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                SELECT id, name, type, image_url, video_url, filename, position,
                       scale, opacity, gender, voice, active, created_at, updated_at
                FROM avatars
                ORDER BY created_at DESC
                """
            )
        )
        rows = cursor.fetchall() or []
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def get_active_avatar() -> Optional[Dict[str, Any]]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                SELECT id, name, type, image_url, video_url, filename, position,
                       scale, opacity, gender, voice, active
                FROM avatars
                WHERE active = 1
                LIMIT 1
                """
            )
        )
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def save_avatar_to_db(avatar_data: Dict[str, Any]) -> bool:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql("SELECT id FROM avatars WHERE id = ?"),
            (avatar_data["id"],),
        )
        exists = cursor.fetchone() is not None

        if exists:
            cursor.execute(
                _sql(
                    """
                    UPDATE avatars
                    SET name = ?, type = ?, image_url = ?, video_url = ?, filename = ?,
                        position = ?, scale = ?, opacity = ?, gender = ?, voice = ?,
                        active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """
                ),
                (
                    avatar_data.get("name"),
                    avatar_data.get("type", "image"),
                    avatar_data.get("image_url"),
                    avatar_data.get("video_url", ""),
                    avatar_data.get("filename"),
                    avatar_data.get("position", "bottom-right"),
                    avatar_data.get("scale", 18),
                    avatar_data.get("opacity", 100),
                    avatar_data.get("gender", "female"),
                    avatar_data.get("voice", "en-US-Neural2-F"),
                    1 if avatar_data.get("active") else 0,
                    avatar_data["id"],
                ),
            )
        else:
            cursor.execute(
                _sql(
                    """
                    INSERT INTO avatars (
                        id, name, type, image_url, video_url, filename,
                        position, scale, opacity, gender, voice, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (
                    avatar_data["id"],
                    avatar_data.get("name"),
                    avatar_data.get("type", "image"),
                    avatar_data.get("image_url"),
                    avatar_data.get("video_url", ""),
                    avatar_data.get("filename"),
                    avatar_data.get("position", "bottom-right"),
                    avatar_data.get("scale", 18),
                    avatar_data.get("opacity", 100),
                    avatar_data.get("gender", "female"),
                    avatar_data.get("voice", "en-US-Neural2-F"),
                    1 if avatar_data.get("active") else 0,
                ),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def set_active_avatar_in_db(avatar_id: str) -> bool:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(_sql("UPDATE avatars SET active = 0"))
        cursor.execute(
            _sql(
                """
                UPDATE avatars
                SET active = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """
            ),
            (avatar_id,),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_all_logos() -> Iterable[Dict[str, Any]]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                SELECT id, name, filename, url, active, created_at, updated_at
                FROM logos
                ORDER BY created_at DESC
                """
            )
        )
        rows = cursor.fetchall() or []
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def get_active_logo() -> Optional[Dict[str, Any]]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql(
                """
                SELECT id, name, filename, url, active
                FROM logos
                WHERE active = 1
                LIMIT 1
                """
            )
        )
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def save_logo_to_db(logo_data: Dict[str, Any]) -> bool:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql("SELECT id FROM logos WHERE id = ?"),
            (logo_data["id"],),
        )
        exists = cursor.fetchone() is not None

        if exists:
            cursor.execute(
                _sql(
                    """
                    UPDATE logos
                    SET name = ?, filename = ?, url = ?, active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """
                ),
                (
                    logo_data.get("name"),
                    logo_data.get("filename"),
                    logo_data.get("url"),
                    1 if logo_data.get("active") else 0,
                    logo_data["id"],
                ),
            )
        else:
            cursor.execute(
                _sql(
                    """
                    INSERT INTO logos (id, name, filename, url, active)
                    VALUES (?, ?, ?, ?, ?)
                    """
                ),
                (
                    logo_data["id"],
                    logo_data.get("name"),
                    logo_data.get("filename"),
                    logo_data.get("url"),
                    1 if logo_data.get("active") else 0,
                ),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def set_active_logo_in_db(logo_id: str) -> bool:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(_sql("UPDATE logos SET active = 0"))
        cursor.execute(
            _sql(
                """
                UPDATE logos
                SET active = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """
            ),
            (logo_id,),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def delete_logo_from_db(logo_id: str) -> bool:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            _sql("DELETE FROM logos WHERE id = ?"),
            (logo_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover
    init_db()
    print("Database initialized successfully!")

