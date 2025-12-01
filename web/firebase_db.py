import logging
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional, List

import firebase_admin
from firebase_admin import credentials, firestore, auth, storage

logger = logging.getLogger(__name__)

# Legacy DB Path removed


# Initialize Firebase
# Try to find service account key
cred_path = Path(__file__).parent / "serviceAccountKey.json"
if cred_path.exists():
    try:
        cred = credentials.Certificate(str(cred_path))
        firebase_admin.initialize_app(cred, options={
            'storageBucket': 'mss-video-creator-app.firebasestorage.app'
        })
        logger.info("[FIREBASE] Initialized with serviceAccountKey.json and storage bucket")
    except ValueError:
        # App already initialized
        pass
else:
    # Try default credentials (works on Cloud Run if configured)
    try:
        firebase_admin.initialize_app(options={
            'storageBucket': 'mss-video-creator-app.firebasestorage.app'
        })
        logger.info("[FIREBASE] Initialized with default credentials and storage bucket (UPDATED - ROUND 7 CHECK)")
    except ValueError:
        pass
    except Exception as e:
        logger.warning(f"[FIREBASE] Failed to initialize: {e}. DB operations may fail.")

def get_db():
    """Return Firestore client."""
    return firestore.client()

# --- Auth & User Management ---

def verify_user(email: str, password: str) -> Dict[str, Any]:
    """
    DEPRECATED in Firebase flow: Client handles password.
    This is kept for compatibility if we need to verify credentials server-side,
    but Firebase Admin SDK DOES NOT support verifying passwords.
    
    We should change the API to expect an ID Token instead.
    For now, return error to force frontend update.
    """
    return {"success": False, "error": "Please log in via the new Firebase login form."}

def verify_id_token(id_token: str) -> Dict[str, Any]:
    """Verify Firebase ID Token from client."""
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        
        # Ensure user doc exists
        user_ref = get_db().collection('users').document(uid)
        doc = user_ref.get()
        if not doc.exists:
            # Create basic user doc
            user_data = {
                'email': email,
                'created_at': firestore.SERVER_TIMESTAMP,
                'subscription_tier': 'free',
                'videos_this_month': 0,
                'total_videos': 0,
                'username': email.split('@')[0]
            }
            user_ref.set(user_data)
            user_dict = user_data
            user_dict['id'] = uid
        else:
            user_dict = doc.to_dict()
            user_dict['id'] = uid
            
        return {"success": True, "user": user_dict, "uid": uid}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_user(email: str, password: str, username: Optional[str] = None) -> Dict[str, Any]:
    """Create user in Firebase Auth and Firestore."""
    try:
        # Create Auth User
        user_record = auth.create_user(
            email=email,
            password=password,
            display_name=username
        )
        
        # Create Firestore Doc
        user_data = {
            'email': email,
            'username': username or email.split('@')[0],
            'created_at': firestore.SERVER_TIMESTAMP,
            'subscription_tier': 'free',
            'videos_this_month': 0,
            'total_videos': 0,
            'email_sent_80': 0,
            'email_sent_100': 0
        }
        get_db().collection('users').document(user_record.uid).set(user_data)
        
        return {"success": True, "user_id": user_record.uid}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_session(user_id: str, duration_days: int = 7, remember_me: bool = False) -> str:
    """
    Create a Firebase Session Cookie.
    NOTE: user_id here MUST be the Firebase UID.
    """
    try:
        # We need an ID token to create a session cookie, but this function is usually called
        # after we verified the user. 
        # IF we are migrating, we might need to change how this is called.
        # However, typically the client sends ID token, and we exchange it for Session Cookie.
        # BUT `create_session` in legacy code just generated a random string.
        # We can't easily generate a Firebase Session Cookie without an ID token.
        
        # Temporary Hybrid: Just return a random string and store it in Firestore 'sessions' collection?
        # This allows us to keep the "Session ID" concept without full Firebase Session Cookie strictness yet.
        # Let's do that for easier migration.
        
        import secrets
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=duration_days)
        
        get_db().collection('sessions').document(session_id).set({
            'user_id': user_id,
            'expires_at': expires_at,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        
        # Update last login
        get_db().collection('users').document(user_id).update({
            'last_login': firestore.SERVER_TIMESTAMP
        })
        
        return session_id
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return ""

def get_session(session_id: str) -> Dict[str, Any]:
    """Retrieve session from Firestore."""
    try:
        doc_ref = get_db().collection('sessions').document(session_id)
        doc = doc_ref.get()
        if not doc.exists:
            return {"success": False, "error": "Invalid session"}
        
        data = doc.to_dict()
        # Check expiry
        # Firestore timestamps are datetime objects with timezone
        expires_at = data.get('expires_at')
        if expires_at:
            # Ensure comparison works (remove tz if needed or make now aware)
            now = datetime.now(expires_at.tzinfo)
            if now > expires_at:
                return {"success": False, "error": "Session expired"}
        
        user_id = data.get('user_id')
        
        # Get User
        user_doc = get_db().collection('users').document(user_id).get()
        if not user_doc.exists:
            return {"success": False, "error": "User not found"}
            
        user_data = user_doc.to_dict()
        user_data['id'] = user_id
        
        return {"success": True, "user": user_data}
    except Exception as e:
        return {"success": False, "error": str(e)}

def delete_session(session_id: str) -> Dict[str, Any]:
    try:
        get_db().collection('sessions').document(session_id).delete()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- Stats & Usage ---

def get_user_stats(user_id: str) -> Optional[Dict[str, Any]]:
    try:
        doc = get_db().collection('users').document(user_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    except:
        return None

def get_usage_stats(user_id: str) -> Optional[Dict[str, Any]]:
    return get_user_stats(user_id)

USAGE_LIMITS: Dict[str, Optional[int]] = {
    "free": 3,
    "starter": 10,
    "pro": None,
    "agency": None,
    "lifetime": None,
}

def _check_and_reset_monthly_usage(user_id: str) -> None:
    # Similar logic to SQL but with Firestore
    stats = get_user_stats(user_id)
    if not stats:
        return

    now = datetime.utcnow()
    current_month = now.strftime("%Y-%m")
    last_reset = stats.get("last_reset_month")

    if last_reset != current_month:
        get_db().collection('users').document(user_id).update({
            'videos_this_month': 0,
            'last_reset_month': current_month,
            'email_sent_80': 0,
            'email_sent_100': 0
        })

def can_create_video(user_id: str) -> Dict[str, Any]:
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

def increment_video_count(user_id: str) -> Dict[str, Any]:
    _check_and_reset_monthly_usage(user_id)
    
    ref = get_db().collection('users').document(user_id)
    ref.update({
        'videos_this_month': firestore.Increment(1),
        'total_videos': firestore.Increment(1)
    })
    
    # Check limits for email (simplified)
    return {"success": True}

# --- Video History ---

def add_video_to_history(user_id: str, video_filename: str, title: Optional[str]) -> Dict[str, Any]:
    try:
        get_db().collection('users').document(user_id).collection('video_history').add({
            'video_filename': video_filename,
            'title': title,
            'created_at': firestore.SERVER_TIMESTAMP
        })
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_user_videos(user_id: str, limit: int = 20) -> Iterable[Dict[str, Any]]:
    try:
        docs = (get_db().collection('users').document(user_id)
                .collection('video_history')
                .order_by('created_at', direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream())
        
        videos = []
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            # Convert timestamp to string or keep as object? 
            # Frontend might expect string.
            if d.get('created_at'):
                d['created_at'] = d['created_at'].isoformat() if hasattr(d['created_at'], 'isoformat') else str(d['created_at'])
            videos.append(d)
        return videos
    except Exception as e:
        logger.error(f"Error getting videos: {e}")
        return []

# --- Init ---
def init_db():
    # No schema migration needed for Firestore
    pass


# --- Storage & Logos ---

def upload_file(file_obj, destination_path: str, content_type: str = None) -> str:
    """
    Upload a file-like object to Firebase Storage.
    Returns the public download URL.
    """
    try:
        bucket = storage.bucket()
        blob = bucket.blob(destination_path)
        
        # Reset file pointer just in case
        file_obj.seek(0)
        
        blob.upload_from_file(file_obj, content_type=content_type)
        blob.make_public()
        
        return blob.public_url
    except Exception as e:
        logger.error(f"Error uploading file to storage: {e}")
        raise e

def add_logo(user_id: str, name: str, url: str, filename: str) -> Dict[str, Any]:
    """Add a logo to the user's library in Firestore."""
    try:
        logo_data = {
            'name': name,
            'url': url,
            'filename': filename,
            'active': False,
            'uploadedAt': firestore.SERVER_TIMESTAMP
        }
        # Use a subcollection for user logos
        doc_ref = get_db().collection('users').document(user_id).collection('logos').add(logo_data)
        
        logo_data['id'] = doc_ref[1].id
        # Convert timestamp for immediate return
        logo_data['uploadedAt'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        
        return {"success": True, "logo": logo_data}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_logos(user_id: str) -> List[Dict[str, Any]]:
    """Get all logos for a user."""
    try:
        docs = (get_db().collection('users').document(user_id)
                .collection('logos')
                .order_by('uploadedAt', direction=firestore.Query.DESCENDING)
                .stream())
        
        logos = []
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            # Convert timestamp
            if d.get('uploadedAt'):
                 # Handle both Firestore Timestamp and string (legacy)
                ts = d['uploadedAt']
                if hasattr(ts, 'isoformat'):
                    d['uploadedAt'] = ts.isoformat()
                else:
                    d['uploadedAt'] = str(ts)
            logos.append(d)
        return logos
    except Exception as e:
        logger.error(f"Error getting logos: {e}")
        return []

def delete_logo(user_id: str, logo_id: str) -> Dict[str, Any]:
    """Delete a logo from Firestore and Storage."""
    try:
        # Get logo to find filename for storage deletion
        doc_ref = get_db().collection('users').document(user_id).collection('logos').document(logo_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return {"success": False, "error": "Logo not found"}
            
        data = doc.to_dict()
        filename = data.get('filename')
        
        # Delete from Firestore
        doc_ref.delete()
        
        # Delete from Storage (optional, but good practice)
        if filename:
            try:
                bucket = storage.bucket()
                blob = bucket.blob(f"logos/{filename}")
                blob.delete()
            except Exception as e:
                logger.warning(f"Failed to delete logo from storage: {e}")
                
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def set_active_logo(user_id: str, logo_id: str) -> Dict[str, Any]:
    """Set a logo as active and deactivate others."""
    try:
        # Deactivate all current active logos
        # Ideally use a batch or transaction, but for now simple query is fine
        docs = (get_db().collection('users').document(user_id)
                .collection('logos')
                .where('active', '==', True)
                .stream())
        
        batch = get_db().batch()
        
        for doc in docs:
            batch.update(doc.reference, {'active': False})
            
        # Activate new logo
        if logo_id:
            ref = get_db().collection('users').document(user_id).collection('logos').document(logo_id)
            batch.update(ref, {'active': True})
            
        batch.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- Avatars ---

def save_avatar(user_id: str, data: Dict[str, Any], avatar_id: str = None) -> Dict[str, Any]:
    """Save (create or update) an avatar in Firestore."""
    try:
        # Extract filename from URL if not provided (for deletion later)
        if 'filename' not in data and 'image_url' in data:
            # Try to extract from Firebase Storage URL
            # Format: .../o/avatars%2Ffilename?alt=...
            try:
                from urllib.parse import unquote
                url = data['image_url']
                if '/o/' in url:
                    path = unquote(url.split('/o/')[1].split('?')[0])
                    if '/' in path:
                        data['filename'] = path.split('/')[-1]
            except Exception:
                pass # Keep going if we can't extract

        # Map frontend fields to DB fields if needed
        # Frontend sends: name, type, image_url, video_url, position, scale, opacity, gender, voice
        # DB expects: name, url (for image), video_url, filename, etc.
        
        db_data = {
            'name': data.get('name'),
            'type': data.get('type', 'image'),
            'url': data.get('image_url'), # Main URL is image_url
            'video_url': data.get('video_url'),
            'position': data.get('position', 'bottom-right'),
            'scale': int(data.get('scale', 25)),
            'opacity': int(data.get('opacity', 100)),
            'gender': data.get('gender', 'female'),
            'voice': data.get('voice'),
            'updatedAt': firestore.SERVER_TIMESTAMP
        }
        
        if 'filename' in data:
            db_data['filename'] = data['filename']

        if avatar_id:
            # Update
            doc_ref = get_db().collection('users').document(user_id).collection('avatars').document(avatar_id)
            doc_ref.set(db_data, merge=True)
            db_data['id'] = avatar_id
        else:
            # Create
            db_data['active'] = False # Default inactive
            db_data['uploadedAt'] = firestore.SERVER_TIMESTAMP
            doc_ref = get_db().collection('users').document(user_id).collection('avatars').add(db_data)
            db_data['id'] = doc_ref[1].id
            # Convert timestamp for return
            db_data['uploadedAt'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        # Convert timestamps for return (remove Sentinel objects)
        if 'updatedAt' in db_data:
            db_data['updatedAt'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        return {"success": True, "avatar": db_data}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_avatars(user_id: str) -> List[Dict[str, Any]]:
    """Get all avatars for a user."""
    try:
        docs = (get_db().collection('users').document(user_id)
                .collection('avatars')
                .order_by('uploadedAt', direction=firestore.Query.DESCENDING)
                .stream())
        
        avatars = []
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            d['image_url'] = d.get('url') # Frontend expects image_url
            # Convert timestamp
            if d.get('uploadedAt'):
                ts = d['uploadedAt']
                if hasattr(ts, 'isoformat'):
                    d['uploadedAt'] = ts.isoformat()
                else:
                    d['uploadedAt'] = str(ts)
            avatars.append(d)
        return avatars
    except Exception as e:
        logger.error(f"Error getting avatars: {e}")
        return []

def delete_avatar(user_id: str, avatar_id: str) -> Dict[str, Any]:
    """Delete an avatar from Firestore and Storage."""
    try:
        # Get avatar to find filename for storage deletion
        doc_ref = get_db().collection('users').document(user_id).collection('avatars').document(avatar_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return {"success": False, "error": "Avatar not found"}
            
        data = doc.to_dict()
        filename = data.get('filename')
        
        # Delete from Firestore
        doc_ref.delete()
        
        # Delete from Storage
        if filename:
            try:
                bucket = storage.bucket()
                blob = bucket.blob(f"avatars/{filename}")
                blob.delete()
            except Exception as e:
                logger.warning(f"Failed to delete avatar from storage: {e}")
                
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def set_active_avatar(user_id: str, avatar_id: str) -> Dict[str, Any]:
    """Set an avatar as active and deactivate others."""
    try:
        # Deactivate all current active avatars
        docs = (get_db().collection('users').document(user_id)
                .collection('avatars')
                .where('active', '==', True)
                .stream())
        
        batch = get_db().batch()
        
        for doc in docs:
            batch.update(doc.reference, {'active': False})
            
        # Activate new avatar
        if avatar_id:
            ref = get_db().collection('users').document(user_id).collection('avatars').document(avatar_id)
            batch.update(ref, {'active': True})
            
        batch.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
