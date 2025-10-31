import os
import json
import time
import sqlite3
import logging
from pathlib import Path
import sys

# Ensure project root is on sys.path so `web` package imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, request, jsonify, send_from_directory, Response, redirect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from PIL import Image, ImageDraw, ImageFont
import io
import requests
import stripe
import shutil
import uuid
from pydantic import BaseModel, EmailStr, Field, ValidationError as PydanticValidationError
from web.exceptions import (
    MSSException, VideoGenerationError, APIError,
    AuthenticationError, DatabaseError, FileUploadError
)

logging.basicConfig(
    level=logging.INFO if os.getenv('FLASK_ENV') != 'development' else logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Database access (robust import regardless of how app is launched)
try:
    # When installed as a package or run via `flask --app web.api_server`
    from web import database as database  # type: ignore
except Exception:
    try:
        # When running directly: `python web\api_server.py`
        import database  # type: ignore
    except Exception:
        # Fallback shim to avoid crashes if DB layer is unavailable
        class _DatabaseShim:
            @staticmethod
            def get_session(session_id):
                return {'success': False, 'error': 'db unavailable'}

            @staticmethod
            def can_create_video(user_id):
                return {'allowed': True, 'remaining': 'unlimited'}

            @staticmethod
            def increment_video_count(user_id):
                return {'success': True}

            @staticmethod
            def add_video_to_history(user_id, video_filename, title):
                return {'success': True}

            @staticmethod
            def verify_user(email, password):
                return {'success': False, 'error': 'Database unavailable - cannot verify user'}

            @staticmethod
            def create_user(email, password, username=None):
                return {'success': False, 'error': 'Database unavailable - cannot create user'}

            @staticmethod
            def create_session(user_id, duration_days=7, remember_me=False):
                return 'dummy_session_id'

        database = _DatabaseShim()  # type: ignore
        logger.error("[DATABASE] Failed to import database module - using fallback shim")

from scripts.make_video import (
    read_env,
    ensure_dir,
    openai_generate_topics,
    openai_draft_from_topic,
    google_tts,
    drive_upload_public,
    get_mp3_duration_seconds,
    build_shotstack_payload,
    build_shotstack_payload_wide,
    shotstack_render,
    shotstack_poll,
    render_video,
)
from scripts.video_utils import (
    generate_thumbnail_variants,
    get_stock_footage_for_keywords,
)

# Ensure temp directory is on the project drive (avoid filling system TEMP)
from pathlib import Path as _Path
import tempfile as _tempfile

# Best-effort .env loader (so OPENAI_API_KEY and others are available when launching directly)
def _load_env_file():
    try:
        root = _Path(__file__).parent.parent
        env_path = root / ".env"
        if env_path.exists():
            # Safety: back up .env on boot (timestamped + rolling .env.bak)
            try:
                backups = root / "backups"
                backups.mkdir(exist_ok=True)
                import time as _time
                ts = _time.strftime("%Y%m%d-%H%M%S")
                # Rolling backup
                bak_path = root / ".env.bak"
                try:
                    env_path.replace(bak_path)
                    bak_path.replace(env_path)  # move back to original place
                except Exception:
                    pass
                # Timestamped copy
                ts_path = backups / f".env-{ts}"
                try:
                    ts_path.write_text(env_path.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception:
                    pass
            except Exception:
                pass
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and v and not os.environ.get(k):
                        os.environ[k] = v
        if os.getenv("OPENAI_API_KEY"):
            print("[BOOT] OPENAI_API_KEY loaded from .env")
    except Exception as e:
        print(f"[BOOT] .env load skipped: {e}")

_load_env_file()

_tmp_dir = _Path(__file__).parent.parent / "tmp"
try:
    _tmp_dir.mkdir(exist_ok=True)
    os.environ["TMPDIR"] = str(_tmp_dir)
    os.environ["TEMP"] = str(_tmp_dir)
    os.environ["TMP"] = str(_tmp_dir)
    _tempfile.tempdir = str(_tmp_dir)
    print(f"[BOOT] Using temp dir: {_tmp_dir}")
except Exception as _e:
    print(f"[BOOT] Could not set temp dir: {_e}")

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1 GB upload cap
CORS(app, supports_credentials=True)  # Enable CORS with credentials for authentication

# Initialize database on startup
try:
    if hasattr(database, 'init_db'):
        database.init_db()
        logger.info("[DATABASE] Database initialized successfully")
except Exception as e:
    logger.warning(f"[DATABASE] Database initialization failed: {e}")
    # Don't crash - database will be created on first use if needed

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# Stripe Price IDs (will be set after creating products)
STRIPE_PRICES = {
    'starter': os.getenv('STRIPE_PRICE_STARTER', ''),  # $19/month
    'pro': os.getenv('STRIPE_PRICE_PRO', ''),          # $49/month
    'agency': os.getenv('STRIPE_PRICE_AGENCY', ''),    # $149/month
    'lifetime': os.getenv('STRIPE_PRICE_LIFETIME', ''),  # $199 one-time
}

@app.route('/')
def serve_landing():
    """Serve landing page"""
    return send_from_directory('topic-picker-standalone', 'landing.html')

@app.route('/studio')
@app.route('/studio.html')
def serve_studio():
    """Serve Studio page"""
    return send_from_directory('topic-picker-standalone', 'studio.html')

@app.route('/topics')
@app.route('/index.html')
def serve_topics():
    """Serve Topic Picker page"""
    return send_from_directory('topic-picker-standalone', 'index.html')

@app.route('/pricing')
@app.route('/pricing.html')
def serve_pricing():
    """Serve Pricing page"""
    return send_from_directory('topic-picker-standalone', 'pricing.html')

@app.route('/payment-success')
def serve_payment_success():
    """Serve Payment Success page"""
    return send_from_directory('topic-picker-standalone', 'payment-success.html')

@app.route('/admin')
@app.route('/admin.html')
def serve_admin():
    """Serve Admin page"""
    return send_from_directory('topic-picker-standalone', 'admin.html')

@app.route('/auth')
@app.route('/auth.html')
@app.route('/login')
@app.route('/signup')
def serve_auth():
    """Serve Authentication page"""
    try:
        return send_from_directory('topic-picker-standalone', 'auth.html')
    except Exception as e:
        logger.error(f"[AUTH] Error serving auth.html: {e}")
        # Fallback: try with absolute path
        try:
            topic_picker_dir = Path(__file__).parent / 'topic-picker-standalone'
            return send_from_directory(str(topic_picker_dir), 'auth.html')
        except Exception as e2:
            logger.error(f"[AUTH] Fallback also failed: {e2}")
            from flask import abort
            abort(404)

@app.route('/forgot-password')
@app.route('/forgot-password.html')
def serve_forgot_password():
    """Serve Forgot Password page"""
    return send_from_directory('topic-picker-standalone', 'forgot-password.html')

@app.route('/reset-password')
@app.route('/reset-password.html')
def serve_reset_password():
    """Serve Reset Password page"""
    return send_from_directory('topic-picker-standalone', 'reset-password.html')

@app.route('/terms')
@app.route('/terms.html')
@app.route('/terms-of-service')
def serve_terms():
    """Serve Terms of Service page"""
    return send_from_directory('topic-picker-standalone', 'terms.html')

@app.route('/privacy')
@app.route('/privacy.html')
@app.route('/privacy-policy')
def serve_privacy():
    """Serve Privacy Policy page"""
    return send_from_directory('topic-picker-standalone', 'privacy.html')


# Quiet favicon requests to avoid 404 noise
@app.route('/favicon.ico')
def favicon_silence():
    from flask import Response
    return Response(status=204)


# -------------------- Auth API --------------------
@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip()
        password = (data.get('password') or '').strip()
        remember_me = data.get('remember_me', False)
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password required'}), 400

        result = database.verify_user(email, password)
        if not result.get('success'):
            return jsonify({'success': False, 'error': result.get('error', 'Invalid credentials')}), 401

        user = result['user']
        session_id = database.create_session(user['id'], remember_me=remember_me)
        resp = jsonify({'success': True, 'user': {'id': user['id'], 'email': user['email']}})
        resp.set_cookie('session_id', session_id, httponly=True, samesite='Lax', secure=False, path='/')
        return resp
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ---------------- Intro/Outro Conversion ----------------

def _ensure_intro_outro_lib() -> dict:
    try:
        LIB_DIR.mkdir(exist_ok=True)
        if LIB_PATH.exists():
            data = json.loads(LIB_PATH.read_text(encoding='utf-8') or '{}')
            if isinstance(data, dict):
                data.setdefault('intros', [])
                data.setdefault('outros', [])
                data.setdefault('active', {'intro': None, 'outro': None})
                return data
    except Exception:
        pass
    return {'intros': [], 'outros': [], 'active': {'intro': None, 'outro': None}}

def _save_intro_outro_lib(data: dict):
    try:
        LIB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass

def _local_path_from_url(url: str) -> Path | None:
    try:
        if not url:
            return None
        if url.startswith('http://localhost:5000/intro_outro/') or url.startswith('http://127.0.0.1:5000/intro_outro/'):
            fname = url.split('/')[-1]
            return Path('intro_outro') / fname
        p = Path(url)
        return p if p.exists() else None
    except Exception:
        return None

def _convert_item_to_standard(item: dict, which: str) -> dict:
    """Convert an intro/outro item to 1080x1920@30fps H.264/AAC and update videoUrl.
    which: 'intro' or 'outro'
    """
    from scripts.ffmpeg_render import create_intro_video, create_outro_video
    import imageio_ffmpeg, subprocess

    width, height = 1080, 1920
    duration = float(item.get('duration') or 3.0)

    src_path = None
    url = (item.get('videoUrl') or '').strip()
    if url:
        src_path = _local_path_from_url(url)

    # If no video source, render HTML to a temp MP4 first
    if not src_path:
        tmp = Path('intro_outro') / f"tmp_{which}_{int(time.time())}.mp4"
        if which == 'intro':
            create_intro_video(tmp, {'html': item.get('html', '')}, duration, width, height, imageio_ffmpeg.get_ffmpeg_exe())
        else:
            create_outro_video(tmp, {'html': item.get('html', '')}, duration, width, height, imageio_ffmpeg.get_ffmpeg_exe())
        src_path = tmp

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out_name = f"std_{which}_{item.get('id') or 'item'}_{int(time.time())}.mp4"
    out_path = Path('intro_outro') / out_name

    cmd = [
        ffmpeg, '-hide_banner', '-loglevel', 'error',
        '-i', str(src_path),
        '-r', '30',
        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-ac', '2',
        '-movflags', '+faststart',
        '-y', str(out_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Convert failed: {res.stderr[:300]}")

    # Update item
    from urllib.parse import urljoin
    base = 'http://127.0.0.1:5000/'
    item['videoUrl'] = urljoin(base, f"intro_outro/{out_name}")
    item['itemType'] = 'video'
    return item

@app.route('/convert-intro-outro', methods=['POST'])
def convert_intro_outro():
    try:
        data = request.get_json(force=True) or {}
        which = (data.get('type') or '').strip().lower()  # 'intro' or 'outro'
        item_id = (data.get('id') or '').strip()
        set_active = bool(data.get('set_active', True))
        if which not in ('intro', 'outro') or not item_id:
            return jsonify({'success': False, 'error': 'type and id required'}), 400
        lib = _ensure_intro_outro_lib()
        items = lib['intros'] if which == 'intro' else lib['outros']
        item = next((x for x in items if str(x.get('id')) == item_id), None)
        if not item:
            return jsonify({'success': False, 'error': 'Item not found'}), 404
        item = _convert_item_to_standard(item, which)
        # write back
        for i, x in enumerate(items):
            if str(x.get('id')) == item_id:
                items[i] = item
                break
        if set_active:
            lib.setdefault('active', {'intro': None, 'outro': None})
            lib['active'][which] = item.get('id')
        _save_intro_outro_lib(lib)
        return jsonify({'success': True, 'item': item, 'active': lib.get('active')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/convert-active-intro-outro', methods=['POST'])
def convert_active_intro_outro():
    try:
        data = request.get_json(silent=True) or {}
        set_active = bool(data.get('set_active', True))
        lib = _ensure_intro_outro_lib()
        act = lib.get('active') or {}
        changed = []
        for which in ('intro', 'outro'):
            act_id = (act.get(which) or '').strip()
            items = lib['intros'] if which == 'intro' else lib['outros']
            if not items:
                continue
            item = None
            if act_id:
                item = next((x for x in items if str(x.get('id')) == act_id), None)
            if item is None:
                item = next((x for x in items if x.get('active')), None)
            if item is None:
                continue
            item = _convert_item_to_standard(item, which)
            for i, x in enumerate(items):
                if str(x.get('id')) == item.get('id'):
                    items[i] = item
                    break
            if set_active:
                lib.setdefault('active', {'intro': None, 'outro': None})
                lib['active'][which] = item.get('id')
            changed.append({'type': which, 'id': item.get('id'), 'videoUrl': item.get('videoUrl')})
        _save_intro_outro_lib(lib)
        return jsonify({'success': True, 'changed': changed, 'active': lib.get('active')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ---------------- Intro/Outro Library Endpoints ----------------

LIB_DIR = Path('intro_outro')
LIB_DIR.mkdir(exist_ok=True)
LIB_PATH = LIB_DIR / 'library.json'

def _load_intro_outro_library():
    """Load intro/outro library, supporting both new and legacy formats.

    New format: intro_outro/library.json with keys { intros: [], outros: [], active: { intro, outro } }
    Legacy format: intro_outro_library.json at repo root with items marking active via item['active'].
    """
    # 1) Try new format first
    try:
        if LIB_PATH.exists():
            data = json.loads(LIB_PATH.read_text(encoding='utf-8') or '{}')
            if not isinstance(data, dict):
                data = {}
            data.setdefault('intros', [])
            data.setdefault('outros', [])
            data.setdefault('active', {'intro': None, 'outro': None})
            # If new lib has any items, use it
            if data['intros'] or data['outros']:
                return data
    except Exception:
        pass

    # 2) Fallback to legacy file(s)
    legacy_candidates = [
        Path(__file__).parent.parent / 'intro_outro_library.json',
        Path(__file__).parent / 'intro_outro_library.json',
    ]
    for cand in legacy_candidates:
        try:
            if cand.exists():
                raw = cand.read_text(encoding='utf-8')
                legacy = json.loads(raw or '{}') if raw is not None else {}
                if isinstance(legacy, dict):
                    intros = legacy.get('intros', []) or []
                    outros = legacy.get('outros', []) or []
                    active_map = {'intro': None, 'outro': None}
                    act_intro = next((x for x in intros if x.get('active')), None)
                    act_outro = next((x for x in outros if x.get('active')), None)
                    if act_intro:
                        active_map['intro'] = act_intro.get('id') or act_intro.get('name')
                    if act_outro:
                        active_map['outro'] = act_outro.get('id') or act_outro.get('name')
                    data = {'intros': intros, 'outros': outros, 'active': active_map}
                    # Persist to new format so UI sees it next time
                    try:
                        LIB_DIR.mkdir(exist_ok=True)
                        LIB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                    except Exception:
                        pass
                    return data
        except Exception:
            continue

    # 3) Nothing found
    return {'intros': [], 'outros': [], 'active': {'intro': None, 'outro': None}}

def _save_intro_outro_library(data: dict):
    LIB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

@app.route('/intro_outro/<path:filename>', methods=['GET'])
def serve_intro_outro_file(filename):
    try:
        return send_from_directory(LIB_DIR.absolute(), filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/get-intro-outro-library', methods=['GET'])
def get_intro_outro_library():
    try:
        data = _load_intro_outro_library()
        return jsonify({'success': True, **data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/upload-intro-outro-file', methods=['POST'])
def upload_intro_outro_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        f = request.files['file']
        if not f.filename:
            return jsonify({'success': False, 'error': 'Empty filename'}), 400
        ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else 'bin'
        fname = f"io_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
        path = LIB_DIR / fname
        f.save(str(path))
        from urllib.parse import urljoin
        base = request.host_url if hasattr(request, 'host_url') else 'http://127.0.0.1:5000/'
        url = urljoin(base, f"intro_outro/{fname}")
        return jsonify({'success': True, 'file': fname, 'url': url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/save-intro-outro', methods=['POST'])
def save_intro_outro():
    try:
        payload = request.get_json(silent=True) or {}
        typ = (payload.get('type') or '').strip().lower()  # 'intro' or 'outro'
        if typ not in ('intro', 'outro'):
            return jsonify({'success': False, 'error': 'type must be intro or outro'}), 400
        data = _load_intro_outro_library()
        bucket = data['intros'] if typ == 'intro' else data['outros']
        item_id = payload.get('id') or f"{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"
        new_item = {
            'id': item_id,
            'name': payload.get('name') or f"{typ.title()} {item_id}",
            'duration': float(payload.get('duration') or 3),
            'html': payload.get('html') or '',
            'audio': payload.get('audio') or '',
            'videoUrl': payload.get('videoUrl') or '',
            'itemType': payload.get('itemType') or ('video' if payload.get('videoUrl') else 'html'),
            'updated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        # Update if exists
        idx = next((i for i, x in enumerate(bucket) if x.get('id') == item_id), None)
        if idx is None:
            bucket.append(new_item)
        else:
            bucket[idx] = new_item
        _save_intro_outro_library(data)
        return jsonify({'success': True, 'id': item_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/delete-intro-outro', methods=['POST'])
def delete_intro_outro():
    try:
        payload = request.get_json(silent=True) or {}
        typ = (payload.get('type') or '').strip().lower()
        item_id = payload.get('id')
        if typ not in ('intro', 'outro') or not item_id:
            return jsonify({'success': False, 'error': 'type and id required'}), 400
        data = _load_intro_outro_library()
        key = 'intros' if typ == 'intro' else 'outros'
        before = len(data[key])
        data[key] = [x for x in data[key] if x.get('id') != item_id]
        if data.get('active', {}).get(typ) == item_id:
            data['active'][typ] = None
        _save_intro_outro_library(data)
        return jsonify({'success': True, 'deleted': before - len(data[key])})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/set-active-intro-outro', methods=['POST'])
def set_active_intro_outro():
    try:
        payload = request.get_json(silent=True) or {}
        typ = (payload.get('type') or '').strip().lower()
        item_id = payload.get('id')
        if typ not in ('intro', 'outro'):
            return jsonify({'success': False, 'error': 'type must be intro or outro'}), 400
        data = _load_intro_outro_library()
        data.setdefault('active', {'intro': None, 'outro': None})
        data['active'][typ] = item_id
        _save_intro_outro_library(data)
        return jsonify({'success': True, 'active': data['active']})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/preview-tts', methods=['POST'])
def preview_tts():
    """Generate a short MP3 preview for provided text. Falls back to a small silent MP3 if TTS fails."""
    try:
        payload = request.get_json(silent=True) or {}
        text = (payload.get('text') or '').strip()
        if not text:
            return jsonify({'success': False, 'error': 'text required'}), 400
        out = LIB_DIR / f"tts_preview_{int(time.time())}.mp3"
        try:
            # Try Google TTS if configured
            google_tts(text, out)
        except Exception as e:
            print(f"[TTS] preview fallback: {e}")
            # Write a tiny silent MP3 so UI can play something
            mp3_data = bytes([0xFF, 0xFB, 0x90, 0x00] * 5000)
            out.write_bytes(mp3_data)
        from urllib.parse import urljoin
        base = request.host_url if hasattr(request, 'host_url') else 'http://127.0.0.1:5000/'
        url = urljoin(base, f"intro_outro/{out.name}")
        return jsonify({'success': True, 'audio_url': url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/logout', methods=['POST'])
def api_logout():
    try:
        sid = request.cookies.get('session_id')
        if sid:
            database.delete_session(sid)
        resp = jsonify({'success': True})
        resp.set_cookie('session_id', '', expires=0, path='/')
        return resp
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/me', methods=['GET'])
def api_me():
    """Get current user info from session"""
    try:
        session_id = request.cookies.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 200

        result = database.get_session(session_id)
        if not result.get('success'):
            return jsonify({'success': False, 'error': 'Invalid or expired session'}), 200

        user = result['user']
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'username': user['username'],
                'subscription_tier': user['subscription_tier'],
                'videos_this_month': user['videos_this_month'],
                'total_videos': user['total_videos'],
                'created_at': user['created_at']
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/signup', methods=['POST'])
def api_signup():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip()
        password = (data.get('password') or '').strip()
        username = (data.get('username') or '').strip() or None
        remember_me = data.get('remember_me', False)
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password required'}), 400

        res = database.create_user(email, password, username=username)
        if not res.get('success'):
            error_msg = res.get('error', 'Signup failed')
            # Provide helpful message for common errors
            if 'already registered' in error_msg.lower():
                error_msg = 'This email is already registered. Please try logging in instead, or use a different email address.'
            return jsonify({'success': False, 'error': error_msg}), 400
        user_id = res['user_id']
        session_id = database.create_session(user_id, remember_me=remember_me)
        resp = jsonify({'success': True, 'user': {'id': user_id, 'email': email}})
        resp.set_cookie('session_id', session_id, httponly=True, samesite='Lax', secure=False, path='/')
        return resp
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard')
@app.route('/dashboard.html')
def serve_dashboard():
    """Serve User Dashboard"""
    return send_from_directory('topic-picker-standalone', 'dashboard.html')

@app.route('/trends-calendar')
@app.route('/trends-calendar.html')
def serve_trends_calendar():
    """Serve Trends & Calendar Page"""
    return send_from_directory('topic-picker-standalone', 'trends-calendar.html')

@app.route('/workflow')
@app.route('/workflow.html')
def serve_workflow():
    """Serve Video Creation Workflow Page"""
    return send_from_directory('topic-picker-standalone', 'workflow.html')

@app.route('/<path:filename>')
def serve_frontend_file(filename):
    """Serve CSS, JS, and other frontend static files"""
    # Skip if it looks like an API endpoint
    api_prefixes = ['api', 'get-', 'set-', 'upload-', 'delete-', 'create-', 'generate-', 'post-process', 'save-', 'test-', 'health']
    if any(filename.startswith(prefix) for prefix in api_prefixes):
        from flask import abort
        abort(404)

    # Only serve static file types
    if filename.endswith(('.css', '.js', '.svg', '.png', '.jpg', '.ico', '.html')):
        try:
            return send_from_directory('topic-picker-standalone', filename)
        except:
            pass
    from flask import abort
    abort(404)

@app.route('/health')
@app.route('/healthz')
def _health():
    """Health check endpoint for Cloud Run"""
    return jsonify({
        'status': 'ok',
        'service': 'MSS API',
        'version': '5.5.7',
        'endpoints': [
            '/studio', '/topics', '/post-process-video',
            '/get-avatar-library', '/get-logo-library', '/api/logo-files',
            '/api/usage', '/youtube-categories', '/out/<file>', '/logos/<file>'
        ]
    })

@app.route('/get-selected-topic', methods=['GET'])
def get_selected_topic():
    """Return the most recently saved topic (out/topic_selected.json) if available."""
    try:
        outdir = Path('out')
        path = outdir / 'topic_selected.json'
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            return jsonify({'success': True, 'topic': data})
        else:
            return jsonify({'success': False, 'error': 'No topic saved yet'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get-avatar-library', methods=['GET'])
def get_avatar_library():
    try:
        path = Path(__file__).parent.parent / 'avatar_library.json'
        avatars_dir = Path(__file__).parent.parent / 'avatars'
        avatars = []
        if path.exists():
            try:
                raw = path.read_text(encoding='utf-8')
                data = json.loads(raw or '{}') if raw is not None else {}
                avatars = data.get('avatars', []) if isinstance(data, dict) else []
            except Exception:
                avatars = []
        # Fallback: scan avatars directory if library is missing/empty
        if (not avatars) and avatars_dir.exists():
            allowed_ext = ('.png', '.jpg', '.jpeg', '.webp')
            for f in avatars_dir.iterdir():
                if f.is_file() and f.suffix.lower() in allowed_ext:
                    stem = f.stem
                    avatars.append({
                        'id': stem,
                        'name': stem.replace('_', ' ').title(),
                        'image_url': f"http://127.0.0.1:5000/avatars/{f.name}",
                        'active': False,
                    })
            # Sort newest first where possible
            try:
                avatars.sort(key=lambda a: (avatars_dir / (a.get('id', '') + '.png')).stat().st_mtime if (avatars_dir / (a.get('id', '') + '.png')).exists() else 0, reverse=True)
            except Exception:
                pass
        return jsonify({'success': True, 'avatars': avatars})
    except Exception as e:
        # Still return 200 so UI can proceed
        return jsonify({'success': False, 'error': str(e), 'avatars': []}), 200


@app.route('/set-active-avatar', methods=['POST'])
def set_active_avatar():
    """Set an avatar as active"""
    try:
        data = request.get_json(force=True) or {}
        avatar_id = data.get('id')

        if not avatar_id:
            return jsonify({'success': False, 'error': 'No avatar ID provided'}), 400

        library_path = Path(__file__).parent.parent / 'avatar_library.json'

        # Load library
        avatars = []
        if library_path.exists():
            try:
                raw = library_path.read_text(encoding='utf-8')
                library_data = json.loads(raw or '{}')
                avatars = library_data.get('avatars', [])
            except Exception:
                avatars = []

        # Set all to inactive, then activate the selected one
        for avatar in avatars:
            avatar['active'] = (avatar.get('id') == avatar_id)

        # Save library
        library_path.write_text(json.dumps({'avatars': avatars}, indent=2, ensure_ascii=False), encoding='utf-8')

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save-avatar', methods=['POST'])
def save_avatar():
    """Save or update an avatar"""
    try:
        data = request.get_json(force=True) or {}
        avatar_id = data.get('id')

        library_path = Path(__file__).parent.parent / 'avatar_library.json'

        # Load library
        avatars = []
        if library_path.exists():
            try:
                raw = library_path.read_text(encoding='utf-8')
                library_data = json.loads(raw or '{}')
                avatars = library_data.get('avatars', [])
            except Exception:
                avatars = []

        # Generate ID if new avatar
        if not avatar_id:
            avatar_id = f"avatar_{int(time.time())}"

        # Create avatar object
        avatar = {
            'id': avatar_id,
            'name': data.get('name', 'Unnamed Avatar'),
            'type': data.get('type', 'image'),
            'image_url': data.get('image_url', ''),
            'video_url': data.get('video_url', ''),
            'position': data.get('position', 'bottom-right'),
            'scale': int(data.get('scale', 25)),
            'opacity': int(data.get('opacity', 100)),
            'gender': data.get('gender', 'female'),
            'voice': data.get('voice', 'en-US-Neural2-F'),
            'active': False
        }

        # Update or add avatar
        existing_index = next((i for i, a in enumerate(avatars) if a.get('id') == avatar_id), None)
        if existing_index is not None:
            # Keep active status when updating
            avatar['active'] = avatars[existing_index].get('active', False)
            avatars[existing_index] = avatar
        else:
            avatars.append(avatar)

        # Save library
        library_path.write_text(json.dumps({'avatars': avatars}, indent=2, ensure_ascii=False), encoding='utf-8')

        return jsonify({'success': True, 'id': avatar_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete-avatar', methods=['POST'])
def delete_avatar():
    """Delete an avatar"""
    try:
        data = request.get_json(force=True) or {}
        avatar_id = data.get('id')

        if not avatar_id:
            return jsonify({'success': False, 'error': 'No avatar ID provided'}), 400

        library_path = Path(__file__).parent.parent / 'avatar_library.json'

        # Load library
        avatars = []
        if library_path.exists():
            try:
                raw = library_path.read_text(encoding='utf-8')
                library_data = json.loads(raw or '{}')
                avatars = library_data.get('avatars', [])
            except Exception:
                avatars = []

        # Remove avatar
        avatars = [a for a in avatars if a.get('id') != avatar_id]

        # Save library
        library_path.write_text(json.dumps({'avatars': avatars}, indent=2, ensure_ascii=False), encoding='utf-8')

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/set-selected-topic', methods=['POST'])
def set_selected_topic():
    """Persist a selected topic to out/topic_selected.json for reuse across tools."""
    try:
        payload = request.get_json(force=True) or {}
        outdir = Path('out')
        outdir.mkdir(exist_ok=True)
        path = outdir / 'topic_selected.json'
        # Write with UTF-8 and pretty print for debugging
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return jsonify({'success': True, 'path': str(path)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/generate-meme-bg', methods=['POST'])
def generate_meme_bg():
    """Generate a meme background using the thumbnail generator with richer prompt.

    Body JSON: { title, hook, description, keywords[] }
    Returns: { success, file, url }
    """
    try:
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        hook = (data.get('hook') or data.get('angle') or '').strip()
        description = (data.get('description') or '').strip()
        keywords = data.get('keywords') or []
        # Build a rich prompt for the background generator
        key_str = ', '.join([str(k) for k in keywords][:10])
        rich_title = f"{title}. Hook: {hook}. Description: {description}. Keywords: {key_str}. Create a bold, high-contrast, safe-zone friendly background with depth and subtle lighting; NO text."

        outdir = Path(__file__).parent.parent / 'thumbnails'
        outdir.mkdir(exist_ok=True)

        # Prefer AI image generation with NO TEXT
        def _openai_background(prompt: str, outdir: Path) -> Path:
            from openai import OpenAI
            import requests as _req
            import base64 as _b64
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
            resp = client.images.generate(
                model=model,
                prompt=prompt,
                size=os.getenv("OPENAI_IMAGE_SIZE", "1536x1024"),
                quality=os.getenv("OPENAI_IMAGE_QUALITY", "high"),
                response_format="b64_json",
                n=1,
            )
            data0 = resp.data[0]
            content = None
            if hasattr(data0, 'b64_json') and data0.b64_json:
                content = _b64.b64decode(data0.b64_json)
            elif hasattr(data0, 'url') and data0.url:
                image_url = data0.url
                r = _req.get(image_url, timeout=30)
                r.raise_for_status()
                content = r.content
            else:
                raise RuntimeError('Image API returned no url or b64_json')
            fname = f"meme_bg_{int(time.time())}.png"
            path = outdir / fname
            path.write_bytes(content)
            return path

        def _gradient_background(outdir: Path) -> Path:
            # Simple, clean background without any text
            width, height = 1280, 720
            img = Image.new('RGB', (width, height), (12, 18, 32))
            draw = ImageDraw.Draw(img)
            # radial-ish vignetting + subtle stripes for depth
            for y in range(height):
                ratio = y / height
                color = (
                    int(30 + 10 * ratio),
                    int(40 + 12 * ratio),
                    int(70 + 25 * ratio)
                )
                draw.line([(0, y), (width, y)], fill=color)
            # subtle diagonal highlights
            for x in range(0, width, 8):
                alpha = max(0, 40 - (x % 160))
                draw.line([(x, 0), (x-200, height)], fill=(alpha, alpha, alpha))
            fname = f"meme_bg_{int(time.time())}.jpg"
            path = outdir / fname
            img.save(path, quality=92)
            return path

        # Optional auto-retry if OCR detects text in the image
        retry_on_text = bool(data.get('retry_on_text', False))
        retry_max = int(data.get('retry_max', 2))

        def _image_contains_text(path: Path) -> bool:
            try:
                import pytesseract  # type: ignore
            except Exception as _imp_err:
                print(f"[OCR] pytesseract not available, skipping text check: {_imp_err}")
                return False
            try:
                from PIL import Image as _PILImage
                text = pytesseract.image_to_string(_PILImage.open(path))
                alnum = ''.join(ch for ch in text if ch.isalnum())
                return len(alnum) >= 2
            except Exception as _ocr_err:
                print(f"[OCR] Error during OCR: {_ocr_err}")
                return False

        def _vision_detects_text_or_logo(path: Path) -> bool:
            try:
                if not bool(int(os.getenv('ENABLE_BG_VISION_AUDIT', '1'))):
                    return False
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    return False
                from openai import OpenAI
                import base64
                client = OpenAI(api_key=api_key)
                b64 = base64.b64encode(path.read_bytes()).decode('utf-8')
                data_url = f"data:image/{path.suffix.lstrip('.').lower()};base64,{b64}"
                prompt = (
                    "Does this image contain any readable or stylized text, letters, numbers, signage,"
                    " labels, banners, title cards, or recognizable logos/icons (e.g., play button, app UI)?"
                    " Answer with a single word: YES or NO."
                )
                resp = client.chat.completions.create(
                    model=os.getenv('OPENAI_MODEL_SEO', 'gpt-4o-mini'),
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ]}
                    ],
                    temperature=0,
                )
                ans = (resp.choices[0].message.content or '').strip().upper()
                return ans.startswith('Y')
            except Exception as _v_err:
                print(f"[VISION] Audit skipped: {_v_err}")
                return False

        img_path = None
        source = None

        # Resolve whether OpenAI Images are disabled
        dalle_disabled = (
            os.getenv('DISABLE_DALLE', '').lower() in {'1', 'true', 'yes'} or
            os.getenv('OPENAI_IMAGE_MODEL', '').lower() in {'disabled', 'none'}
        )

        # ChatGPT-guided procedural background when DALL·E is disabled
        def _chatgpt_background(outdir: Path) -> Path:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                sys_msg = (
                    "You are a thumbnail design assistant. Output compact JSON describing a background: "
                    "{palette:{bg1:'#0b0f19',bg2:'#101827',accent:'#3b82f6'},gradient:'linear',"
                    "shapes:[{type:'circle',x:0.7,y:0.3,size:220,color:'#2563eb',alpha:0.25}],"
                    "vignette:0.35,noise:0.02}. Do not include any text elements."
                )
                user_ctx = f"Topic: {title}\nHook: {hook}\nDescription: {description}\nKeywords: {key_str}"
                resp = client.chat.completions.create(
                    model=os.getenv('OPENAI_MODEL_SEO','gpt-4o-mini'),
                    messages=[
                        {"role":"system","content":sys_msg},
                        {"role":"user","content":user_ctx}
                    ],
                    temperature=0.7,
                    response_format={"type":"json_object"}
                )
                import json as _json, random as _random
                spec = {}
                try:
                    spec = _json.loads(resp.choices[0].message.content or '{}')
                except Exception:
                    spec = {}

                # Render spec via PIL
                from PIL import Image as _Image, ImageDraw as _ImageDraw
                width, height = 1280, 720
                bg1 = spec.get('palette',{}).get('bg1','#0b0f19')
                bg2 = spec.get('palette',{}).get('bg2','#101827')
                def _hex_to_rgb(h):
                    h = h.lstrip('#')
                    return tuple(int(h[i:i+2],16) for i in (0,2,4)) if len(h)>=6 else (16,24,39)
                img = _Image.new('RGB',(width,height),_hex_to_rgb(bg2))
                draw = _ImageDraw.Draw(img, 'RGBA')
                # gradient
                grad_type = str(spec.get('gradient','linear')).lower()
                c1 = _hex_to_rgb(bg1); c2 = _hex_to_rgb(bg2)
                if grad_type=='radial':
                    cx, cy = width//2, height//2
                    import math
                    max_r = int((width**2+height**2)**0.5/2)
                    for r in range(max_r,0,-1):
                        t = r/max_r
                        col = tuple(int(c1[i]*t + c2[i]*(1-t)) for i in range(3))
                        draw.ellipse((cx-r,cy-r,cx+r,cy+r), fill=col+(255,))
                else:
                    for y in range(height):
                        t = y/height
                        col = tuple(int(c1[i]*(1-t)+c2[i]*t) for i in range(3))
                        draw.line([(0,y),(width,y)], fill=col+(255,))
                # shapes
                for shp in spec.get('shapes',[])[:12]:
                    try:
                        t = (shp.get('type') or 'circle').lower()
                        x = float(shp.get('x',0.5))*width
                        y = float(shp.get('y',0.5))*height
                        size = int(shp.get('size',180))
                        col = _hex_to_rgb(str(shp.get('color','#3b82f6')))
                        alpha = int(255*max(0.0,min(1.0,float(shp.get('alpha',0.2)))))
                        if t=='circle':
                            draw.ellipse((x-size,y-size,x+size,y+size), fill=col+(alpha,))
                        elif t=='stripe':
                            w=size; h2=int(size*0.15)
                            draw.rectangle((x-w,y-h2,x+w,y+h2), fill=col+(alpha,))
                        elif t=='rect':
                            w=size; h2=int(size*0.6)
                            draw.rectangle((x-w,y-h2,x+w,y+h2), fill=col+(alpha,))
                    except Exception:
                        continue
                # vignette
                try:
                    vig = float(spec.get('vignette',0.3))
                    if vig>0:
                        import math
                        for y in range(height):
                            for x in range(width):
                                dx=(x-width/2)/(width/2); dy=(y-height/2)/(height/2)
                                d=min(1.0, (dx*dx+dy*dy)**0.5)
                                a=int(255*vig*d*d)
                                draw.point((x,y), fill=(0,0,0,a))
                except Exception:
                    pass
                # noise (very light)
                try:
                    noise = float(spec.get('noise',0.01))
                    if noise>0:
                        import random as rn
                        for _ in range(int(width*height*0.02)):
                            x = rn.randrange(0,width); y = rn.randrange(0,height)
                            n = rn.randint(0,int(50*noise))
                            draw.point((x,y), fill=(n,n,n,120))
                except Exception:
                    pass

                out = outdir / f"meme_bg_{int(time.time())}.png"
                img.save(out, 'PNG')
                return out
            except Exception as _e:
                print(f"[CHATGPT BG] Fallback due to: {_e}")
                return _gradient_background(outdir)

        try:
            # Debug: log env flags for image generation
            api_key_status = 'set' if os.getenv('OPENAI_API_KEY') else 'NOT SET'
            disable_dalle_raw = os.getenv('DISABLE_DALLE', '')
            image_model = os.getenv('OPENAI_IMAGE_MODEL', '')
            print(f"[generate-meme-bg FLAGS] OPENAI_API_KEY={api_key_status}, OPENAI_IMAGE_MODEL={image_model}, DISABLE_DALLE={disable_dalle_raw}, dalle_disabled={dalle_disabled}")
            try:
                Path('out').mkdir(exist_ok=True)
                with open('out/api_errors.log','a',encoding='utf-8') as _lf:
                    _lf.write(f"\n[generate-meme-bg FLAGS] OPENAI_API_KEY={api_key_status}, OPENAI_IMAGE_MODEL={image_model}, DISABLE_DALLE={disable_dalle_raw}, dalle_disabled={dalle_disabled}\n")
            except Exception:
                pass

            # Use DALL-E if enabled and API key is available
            if os.getenv("OPENAI_API_KEY") and not dalle_disabled:
                print("[BG] Using DALL-E for background generation...")
                bg_prompt = (
                    f"Design a cinematic, high-contrast abstract background for a video thumbnail. "
                    f"Topic: {title}. Hook: {hook}. Description: {description}. Keywords: {key_str}. "
                    f"Mood: bold, modern, subtle depth, soft lighting, safe-zone friendly. "
                    f"Strictly avoid all logos, UI, and iconography (e.g., play buttons). "
                    f"CRITICAL: NO TEXT, NO LETTERS, NO WORDS anywhere in the image."
                )
                img_path = _openai_background(bg_prompt, outdir)
                source = 'openai'
            elif os.getenv("OPENAI_API_KEY") and dalle_disabled:
                # Use ChatGPT-guided procedural background when DALL-E is disabled
                print("[BG] DALL-E disabled, using ChatGPT-guided procedural background...")
                img_path = _chatgpt_background(outdir)
                source = 'chatgpt'
        except Exception as _e:
            print(f"[BG AI] Falling back to gradient: {_e}")
            try:
                import traceback as _tb
                Path('out').mkdir(exist_ok=True)
                with open('out/api_errors.log','a',encoding='utf-8') as _lf:
                    _lf.write("\n[generate-meme-bg ERROR]\n")
                    _lf.write(_tb.format_exc())
            except Exception:
                pass

        if img_path is None:
            img_path = _gradient_background(outdir)
            source = 'gradient'

        # Auto-retry on text if enabled and using AI source
        if retry_on_text and source == 'openai':
            attempts = 0
            while attempts < retry_max and (_image_contains_text(img_path) or _vision_detects_text_or_logo(img_path)):
                attempts += 1
                try:
                    # remove previous image to avoid clutter
                    try:
                        img_path.unlink()
                    except Exception:
                        pass
                    img_path = _openai_background(bg_prompt, outdir)
                except Exception as _re_err:
                    print(f"[BG AI] Retry failed: {_re_err}")
                    break

        from urllib.parse import urljoin
        base = request.host_url if hasattr(request, 'host_url') else 'http://127.0.0.1:5000/'
        url = urljoin(base, f"thumbnails/{img_path.name}") if '://' not in str(img_path) else str(img_path)
        return jsonify({'success': True, 'file': img_path.name, 'url': url, 'source': source})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/generate-clean-bg', methods=['POST'])
def generate_clean_bg():
    """Generate a clean, text-free background image for the meme canvas.

    Body JSON: { title, hook, description, keywords[] }
    Returns: { success, file, url, source }
    """
    try:
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        hook = (data.get('hook') or data.get('angle') or '').strip()
        description = (data.get('description') or '').strip()
        keywords = data.get('keywords') or []
        prompt_override = (data.get('prompt') or '').strip()
        enforce_no_text = bool(data.get('enforce_no_text', False))
        retry_on_text = bool(data.get('retry_on_text', False))
        retry_max = int(data.get('retry_max', 2))
        key_str = ', '.join([str(k) for k in keywords][:10])

        outdir = Path(__file__).parent.parent / 'thumbnails'
        outdir.mkdir(exist_ok=True)

        def _openai_background(prompt: str, outdir: Path) -> Path:
            from openai import OpenAI
            import requests as _req
            import base64 as _b64
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
            resp = client.images.generate(
                model=model,
                prompt=prompt,
                size=os.getenv("OPENAI_IMAGE_SIZE", "1536x1024"),
                quality=os.getenv("OPENAI_IMAGE_QUALITY", "high"),
                response_format="b64_json",
                n=1,
            )
            data0 = resp.data[0]
            content = None
            if hasattr(data0, 'b64_json') and data0.b64_json:
                content = _b64.b64decode(data0.b64_json)
            elif hasattr(data0, 'url') and data0.url:
                image_url = data0.url
                r = _req.get(image_url, timeout=30)
                r.raise_for_status()
                content = r.content
            else:
                raise RuntimeError('Image API returned no url or b64_json')
            fname = f"meme_bg_{int(time.time())}.png"
            path = outdir / fname
            path.write_bytes(content)
            return path

        def _gradient_background(outdir: Path) -> Path:
            width, height = 1280, 720
            img = Image.new('RGB', (width, height), (12, 18, 32))
            draw = ImageDraw.Draw(img)
            for y in range(height):
                ratio = y / height
                color = (
                    int(30 + 10 * ratio),
                    int(40 + 12 * ratio),
                    int(70 + 25 * ratio),
                )
                draw.line([(0, y), (width, y)], fill=color)
            for x in range(0, width, 8):
                alpha = max(0, 40 - (x % 160))
                draw.line([(x, 0), (x-200, height)], fill=(alpha, alpha, alpha))
            fname = f"meme_bg_{int(time.time())}.jpg"
            path = outdir / fname
            img.save(path, quality=92)
            return path

        def _image_contains_text(path: Path) -> bool:
            try:
                import pytesseract  # type: ignore
            except Exception as _imp_err:
                print(f"[OCR] pytesseract not available, skipping text check: {_imp_err}")
                return False
            try:
                from PIL import Image as _PILImage
                text = pytesseract.image_to_string(_PILImage.open(path))
                alnum = ''.join(ch for ch in text if ch.isalnum())
                return len(alnum) >= 2
            except Exception as _ocr_err:
                print(f"[OCR] Error during OCR: {_ocr_err}")
                return False

        def _vision_detects_text_or_logo(path: Path) -> bool:
            try:
                if not bool(int(os.getenv('ENABLE_BG_VISION_AUDIT', '1'))):
                    return False
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    return False
                from openai import OpenAI
                import base64
                client = OpenAI(api_key=api_key)
                b64 = base64.b64encode(path.read_bytes()).decode('utf-8')
                data_url = f"data:image/{path.suffix.lstrip('.').lower()};base64,{b64}"
                prompt = (
                    "Does this image contain any readable or stylized text, letters, numbers, signage,"
                    " labels, banners, title cards, or recognizable logos/icons (e.g., play button, app UI)?"
                    " Answer with a single word: YES or NO."
                )
                resp = client.chat.completions.create(
                    model=os.getenv('OPENAI_MODEL_SEO', 'gpt-4o-mini'),
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ]}
                    ],
                    temperature=0,
                )
                ans = (resp.choices[0].message.content or '').strip().upper()
                return ans.startswith('Y')
            except Exception as _v_err:
                print(f"[VISION] Audit skipped: {_v_err}")
                return False

        img_path = None
        source = None

        # Resolve whether OpenAI Images are disabled
        dalle_disabled = (
            os.getenv('DISABLE_DALLE', '').lower() in {'1', 'true', 'yes'} or
            os.getenv('OPENAI_IMAGE_MODEL', '').lower() in {'disabled', 'none'}
        )

        # Debug: Print environment flags
        api_key_status = 'set' if os.getenv('OPENAI_API_KEY') else 'NOT SET'
        disable_dalle_raw = os.getenv('DISABLE_DALLE', '')
        image_model = os.getenv('OPENAI_IMAGE_MODEL', '')
        print(f"[generate-clean-bg FLAGS] OPENAI_API_KEY={api_key_status}, OPENAI_IMAGE_MODEL={image_model}, DISABLE_DALLE={disable_dalle_raw}, dalle_disabled={dalle_disabled}")

        try:
            if os.getenv("OPENAI_API_KEY") and not dalle_disabled:
                print("[BG] Using DALL-E for clean background generation...")
                if prompt_override:
                    bg_prompt = prompt_override
                    # Substitute common placeholders so the prompt reflects the current topic
                    try:
                        subs = {
                            '{{title}}': title,
                            '{{Title}}': title,
                            '{{hook}}': hook,
                            '{{Hook}}': hook,
                            '{{description}}': description,
                            '{{Description}}': description,
                            '{{keywords}}': key_str,
                            '{{Keywords}}': key_str,
                        }
                        for k, v in subs.items():
                            if k in bg_prompt:
                                bg_prompt = bg_prompt.replace(k, v)
                    except Exception:
                        pass
                else:
                    bg_prompt = (
                        f"Design a cinematic, high-contrast abstract background for a video thumbnail. "
                        f"Topic: {title}. Hook: {hook}. Description: {description}. Keywords: {key_str}. "
                        f"Mood: bold, modern, subtle depth, soft lighting, safe-zone friendly."
                    )
                if enforce_no_text:
                    bg_prompt += (
                        "\nCRITICAL: BACKGROUND ONLY - absolutely no text, words, letters, numbers, typography, signage, labels, logos, icons (including play buttons), UI, or watermarks."
                        " Use abstract shapes, gradients, lighting, and texture only."
                    )
                img_path = _openai_background(bg_prompt, outdir)
                source = 'openai'
            elif os.getenv("OPENAI_API_KEY") and dalle_disabled:
                # ChatGPT-guided procedural background when DALL-E is disabled
                print("[BG] DALL-E disabled, using ChatGPT-guided procedural background...")
                from openai import OpenAI
                client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                sys_msg = (
                    "You are a thumbnail design assistant. Output compact JSON describing a background: "
                    "{palette:{bg1:'#0b0f19',bg2:'#101827',accent:'#3b82f6'},gradient:'linear',"
                    "shapes:[{type:'circle',x:0.7,y:0.3,size:220,color:'#2563eb',alpha:0.25}],"
                    "vignette:0.35,noise:0.02}. Do not include any text elements."
                )
                user_ctx = f"Title: {title}\nHook: {hook}\nDescription: {description}\nKeywords: {key_str}"
                resp = client.chat.completions.create(
                    model=os.getenv('OPENAI_MODEL_SEO','gpt-4o-mini'),
                    messages=[
                        {"role":"system","content":sys_msg},
                        {"role":"user","content":user_ctx}
                    ],
                    temperature=0.7,
                    response_format={"type":"json_object"}
                )
                import json as _json
                try:
                    spec = _json.loads(resp.choices[0].message.content or '{}')
                except Exception:
                    spec = {}
                from PIL import Image as _Image, ImageDraw as _ImageDraw
                width, height = 1280, 720
                def _hex_to_rgb(h):
                    h = str(h or '').lstrip('#')
                    return tuple(int(h[i:i+2],16) for i in (0,2,4)) if len(h)>=6 else (16,24,39)
                bg1 = spec.get('palette',{}).get('bg1','#0b0f19')
                bg2 = spec.get('palette',{}).get('bg2','#101827')
                c1 = _hex_to_rgb(bg1); c2 = _hex_to_rgb(bg2)
                img = _Image.new('RGB',(width,height),c2)
                draw = _ImageDraw.Draw(img, 'RGBA')
                # gradient
                grad_type = str(spec.get('gradient','linear')).lower()
                if grad_type == 'radial':
                    cx, cy = width//2, height//2
                    max_r = int((width**2+height**2)**0.5/2)
                    for r in range(max_r,0,-1):
                        t = r/max_r
                        col = tuple(int(c1[i]*t + c2[i]*(1-t)) for i in range(3))
                        draw.ellipse((cx-r,cy-r,cx+r,cy+r), fill=col+(255,))
                else:
                    for y in range(height):
                        t = y/height
                        col = tuple(int(c1[i]*(1-t)+c2[i]*t) for i in range(3))
                        draw.line([(0,y),(width,y)], fill=col+(255,))
                # shapes
                for shp in spec.get('shapes',[])[:12]:
                    try:
                        t = (shp.get('type') or 'circle').lower()
                        x = float(shp.get('x',0.5))*width
                        y = float(shp.get('y',0.5))*height
                        size = int(shp.get('size',180))
                        col = _hex_to_rgb(str(shp.get('color','#3b82f6')))
                        alpha = int(255*max(0.0,min(1.0,float(shp.get('alpha',0.2)))))
                        if t=='circle':
                            draw.ellipse((x-size,y-size,x+size,y+size), fill=col+(alpha,))
                        elif t=='stripe':
                            w=size; h2=int(size*0.15)
                            draw.rectangle((x-w,y-h2,x+w,y+h2), fill=col+(alpha,))
                        elif t=='rect':
                            w=size; h2=int(size*0.6)
                            draw.rectangle((x-w,y-h2,x+w,y+h2), fill=col+(alpha,))
                    except Exception:
                        continue
                # vignette
                try:
                    vig = float(spec.get('vignette',0.3))
                    if vig>0:
                        for yy in range(height):
                            for xx in range(width):
                                dx=(xx-width/2)/(width/2); dy=(yy-height/2)/(height/2)
                                d=min(1.0, (dx*dx+dy*dy)**0.5)
                                a=int(255*vig*d*d)
                                draw.point((xx,yy), fill=(0,0,0,a))
                except Exception:
                    pass
                # noise
                try:
                    import random as rn
                    nz = float(spec.get('noise',0.01))
                    if nz>0:
                        for _ in range(int(width*height*0.02)):
                            xx = rn.randrange(0,width); yy = rn.randrange(0,height)
                            n = rn.randint(0,int(50*nz))
                            draw.point((xx,yy), fill=(n,n,n,120))
                except Exception:
                    pass
                out = outdir / f"meme_bg_{int(time.time())}.png"
                img.save(out,'PNG')
                img_path = out
                source = 'chatgpt'
        except Exception as _e:
            print(f"[BG AI] Falling back to gradient (clean route): {_e}")
            try:
                import traceback as _tb
                Path('out').mkdir(exist_ok=True)
                with open('out/api_errors.log','a',encoding='utf-8') as _lf:
                    _lf.write("\n[generate-clean-bg ERROR]\n")
                    _lf.write(_tb.format_exc())
            except Exception:
                pass

        if img_path is None:
            img_path = _gradient_background(outdir)
            source = 'gradient'

        # Auto-retry on text if enabled and using AI source
        if retry_on_text and source == 'openai':
            attempts = 0
            while attempts < retry_max and (_image_contains_text(img_path) or _vision_detects_text_or_logo(img_path)):
                attempts += 1
                try:
                    try:
                        img_path.unlink()
                    except Exception:
                        pass
                    img_path = _openai_background(bg_prompt, outdir)
                except Exception as _re_err:
                    print(f"[BG AI] Retry failed (clean route): {_re_err}")
                    break

        from urllib.parse import urljoin
        base = request.host_url if hasattr(request, 'host_url') else 'http://127.0.0.1:5000/'
        url = urljoin(base, f"thumbnails/{img_path.name}")
        return jsonify({'success': True, 'file': img_path.name, 'url': url, 'source': source})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/cleanup-outputs', methods=['POST'])
def cleanup_outputs():
    """Delete older/larger output files to free space.

    JSON body:
      - keep_n: int (default 10)  Keep most recent N files per directory
      - min_mb: int (default 50)  Only delete files larger than this
      - dirs: list[str] (default ['out', 'web/out']) Directories to clean
      - dry_run: bool (default False) If true, don't delete, just report
    """
    try:
        data = request.get_json(silent=True) or {}
        keep_n = int(data.get('keep_n', 10))
        min_mb = int(data.get('min_mb', 50))
        dirs = data.get('dirs', ['out', 'web/out'])
        dry_run = bool(data.get('dry_run', False))

        def human_size(n):
            for unit in ['B','KB','MB','GB','TB']:
                if n < 1024:
                    return f"{n:.1f}{unit}"
                n /= 1024
            return f"{n:.1f}PB"

        def collect_files(root: Path, patterns=("*.mp4", "*.mp3", "*.wav", "*.mov")):
            files = []
            for pat in patterns:
                files.extend(root.rglob(pat))
            # de-dup
            seen = set()
            unique = []
            for p in files:
                if p not in seen:
                    seen.add(p)
                    unique.append(p)
            return unique

        summary = []
        total_deleted = 0
        total_bytes = 0

        for d in dirs:
            root = Path(d)
            if not root.exists():
                summary.append({'dir': str(root), 'deleted': 0, 'freed_bytes': 0, 'skipped': True})
                continue

            files = collect_files(root)
            files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
            candidates = files[keep_n:]
            candidates = [p for p in candidates if p.stat().st_size >= min_mb * 1024 * 1024]

            freed = 0
            deleted = 0
            for p in candidates:
                size = p.stat().st_size
                if not dry_run:
                    try:
                        p.unlink()
                        deleted += 1
                        freed += size
                    except Exception as e:
                        # skip failures but include them in report as 0-deleted
                        continue
            total_deleted += deleted
            total_bytes += freed
            summary.append({
                'dir': str(root),
                'deleted': deleted,
                'freed_bytes': freed,
                'freed_human': human_size(freed),
                'kept': keep_n,
                'threshold_mb': min_mb,
                'dry_run': dry_run
            })

        return jsonify({
            'success': True,
            'deleted_total': total_deleted,
            'freed_bytes_total': total_bytes,
            'freed_human_total': human_size(total_bytes),
            'details': summary
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/list-outputs', methods=['GET'])
def list_outputs():
    """List files in an output directory.

    Query params:
      - dir: directory to list (default 'out')
      - limit: max number of files (default 100)
      - min_mb: only include files of at least this size (MB)
    """
    try:
        base = request.args.get('dir', 'out')
        limit = int(request.args.get('limit', 100))
        min_mb = request.args.get('min_mb', None)
        min_bytes = int(float(min_mb) * 1024 * 1024) if min_mb is not None else 0

        root = Path(base)
        if not root.exists():
            return jsonify({'success': False, 'error': f'Directory not found: {base}'}), 400

        items = []
        for p in root.rglob('*'):
            if p.is_file():
                try:
                    # skip items under any ".trash" folder
                    if any(part == '.trash' for part in p.parts):
                        continue
                    size = p.stat().st_size
                    if size < min_bytes:
                        continue
                    rel = p.relative_to(root).as_posix()
                    items.append({
                        'path': rel,
                        'size': size,
                        'mtime': int(p.stat().st_mtime),
                        'ext': p.suffix.lower(),
                    })
                except Exception:
                    continue

        # Sort by mtime desc and limit
        items.sort(key=lambda x: x['mtime'], reverse=True)
        items = items[:limit]

        return jsonify({'success': True, 'dir': base, 'count': len(items), 'files': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-description', methods=['POST'])
def generate_description():
    """Generate SEO-optimized YouTube description using ChatGPT"""
    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        data = request.get_json()
        title = data.get('title', '')
        hook = data.get('hook', '')
        keywords = data.get('keywords', [])
        main_topic = data.get('main_topic', '')

        if not title:
            return jsonify({'success': False, 'error': 'Title required'}), 400

        # Build the prompt for ChatGPT
        keywords_str = ', '.join(keywords[:10]) if keywords else 'general trending topics'

        prompt = f"""Create a highly engaging, SEO-optimized YouTube video description for the following video:

Title: {title}
{f'Main Topic: {main_topic}' if main_topic else ''}
{f'Specific Angle/Hook: {hook}' if hook else ''}
Key SEO Keywords: {keywords_str}

Requirements:
1. Start with a compelling hook that includes the main topic and angle
2. Use 2-3 of the provided keywords naturally in the first 2 sentences
3. Include sections with emojis:
   - 🎯 What's covered in the video
   - ⏰ Timestamp placeholders (Introduction, Main content, Conclusion)
   - 📌 Key takeaways
4. Call-to-action section (Subscribe, Like, Comment, Share)
5. Related topics/keywords section at the end
6. Include relevant hashtags at the very end (use the title and 4-5 keywords)
7. Keep it between 200-300 words
8. Make it enthusiastic but professional
9. Focus specifically on the hook/angle provided
10. Optimize for YouTube SEO and viewer engagement

Generate ONLY the description text, no explanations or meta-commentary."""

        # Call OpenAI API
        from openai import OpenAI
        api_key = os.getenv('OPENAI_API_KEY')

        if not api_key:
            return jsonify({
                'success': False,
                'error': 'OpenAI API key not configured'
            }), 500

        client = OpenAI(api_key=api_key)

        print(f"[GENERATE-DESC] Generating description for: {title}")
        print(f"[GENERATE-DESC] Hook: {hook}")
        print(f"[GENERATE-DESC] Keywords: {keywords_str}")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert YouTube content strategist specializing in SEO-optimized video descriptions that maximize engagement and discoverability."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=800
        )

        description = response.choices[0].message.content.strip()

        print(f"[GENERATE-DESC] ✓ Generated {len(description)} characters")

        return jsonify({
            'success': True,
            'description': description
        })

    except Exception as e:
        print(f"[GENERATE-DESC] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trends/search', methods=['GET'])
def search_trends():
    """Search for trend info by title"""
    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    title = request.args.get('title', '').strip()
    if not title:
        return jsonify({'success': False, 'error': 'No title provided'}), 400

    try:
        conn = sqlite3.connect('web/mss_users.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Clean and normalize the search title for better matching
        search_title = title.strip()

        # Try exact match first
        c.execute('''
            SELECT title, description, tags, topic_data
            FROM videos
            WHERE user_email = ? AND LOWER(TRIM(title)) = LOWER(?)
            ORDER BY created_at DESC
            LIMIT 1
        ''', (user_email, search_title))

        row = c.fetchone()

        # If no exact match, try partial match (contains)
        if not row:
            c.execute('''
                SELECT title, description, tags, topic_data
                FROM videos
                WHERE user_email = ? AND LOWER(REPLACE(title, ' ', '')) LIKE LOWER(REPLACE(?, ' ', ''))
                ORDER BY created_at DESC
                LIMIT 1
            ''', (user_email, f'%{search_title}%'))

            row = c.fetchone()

        # If still no match, try even more lenient search
        if not row:
            # Remove common words and try matching core keywords
            core_words = ' '.join([w for w in search_title.split() if len(w) > 3])
            if core_words:
                c.execute('''
                    SELECT title, description, tags, topic_data
                    FROM videos
                    WHERE user_email = ? AND LOWER(title) LIKE LOWER(?)
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (user_email, f'%{core_words}%'))

                row = c.fetchone()

        conn.close()

        if row:
            trend_data = {
                'success': True,
                'found': True,
                'title': row['title'],
                'description': row['description'],
                'tags': row['tags'],
                'topic_data': row['topic_data']
            }
        else:
            trend_data = {
                'success': True,
                'found': False,
                'message': 'No matching trend found'
            }

        return jsonify(trend_data)

    except Exception as e:
        print(f"[TRENDS] Error searching trends: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/video/metadata/<path:filename>', methods=['GET', 'POST'])
@app.route('/api/video/metadata/', methods=['POST'])
def get_video_metadata(filename=None):
    """Get or set metadata for a video by filename"""
    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    # Handle POST - save metadata
    if request.method == 'POST':
        try:
            data = request.get_json()
            video_filename = data.get('filename') or filename
            topic_data = data.get('topic_data')

            if not video_filename:
                return jsonify({'success': False, 'error': 'No filename provided'}), 400

            if not topic_data:
                return jsonify({'success': False, 'error': 'No topic_data provided'}), 400

            # Save metadata to sidecar file
            video_path = Path('out') / video_filename
            metadata_path = video_path.with_suffix('.metadata.json')

            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(topic_data, f, indent=2)

            print(f"[METADATA] Saved topic data for {video_filename}")
            return jsonify({'success': True, 'message': 'Metadata saved'})

        except Exception as e:
            print(f"[METADATA] Error saving: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

    # Handle GET - retrieve metadata
    try:
        # First, try to load metadata from sidecar JSON file (preferred method)
        video_path = Path('out') / filename
        metadata_path = video_path.with_suffix('.metadata.json')

        topic_data = None
        db_metadata = None

        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    topic_data = json.load(f)
                print(f"[METADATA] Loaded topic data from {metadata_path}")
            except Exception as e:
                print(f"[METADATA] Error reading metadata file: {e}")

        # Also check database if analytics_manager is available
        if analytics_manager:
            video = analytics_manager.get_video_by_filename(user_email, filename)
            if video:
                db_metadata = {
                    'title': video.get('title', ''),
                    'description': video.get('description', ''),
                    'tags': video.get('tags', ''),
                    'filename': video.get('filename', ''),
                    'created_at': video.get('created_at', '')
                }

                # Try to parse topic_data from database if no sidecar file
                if not topic_data and video.get('topic_data'):
                    try:
                        topic_data = json.loads(video.get('topic_data'))
                    except:
                        pass

        # Return metadata (prioritize database metadata, but always include topic_data)
        if db_metadata or topic_data:
            return jsonify({
                'success': True,
                'metadata': {
                    'title': db_metadata.get('title', '') if db_metadata else '',
                    'description': db_metadata.get('description', '') if db_metadata else '',
                    'tags': db_metadata.get('tags', '') if db_metadata else '',
                    'filename': filename,
                    'created_at': db_metadata.get('created_at', '') if db_metadata else '',
                    'topic_data': topic_data
                }
            })
        else:
            return jsonify({
                'success': True,
                'metadata': None
            })
    except Exception as e:
        print(f"[METADATA] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/webout/<path:filename>', methods=['GET'])
def serve_web_out(filename):
    """Serve files from web/out via API."""
    try:
        web_out_dir = Path('web') / 'out'
        return send_from_directory(web_out_dir, filename)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 404


@app.route('/delete-output', methods=['POST'])
def delete_output():
    """Delete a file from out/ or web/out based on a relative path.

    Body JSON: { dir: 'out'|'web/out', path: 'relative/file.ext' }
    On Windows, if the file is locked (WinError 32), it will be moved to a
    per-dir '.trash' folder as a soft delete.
    """
    try:
        data = request.get_json(silent=True) or {}
        base = (data.get('dir') or 'out').strip()
        rel = (data.get('path') or '').strip()
        if not rel or '..' in rel or rel.startswith('/') or rel.startswith('\\'):
            return jsonify({'success': False, 'error': 'Invalid path'}), 400
        if base not in ('out', 'web/out'):
            return jsonify({'success': False, 'error': 'Invalid dir'}), 400
        root = Path('out') if base == 'out' else (Path('web') / 'out')
        target = (root / rel).resolve()
        # Ensure target is inside root (allow nested paths)
        try:
            inside = target.is_relative_to(root.resolve())
        except Exception:
            inside = str(target).startswith(str(root.resolve()))
        if not inside:
            return jsonify({'success': False, 'error': 'Path outside allowed directory'}), 400
        if not target.exists() or not target.is_file():
            return jsonify({'success': False, 'error': 'File not found'}), 404
        try:
            target.unlink()
            return jsonify({'success': True, 'deleted': rel, 'dir': base})
        except Exception as e:
            # On Windows, locked files raise WinError 32. Fallback: move to .trash
            err = str(e)
            try:
                trash = root / '.trash'
                trash.mkdir(parents=True, exist_ok=True)
                # ensure unique name
                ts = int(time.time())
                candidate = trash / f"{Path(rel).name}"
                if candidate.exists():
                    candidate = trash / f"{ts}_{Path(rel).name}"
                target.replace(candidate)
                return jsonify({'success': True, 'soft_deleted': True, 'from': rel, 'to': str(candidate.relative_to(root)), 'dir': base, 'note': 'Moved to .trash because file was in use', 'error': err})
            except Exception as e2:
                return jsonify({'success': False, 'error': f"{err}; fallback move failed: {e2}"}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/empty-trash', methods=['POST'])
def empty_trash():
    """Empty the .trash folder under the specified directory (out or web/out).

    JSON body: { dir: 'out'|'web/out'|'all', dry_run?: bool }
    Returns a summary of deleted files and freed bytes per directory.
    """
    try:
        data = request.get_json(silent=True) or {}
        which = (data.get('dir') or 'out').strip()
        dry_run = bool(data.get('dry_run', False))

        dirs = []
        if which == 'all':
            dirs = ['out', 'web/out']
        elif which in ('out', 'web/out'):
            dirs = [which]
        else:
            return jsonify({'success': False, 'error': 'Invalid dir'}), 400

        def human_size(n: int) -> str:
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if n < 1024:
                    return f"{n:.1f}{unit}"
                n /= 1024
            return f"{n:.1f}PB"

        results = []
        total_deleted = 0
        total_bytes = 0

        for d in dirs:
            root = Path('out') if d == 'out' else (Path('web') / 'out')
            trash = root / '.trash'
            deleted = 0
            freed = 0
            if trash.exists() and trash.is_dir():
                # delete files first
                for p in sorted(trash.rglob('*'), key=lambda x: len(x.parts), reverse=True):
                    try:
                        if p.is_file():
                            size = p.stat().st_size
                            if not dry_run:
                                try:
                                    p.unlink()
                                except Exception:
                                    # try to rename into a new filename to break locks on Windows
                                    try:
                                        p.replace(p.with_name(f"_del_{int(time.time())}_{p.name}"))
                                        p.unlink(missing_ok=True)
                                    except Exception:
                                        continue
                            deleted += 1
                            freed += size
                        elif p.is_dir():
                            if not dry_run:
                                try:
                                    p.rmdir()
                                except Exception:
                                    # not empty yet or locked; skip
                                    pass
                    except Exception:
                        continue
            total_deleted += deleted
            total_bytes += freed
            results.append({'dir': d, 'deleted': deleted, 'freed_bytes': freed, 'freed_human': human_size(freed), 'dry_run': dry_run})

        return jsonify({'success': True, 'deleted_total': total_deleted, 'freed_bytes_total': total_bytes, 'freed_human_total': human_size(total_bytes), 'details': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def create_dummy_audio(output_path, duration=60):
    """Create a minimal MP3 file for testing"""
    # Create a minimal valid MP3 file with silence
    # This is a workaround - in production, TTS should work
    import struct

    # Write a minimal MP3 header (silent frame)
    with open(output_path, 'wb') as f:
        # MP3 frame header for silence
        f.write(b'\xff\xfb\x90\x00')  # Basic MP3 sync + header
        # Add some silent frames
        for _ in range(duration * 10):  # Rough approximation
            f.write(b'\x00' * 100)
    print(f"Created dummy audio: {output_path}")


def add_thumbnail_text(image_path, text, output_path=None):
    """
    Add YouTube thumbnail-style text to an image
    - First line: YELLOW with BLACK outline
    - Second line: WHITE with BLACK outline
    - Impact font, all caps, centered

    Args:
        image_path: Path to the background image
        text: The text to add (will be split into 2 lines)
        output_path: Where to save (defaults to overwriting input)

    Returns:
        Path to the output image
    """
    if output_path is None:
        output_path = image_path

    # Open image
    img = Image.open(image_path)
    width, height = img.size

    # Resize to YouTube thumbnail size if needed (1280x720)
    target_width, target_height = 1280, 720
    if width != target_width or height != target_height:
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        width, height = target_width, target_height

    draw = ImageDraw.Draw(img)

    # Load Impact font (Windows default)
    font_path = r"C:\Windows\Fonts\impact.ttf"

    # Calculate font size based on image width (about 10% of width for each character)
    # Start with large font and adjust based on text length
    base_font_size = int(width / 12)  # Starting point

    # Split text into 2 lines
    words = text.upper().split()
    mid_point = len(words) // 2

    # Try to balance line lengths
    line1 = ' '.join(words[:mid_point]) if mid_point > 0 else words[0]
    line2 = ' '.join(words[mid_point:]) if len(words) > 1 else ''

    # If only 1-2 words, keep on one line
    if len(words) <= 2:
        line1 = text.upper()
        line2 = ''

    # Load font
    font = ImageFont.truetype(font_path, base_font_size)

    # Function to draw text with outline
    def draw_text_with_outline(text, position, fill_color, outline_color='black', outline_width=8):
        x, y = position
        # Draw outline by drawing the text multiple times with offset
        for adj_x in range(-outline_width, outline_width + 1, 2):
            for adj_y in range(-outline_width, outline_width + 1, 2):
                draw.text((x + adj_x, y + adj_y), text, font=font, fill=outline_color)
        # Draw main text
        draw.text((x, y), text, font=font, fill=fill_color)

    # Calculate text positions (centered)
    # Get bounding boxes
    bbox1 = draw.textbbox((0, 0), line1, font=font)
    text_width1 = bbox1[2] - bbox1[0]
    text_height1 = bbox1[3] - bbox1[1]

    # Position for line 1 (upper third)
    x1 = (width - text_width1) // 2
    y1 = int(height * 0.25)  # 25% from top

    # Draw line 1 (YELLOW)
    draw_text_with_outline(line1, (x1, y1), fill_color='#FFD700', outline_width=10)

    # Draw line 2 (WHITE) if it exists
    if line2:
        bbox2 = draw.textbbox((0, 0), line2, font=font)
        text_width2 = bbox2[2] - bbox2[0]
        text_height2 = bbox2[3] - bbox2[1]

        x2 = (width - text_width2) // 2
        y2 = y1 + text_height1 + 20  # 20px gap between lines

        draw_text_with_outline(line2, (x2, y2), fill_color='white', outline_width=10)

    # Save image
    img.save(output_path, 'PNG')
    print(f"[TEXT OVERLAY] Added text to thumbnail: {output_path}")

    return output_path


# Load environment variables from parent directory
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(env_file)
    print(f"[OK] Loaded .env from: {env_file}")
    print(f"[OK] ENABLE_STOCK_FOOTAGE = {os.getenv('ENABLE_STOCK_FOOTAGE')}")
else:
    print(f"[WARN] .env file not found at: {env_file}")


@app.route('/generate-ai-thumbnail', methods=['POST'])
def generate_ai_thumbnail():
    """Generate multiple thumbnail variants with PIL text overlay.

    Body JSON: { title: str, prompt?: str }
    Returns: { success: bool, thumbnails: [{ variation, url }] }
    """
    try:
        data = request.get_json(force=True) or {}
        title = (data.get('title') or '').strip()
        if not title:
            return jsonify({'success': False, 'error': 'Missing title'}), 400

        # Where to write variants so they can be served via /thumbnails/<file>
        outdir = Path(__file__).parent.parent / 'thumbnails'
        outdir.mkdir(exist_ok=True)

        # Env flag: disable DALL·E image generation (note: generate_thumbnail_variants doesn't use DALL-E)
        dalle_disabled = (
            os.getenv('DISABLE_DALLE', '').lower() in {'1', 'true', 'yes'} or
            os.getenv('OPENAI_IMAGE_MODEL', '').lower() in {'disabled', 'none'}
        )

        # Generate 3 variants using existing utility
        variants = generate_thumbnail_variants(title, outdir, count=3)

        # Build absolute URLs for client consumption
        from urllib.parse import urljoin
        base = request.host_url if hasattr(request, 'host_url') else 'http://127.0.0.1:5000/'
        thumbs = []
        for idx, path in enumerate(variants, start=1):
            thumbs.append({
                'variation': f'variant_{idx}',
                'url': urljoin(base, f'thumbnails/{path.name}')
            })

        return jsonify({'success': True, 'thumbnails': thumbs})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/generate-topics', methods=['GET', 'POST'])
def generate_topics():
    """Generate AI-powered video topics.

    Body JSON: { brand, seed, limit, prompt? }
    If 'prompt' is provided, it will be used to guide generation; otherwise
    falls back to the default implementation in scripts.make_video.
    """
    try:
        if request.method == 'GET':
            brand = (request.args.get('brand') or 'Many Sources Say').strip()
            seed = (request.args.get('seed') or '').strip()
            limit = int(request.args.get('limit') or 5)
            prompt = (request.args.get('prompt') or '').strip()
        else:
            data = request.get_json(silent=True) or {}
            brand = (data.get('brand') or 'Many Sources Say').strip()
            seed = (data.get('seed') or '').strip()
            limit = int(data.get('limit') or 5)
            prompt = (data.get('prompt') or '').strip()

        print(f"Generating {limit} topics for brand: {brand}" + (f" with seed: {seed}" if seed else "") + (" using custom prompt" if prompt else ""))

        source = 'openai'
        model = os.getenv('OPENAI_MODEL_SEO', 'gpt-4o-mini')

        try:
            if prompt:
                topics = _generate_topics_with_prompt(brand, seed, prompt)
            else:
                topics = openai_generate_topics(brand, seed)
        except Exception as gen_err:
            # Fallback to mock topics for local testing when OpenAI is unavailable
            print(f"[WARN] Topic generation failed, falling back to mock: {gen_err}")
            topics = _generate_mock_topics(brand, seed)
            source = 'mock'
            model = None

        # Limit results
        topics = topics[:limit]

        # Ring bell to notify completion
        print('\a')  # ASCII bell character

        payload = {
            'success': True,
            'topics': topics,
            'count': len(topics),
            'source': source,
            'model': model,
            'used_prompt': bool(prompt),
            'brand': brand,
            'seed': seed,
            'limit': limit,
            'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        resp = jsonify(payload)
        try:
            resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
        except Exception:
            pass
        return resp

    except Exception as e:
        print(f"Error generating topics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _generate_topics_with_prompt(brand: str, seed: str, prompt: str):
    """Generate topics using a custom user prompt.

    The prompt may contain placeholders like {{brand}}. Seed, if provided,
    is appended as an additional constraint to keep results on-topic.
    Returns a normalized list of up to 5 items with keys:
      title, angle, keywords[], yt_title, yt_description, yt_tags[], outline
    """
    from openai import OpenAI
    import os, json as _json
    from datetime import datetime, timezone

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Prepare prompt with substitutions
    user_prompt = prompt.replace("{{brand}}", brand)
    if seed:
        user_prompt += f"\nFocus all topics on: {seed}."
    user_prompt += ("\n\nReturn JSON only with key 'topics': ["
                    "{ title, angle, keywords, yt_title, yt_description, yt_tags, outline } ]")

    system = (
        "You are a senior research editor and SEO strategist."
        f" Today's date is {today}."
        " Identify timely, factual video topics relevant to the current year and recent events."
        " Optimize for YouTube SEO with clear search intent."
    )

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_SEO", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        response_format={"type": "json_object"},
    )
    content = completion.choices[0].message.content
    payload = _json.loads(content)
    topics = payload.get("topics") or payload.get("items") or []
    if not isinstance(topics, list) or not topics:
        raise RuntimeError("OpenAI topics response missing 'topics' array")
    norm = []
    for t in topics[:5]:
        norm.append({
            "title": t.get("title"),
            "angle": t.get("angle"),
            "keywords": t.get("keywords", []),
            "yt_title": t.get("yt_title") or t.get("title"),
            "yt_description": t.get("yt_description") or "",
            "yt_tags": t.get("yt_tags", []),
            "outline": t.get("outline", []),
        })
    return norm


def _generate_mock_topics(brand: str, seed: str):
    """Return 5 placeholder topics without external APIs (local testing)."""
    import random
    base = seed if seed else 'AI'
    ideas = [
        f"{base} Trends {n}" for n in [1, 2, 3, 4, 5]
    ]
    topics = []
    for title in ideas:
        topics.append({
            'title': f"{brand}: {title}",
            'angle': 'Timely overview with key takeaways',
            'keywords': [base, 'news', 'analysis', 'tips', '2025'],
            'yt_title': f"{title} ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â What You Need to Know",
            'yt_description': f"Quick breakdown of {title} for {brand}.",
            'yt_tags': [base, 'trends', 'explained', brand],
            'outline': [
                'Context and why it matters',
                'Latest updates',
                'Impacts and opportunities',
                'Practical tips',
                'Key sources to follow',
            ],
        })
    return topics


@app.route('/create-video', methods=['POST'])
def create_video():
    """Create a video from a chosen topic"""
    try:
        data = request.get_json()
        topic = data.get('topic')
        include_avatar = bool(data.get('include_avatar', True))
        include_logo = bool(data.get('include_logo', True))
        print(f"[OPTIONS] include_avatar={include_avatar}, include_logo={include_logo}")

        if not topic:
            return jsonify({
                'success': False,
                'error': 'No topic provided'
            }), 400

        # Check usage limits if user is logged in
        session_id = request.cookies.get('session_id')
        if session_id:
            session_result = database.get_session(session_id)
            if session_result['success']:
                user_id = session_result['user']['id']

                # Check if user can create video
                can_create = database.can_create_video(user_id)
                if not can_create['allowed']:
                    return jsonify({
                        'success': False,
                        'error': can_create['error'],
                        'usage': can_create.get('stats')
                    }), 403

        print(f"Creating video for topic: {topic.get('title')}")

        outdir = Path("out")
        ensure_dir(outdir)

        # Save selected topic
        (outdir / "topic_selected.json").write_text(
            json.dumps(topic, indent=2),
            encoding="utf-8"
        )

        # Draft script from topic
        print("Drafting script...")
        draft = openai_draft_from_topic(topic)
        (outdir / "script.json").write_text(
            json.dumps(draft, indent=2),
            encoding="utf-8"
        )

        title = draft["title"]
        narration = draft["narration"]
        overlays = draft["overlays"]

        # Create dummy audio for testing (no TTS)
        print("Creating test audio...")
        audio_path = outdir / "voiceover.mp3"
        mp3_data = bytes([
            0xFF, 0xFB, 0x90, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ] * 5000)
        audio_path.write_bytes(mp3_data)

        # Generate thumbnails
        print("Generating thumbnails...")
        thumb_variants = generate_thumbnail_variants(title, outdir, count=3)

        # Increment usage counter if user is logged in
        if session_id:
            session_result = database.get_session(session_id)
            if session_result['success']:
                user_id = session_result['user']['id']
                database.increment_video_count(user_id)
                print(f"[USAGE] Incremented video count for user {user_id}")

        # Return success with file paths
        return jsonify({
            'success': True,
            'output_dir': str(outdir.absolute()),
            'files': {
                'script': 'script.json',
                'audio': 'voiceover.mp3 (test/silent)',
                'thumbnails': len(thumb_variants),
                'thumbnail_files': [t.name for t in thumb_variants]
            },
            'message': 'Video components created! (TTS, rendering, and upload require additional setup)'
        })

    except Exception as e:
        print(f"Error creating video: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/preview-script', methods=['POST'])
def preview_script():
    """Preview the script without generating full video"""
    try:
        data = request.get_json()
        topic = data.get('topic')

        if not topic:
            return jsonify({'success': False, 'error': 'No topic provided'}), 400

        print(f"Previewing script for: {topic.get('title')}")

        # Apply custom header/footer if provided
        custom_header = topic.get('custom_header', '')
        custom_footer = topic.get('custom_footer', '')
        full_prompt = topic.get('full_prompt', '')

        # Draft script (use full_prompt if edited, otherwise build from parts)
        draft = openai_draft_from_topic_custom(topic, custom_header, custom_footer, full_prompt)

        return jsonify({
            'success': True,
            'narration': draft['narration'],
            'overlays': draft['overlays'],
            'word_count': len(draft['narration'].split()),
            'title': draft['title']
        })

    except Exception as e:
        print(f"Error previewing script: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/create-video-enhanced', methods=['POST'])
def create_video_enhanced():
    """Create video with custom prompts and AI thumbnail"""
    print("\n" + "="*70)
    print("[VIDEO] CREATE-VIDEO-ENHANCED ENDPOINT CALLED")
    print("="*70)
    try:
        data = request.get_json()
        topic = data.get('topic')

        if not topic:
            return jsonify({'success': False, 'error': 'No topic provided'}), 400

        print(f"Creating enhanced video for: {topic.get('title')}")

        outdir = Path("out")
        ensure_dir(outdir)

        # Save selected topic
        (outdir / "topic_selected.json").write_text(
            json.dumps(topic, indent=2),
            encoding="utf-8"
        )

        # Apply custom prompts
        custom_header = topic.get('custom_header', '')
        custom_footer = topic.get('custom_footer', '')
        full_prompt = topic.get('full_prompt', '')

        # Draft script (or use custom narration if provided)
        if topic.get('narration'):
            # Use custom edited narration
            print("Using custom edited narration...")
            draft = openai_draft_from_topic_custom(topic, custom_header, custom_footer, full_prompt)
            # Override narration with the user's edited version
            draft["narration"] = topic.get('narration')
            print(f"Custom narration length: {len(draft['narration'])} characters")
        else:
            # Generate new narration
            print("Drafting script with custom prompts...")
            draft = openai_draft_from_topic_custom(topic, custom_header, custom_footer, full_prompt)

        (outdir / "script.json").write_text(
            json.dumps(draft, indent=2),
            encoding="utf-8"
        )

        title = draft["title"]

        # Generate TTS voiceover
        print("=" * 50)
        print("ATTEMPTING GOOGLE TTS...")
        print(f"GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
        audio_path = outdir / "voiceover.mp3"
        try:
            google_tts(draft["narration"], audio_path, use_ssml=True)
            print(f"[OK] SUCCESS: Voiceover generated at {audio_path}")
            print(f"[OK] File size: {audio_path.stat().st_size} bytes")
        except Exception as e:
            print(f"[X] TTS FAILED: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'TTS generation failed: {str(e)}'}), 500
        print("=" * 50)

        # Generate standard thumbnails
        print("Generating standard thumbnails...")
        thumb_variants = generate_thumbnail_variants(title, outdir, count=3)

        result_files = {
            'script': 'script.json',
            'audio': 'voiceover.mp3 (test/silent)',
            'thumbnails': len(thumb_variants),
            'thumbnail_files': [t.name for t in thumb_variants]
        }

        # Get stock footage if enabled
        stock_videos = []
        visual_cues = draft.get("visual_cues", draft.get("keywords", []))[:3]

        # Reload .env to ensure we have latest values
        from dotenv import load_dotenv
        env_file = Path(__file__).parent.parent / ".env"
        load_dotenv(env_file, override=True)

        # Debug logging
        enable_stock = os.getenv("ENABLE_STOCK_FOOTAGE", "")
        with open("out/debug.log", "a", encoding="utf-8") as f:
            f.write(f"\n=== Video Generation Debug ===\n")
            f.write(f"ENABLE_STOCK_FOOTAGE env: {enable_stock}\n")
            f.write(f"Keywords from script: {draft.get('keywords', [])}\n")
            f.write(f"Visual cues to use: {visual_cues}\n")

        if enable_stock.lower() in {"true", "1", "yes"}:
            print(f"Fetching stock footage for: {', '.join(visual_cues)}...")
            try:
                stock_videos = get_stock_footage_for_keywords(visual_cues, max_clips=3)
                print(f"Found {len(stock_videos)} stock video clips")
                with open("out/debug.log", "a", encoding="utf-8") as f:
                    f.write(f"Stock videos found: {stock_videos}\n")
            except Exception as e:
                print(f"Stock footage error: {e}")
                with open("out/debug.log", "a", encoding="utf-8") as f:
                    f.write(f"Stock footage ERROR: {e}\n")
        else:
            with open("out/debug.log", "a", encoding="utf-8") as f:
                f.write(f"Stock footage DISABLED\n")

        # Use a fixed duration for testing (60 seconds)
        # Get actual audio duration
        duration = get_mp3_duration_seconds(audio_path)
        print(f"Audio duration: {duration:.1f}s")

        # Upload audio to Google Drive (public)
        print("Uploading audio to Google Drive...")
        try:
            # OAuth approach - will open browser first time for authorization
            audio_upload = drive_upload_public(audio_path, "MSS_Audio")
            audio_url = audio_upload["download_url"]
            print(f"[OK] Audio uploaded to Drive: {audio_url}")
        except FileNotFoundError as e:
            print(f"[WARN] Drive upload failed: {e}")
            print(f"[WARN] Please set up Google Drive OAuth (see SETUP_GOOGLE_DRIVE.md)")
            print(f"[WARN] Falling back to Shotstack example music")
            audio_url = "https://shotstack-assets.s3-ap-southeast-2.amazonaws.com/music/disco.mp3"
            duration = 60
        except Exception as e:
            print(f"[WARN] Drive upload error: {e}")
            print(f"[WARN] Falling back to Shotstack example music")
            audio_url = "https://shotstack-assets.s3-ap-southeast-2.amazonaws.com/music/disco.mp3"
            duration = 60

        # Get overlays from draft
        overlays = draft.get("overlays", [])
        print(f"Rendering with {len(stock_videos)} stock videos: {stock_videos}")

        # Render videos (will use FFmpeg or Shotstack based on VIDEO_RENDERER env var)
        print("Submitting renders...")
        try:
            from concurrent.futures import ThreadPoolExecutor

            def render_and_poll(aspect_ratio, format_name):
                print(f"Rendering {format_name}...")
                video_path = outdir / f"{format_name}.mp4"

                result = render_video(
                    audio_path=str(audio_path),
                    overlays=overlays,
                    total_secs=duration,
                    title=title,
                    output_path=str(video_path),
                    stock_videos=stock_videos,
                    aspect_ratio=aspect_ratio
                )

                # Check if FFmpeg (synchronous) or Shotstack (needs polling)
                if result.get("status") == "done":
                    # FFmpeg - video is already rendered
                    print(f"[OK] {format_name} rendered with FFmpeg: {video_path}")
                    return {"render_id": "ffmpeg", "url": str(video_path), "path": video_path.name}
                else:
                    # Shotstack - need to poll
                    print(f"Shotstack submit response: {json.dumps(result, indent=2)}")

                    if not result.get("success", True):
                        error_msg = result.get("message") or result.get("error") or "Unknown error"
                        raise Exception(f"Shotstack submission failed: {error_msg}")

                    render_id = result.get("response", {}).get("id") or result.get("id")
                    if not render_id:
                        raise Exception(f"No render ID returned: {result}")

                    print(f"{format_name} render ID: {render_id}")

                    final = shotstack_poll(render_id, timeout_s=600, interval_s=5)
                    print(f"Shotstack poll response: {json.dumps(final, indent=2)}")

                    url = final.get("response", {}).get("url") or final.get("url")
                    if not url:
                        raise Exception(f"No video URL returned: {final}")

                    # Download video
                    import requests
                    print(f"Downloading {format_name} from {url}...")
                    with requests.get(url, stream=True, timeout=300) as r:
                        r.raise_for_status()
                        with video_path.open("wb") as f:
                            for chunk in r.iter_content(8192):
                                if chunk:
                                    f.write(chunk)

                    print(f"[OK] {format_name} saved to {video_path}")
                    return {"render_id": render_id, "url": url, "path": video_path.name}

            # Render both formats in parallel
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_vertical = executor.submit(render_and_poll, "9:16", "shorts")
                future_wide = executor.submit(render_and_poll, "16:9", "wide")

                result_vertical = future_vertical.result()
                result_wide = future_wide.result()

            print("[OK] Both renders completed!")
            result_files['shorts'] = result_vertical['path']
            result_files['wide'] = result_wide['path']
            result_files['render_ids'] = {
                'vertical': result_vertical['render_id'],
                'wide': result_wide['render_id']
            }

            # If using Shotstack, add logo overlay locally post-download
            try:
                include_logo = bool(data.get('include_logo', True))
            except Exception:
                include_logo = True

            if include_logo:
                def _resolve_logo_path(ui_filename: str = "", default_position: str = 'bottom-left'):
                    """Return (logo_path, position) using UI override, web library, then thumbnail_settings.json."""
                    logo_position = default_position
                    logo_path = None
                    try:
                        # 1) Explicit UI selection
                        if ui_filename:
                            cand_mss = Path(__file__).parent.parent / 'logos' / ui_filename
                            cand_web = Path(__file__).parent / 'logos' / ui_filename
                            logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
                        # 2) Active logo from web/logo_library.json
                        if not logo_path:
                            library_file = Path(__file__).parent / 'logo_library.json'
                            if library_file.exists():
                                lib = json.loads(library_file.read_text(encoding='utf-8'))
                                active = next((l for l in lib.get('logos', []) if l.get('active')), None)
                                if active:
                                    fname = active.get('filename') or (active.get('url','').split('/')[-1])
                                    if fname:
                                        cand_mss = Path(__file__).parent.parent / 'logos' / fname
                                        cand_web = Path(__file__).parent / 'logos' / fname
                                        logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
                        # 3) Position (and fallback) from root thumbnail_settings.json
                        ts_path = Path(__file__).parent.parent / 'thumbnail_settings.json'
                        if ts_path.exists():
                            ts = json.loads(ts_path.read_text(encoding='utf-8'))
                            logo_position = ts.get('logoPosition', logo_position)
                            if not logo_path and ts.get('logoUrl'):
                                fname = ts.get('logoUrl').split('/')[-1]
                                cand_mss = Path(__file__).parent.parent / 'logos' / fname
                                cand_web = Path(__file__).parent / 'logos' / fname
                                logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
                    except Exception:
                        pass
                    return logo_path, logo_position

                def _overlay_logo(input_path: Path, output_path: Path, logo_path: Path, position: str, opacity: float = 1.0) -> bool:
                    """Apply a PNG logo over video using ffmpeg. Returns True on success."""
                    try:
                        import subprocess, imageio_ffmpeg
                        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                        pos_map = {
                            'bottom-right': 'W-w-20:H-h-20',
                            'bottom-left': '20:H-h-20',
                            'top-right': 'W-w-20:20',
                            'top-left': '20:20',
                            'center': '(W-w)/2:(H-h)/2'
                        }
                        pos = pos_map.get(position, '20:H-h-20')
                        filter_complex = (
                            f"[1:v]scale=-1:110,scale=iw*1.25:ih,format=rgba,geq=a='if(gt(a,0),255,0)'[logo];"
                            f"[0:v][logo]overlay={pos}"
                        )
                        cmd = [
                            ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(input_path),
                            '-i', str(logo_path),
                            '-filter_complex', filter_complex,
                            '-c:v', 'libx264',
                            '-c:a', 'copy',
                            '-map', '0:a?',
                            '-y', str(output_path)
                        ]
                        res = subprocess.run(cmd, capture_output=True, text=True)
                        if res.returncode == 0 and output_path.exists():
                            return True
                        else:
                            print(f"[LOGO] Overlay failed for {input_path.name}: {res.stderr[:200] if res.stderr else 'no stderr'}")
                            return False
                    except Exception as e:
                        print(f"[LOGO] Exception during overlay: {e}")
                        return False

                # Resolve logo once (optionally from UI)
                ui_logo_filename = (data.get('logo_filename') or '').strip() if isinstance(data, dict) else ''
                logo_path, logo_position = _resolve_logo_path(ui_logo_filename)

                if logo_path and logo_path.exists():
                    print(f"[LOGO] Applying logo to Shotstack renders using {logo_path} at {logo_position}")
                    for key in ['shorts', 'wide']:
                        try:
                            in_path = outdir / result_files[key]
                            out_path = outdir / f"{Path(result_files[key]).stem}_logo.mp4"
                            if _overlay_logo(in_path, out_path, logo_path, logo_position, opacity=1.0):
                                result_files[key] = out_path.name
                                print(f"[LOGO] {key} updated with logo -> {out_path.name}")
                        except Exception as e:
                            print(f"[LOGO] Skipped {key} overlay: {e}")
                else:
                    print("[LOGO] No logo file resolved; skipping logo overlay for Shotstack outputs")

        except Exception as e:
            print(f"Shotstack rendering error: {e}")
            import traceback
            error_trace = traceback.format_exc()
            traceback.print_exc()
            result_files['render_error'] = str(e)
            result_files['render_error_details'] = error_trace

            # Return error immediately instead of continuing
            return jsonify({
                'success': False,
                'error': f'Video rendering failed: {str(e)}',
                'details': error_trace,
                'partial_files': result_files
            }), 500

        # Generate AI thumbnail if requested
        if topic.get('generate_ai_thumbnail') and not (
            os.getenv('DISABLE_DALLE', '').lower() in {'1', 'true', 'yes'} or
            os.getenv('OPENAI_IMAGE_MODEL', '').lower() in {'disabled', 'none'}
        ):
            print("Generating AI thumbnail with DALL-E...")
            try:
                ai_thumb_path = generate_dalle_thumbnail(title, outdir)
                result_files['ai_thumbnail'] = ai_thumb_path.name
            except Exception as e:
                print(f"AI thumbnail generation failed: {e}")
                result_files['ai_thumbnail_error'] = str(e)

        # Ring bell to notify video completion
        print('\a')  # ASCII bell character

        return jsonify({
            'success': True,
            'output_dir': str(outdir.absolute()),
            'files': result_files,
            'narration': draft.get('narration', ''),
            'title': draft.get('title', ''),
            'message': 'Video generation complete! Check the output directory for MP4 files.'
        })

    except Exception as e:
        print(f"Error creating enhanced video: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/post-process-video', methods=['POST'])
def post_process_video():
    """
    POST-PROCESSING MODE:
    Upload an existing video -> Add talking avatar + intro/outro -> Get final video

    Accepts:
    - video: Video file (MP4)
    - audio (optional): Audio file (MP3) - if not provided, extract from video
    - intro_text (optional): Custom intro text
    - outro_text (optional): Custom outro text
    - use_did (optional): Use D-ID for talking avatar (default: true)
    """
    try:
        # Safe logger to avoid Windows console encoding errors
        def _log(msg: str):
            try:
                __builtins__['print'](msg)
            except Exception:
                try:
                    __builtins__['print'](str(msg).encode('ascii', 'ignore').decode('ascii'))
                except Exception:
                    pass

        # Sanitize any filename provided by UI
        def _sanitize_basename(name: str) -> str:
            try:
                if not name:
                    return ''
                base = Path(name).name  # drop directories
                allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
                return ''.join(ch for ch in base if ch in allowed)
            except Exception:
                return ''

        # Route-local print override for safe logging
        print = _log

        print("=" * 70)
        print("[VIDEO] POST-PROCESS VIDEO ENDPOINT CALLED")
        print("=" * 70)

        # Check user authentication and limits (optional - works without login too)
        user_id = None
        session_id = request.cookies.get('session_id')
        if session_id:
            session_result = database.get_session(session_id)
            if session_result['success']:
                user_id = session_result['user']['id']
                print(f"[AUTH] User logged in: ID {user_id}")

                # Check if user can create video
                can_create = database.can_create_video(user_id)
                if not can_create['allowed']:
                    return jsonify({
                        'success': False,
                        'error': can_create['reason'],
                        'upgrade_required': True
                    }), 403
                remaining = (can_create.get('remaining') or (can_create.get('stats') or {}).get('videos_remaining') or 'unlimited')
                print(f'[AUTH] User can create video; remaining={remaining}')
            else:
                print("[AUTH] Session expired or invalid")
        else:
            print("[AUTH] No session - processing as guest")

        # Get uploaded files
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': 'No video file uploaded'}), 400

        video_file = request.files['video']
        audio_file = request.files.get('audio', None)

        # Get options
        # Historically 'use_did' doubled as "include avatar" toggle from the UI.
        # Keep existing behavior but add an explicit 'avatar_static' flag to skip any animation/D-ID.
        use_did_flag = request.form.get('use_did', 'true').lower() == 'true'
        include_avatar = use_did_flag
        avatar_static = request.form.get('avatar_static', 'false').lower() == 'true'
        skip_did = request.form.get('skip_did', 'false').lower() == 'true'
        intro_text = request.form.get('intro_text', '')
        outro_text = request.form.get('outro_text', '')
        add_intro_outro = request.form.get('add_intro_outro', 'true').lower() == 'true'
        # Save uploaded video
        outdir = Path("out")
        ensure_dir(outdir)

        def _save_upload(fs, dest: Path):
            try:
                fs.save(str(dest))
            except Exception as e:
                print(f"[UPLOAD] .save failed for {dest}: {e}. Falling back to manual copy...")
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if hasattr(fs, 'stream') and fs.stream:
                        try:
                            fs.stream.seek(0)
                        except Exception:
                            pass
                        with open(str(dest), 'wb') as out_f:
                            shutil.copyfileobj(fs.stream, out_f)
                    else:
                        data = fs.read()
                        with open(str(dest), 'wb') as out_f:
                            out_f.write(data)
                except Exception as e2:
                    raise e2

        video_path = outdir / f"uploaded_video_{int(time.time())}.mp4"
        _save_upload(video_file, video_path)
        _log(f"[OK] Video saved: {video_path}")

        # If no processing requested (no avatar, no intro/outro), return the uploaded video
        try:
            include_logo_flag = request.form.get('include_logo', 'true').lower() == 'true'
        except Exception:
            include_logo_flag = True
        _log(f"[OPTIONS] include_avatar={include_avatar}, include_logo={include_logo_flag}, add_intro_outro={add_intro_outro}")
        if (not include_avatar) and (not add_intro_outro):
            # Optionally apply logo and return immediately
            final_return = video_path
            if include_logo_flag:
                ui_logo_filename = _sanitize_basename((request.form.get('logo_filename') or '').strip())
                logo_path = None
                # Prefer an uploaded logo file if provided
                try:
                    logo_upload = request.files.get('logo_file')
                    if logo_upload:
                        logos_dir = Path(__file__).parent.parent / 'logos'
                        logos_dir.mkdir(exist_ok=True)
                        up_name = f"uploaded_logo_{int(time.time())}.png"
                        up_path = logos_dir / up_name
                        logo_upload.save(str(up_path))
                        if up_path.exists() and up_path.stat().st_size > 0:
                            logo_path = up_path
                            _log(f"[LOGO-NOOP] Using uploaded logo file: {up_path}")
                except Exception as _e:
                    _log(f"[LOGO-NOOP] Upload logo save failed: {_e}")
                if ui_logo_filename:
                    cand_mss = Path(__file__).parent.parent / 'logos' / ui_logo_filename
                    cand_web = Path(__file__).parent / 'logos' / ui_logo_filename
                    logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
                if not logo_path:
                    # Fallback to thumbnail settings
                    ts_path = Path(__file__).parent.parent / 'thumbnail_settings.json'
                    if ts_path.exists():
                        try:
                            ts = json.loads(ts_path.read_text(encoding='utf-8'))
                            lu = ts.get('logoUrl') or ''
                            if lu:
                                fname = lu.split('/')[-1]
                                cand_mss = Path(__file__).parent.parent / 'logos' / fname
                                cand_web = Path(__file__).parent / 'logos' / fname
                                logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
                        except Exception:
                            pass
                if logo_path and logo_path.exists():
                    try:
                        from scripts.overlay_logo import overlay as overlay_logo
                        out_file = overlay_logo(str(video_path), str(logo_path), (request.form.get('logo_position') or 'bottom-left'))
                        out_path = Path(str(out_file))
                        if out_path.exists():
                            final_return = out_path
                            _log(f"[LOGO-NOOP] Applied logo and returning: {out_path}")
                    except Exception as e:
                        _log(f"[LOGO-NOOP] Overlay failed, returning original: {e}")
            return jsonify({
                'success': True,
                'message': 'Video post-processed successfully (no intro/outro)',
                'files': {
                    'final_video': final_return.name,
                    'avatar_video': None
                }
            })

        # Handle audio
        if audio_file:
            audio_path = outdir / f"uploaded_audio_{int(time.time())}.mp3"
            _save_upload(audio_file, audio_path)
            print(f"[OK] Audio saved: {audio_path}")
        else:
            # Extract audio from video using FFmpeg
            print("[EXTRACT] Extracting audio from video...")
            import subprocess
            import imageio_ffmpeg

            audio_path = outdir / f"extracted_audio_{int(time.time())}.mp3"
            try:
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except OSError as oe:
                return jsonify({'success': False, 'error': f'FFmpeg not available: {oe}'}), 500

            cmd = [
                ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(video_path),
                '-vn',  # No video
                '-acodec', 'mp3',
                '-y',
                str(audio_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return jsonify({'success': False, 'error': f'Audio extraction failed: {result.stderr}'}), 500

            print(f"[OK] Audio extracted: {audio_path}")

        # Get audio duration
        duration = get_mp3_duration_seconds(audio_path)
        print(f"[OK] Audio duration: {duration:.1f}s")

        # Start with the uploaded video as our working clip
        current_video = video_path

        # Apply LOGO FIRST so we keep branding even if avatar step fails
        logo_already_applied = False
        try:
            include_logo_early = request.form.get('include_logo', 'true').lower() == 'true'
            print(f"[LOGO-FIRST] ========== LOGO PROCESSING START ==========")
            print(f"[LOGO-FIRST] include_logo_early: {include_logo_early}")
            if include_logo_early:
                logo_url = None
                # Allow UI to pass an explicit filename and/or position
                ui_logo_filename = _sanitize_basename((request.form.get('logo_filename') or '').strip())
                ui_logo_position = (request.form.get('logo_position') or '').strip()
                print(f"[LOGO-FIRST] UI provided: logo_filename='{ui_logo_filename}', logo_position='{ui_logo_position}'")
                logo_position = ui_logo_position if ui_logo_position else 'bottom-left'
                # 1) Try UI override (filename or uploaded file), then active logo from web/logo_library.json
                logo_path = None
                # Uploaded logo file has highest priority
                try:
                    logo_upload = request.files.get('logo_file')
                    if logo_upload:
                        logos_dir = Path(__file__).parent.parent / 'logos'
                        logos_dir.mkdir(exist_ok=True)
                        up_name = f"uploaded_logo_{int(time.time())}.png"
                        up_path = logos_dir / up_name
                        logo_upload.save(str(up_path))
                        if up_path.exists() and up_path.stat().st_size > 0:
                            logo_path = up_path
                            print(f"[LOGO-FIRST] Using uploaded logo file: {up_path}")
                except Exception as _e:
                    print(f"[LOGO-FIRST] Upload logo save failed: {_e}")
                if ui_logo_filename:
                    cand_mss = Path(__file__).parent.parent / 'logos' / ui_logo_filename
                    print(f"[LOGO-FIRST] UI override => MSS: {cand_mss.exists()} {cand_mss}")
                    logo_path = cand_mss if cand_mss.exists() else None
                    print(f"[LOGO-FIRST] Selected logo_path from UI: {logo_path}")
                # Only check library if UI didn't provide a logo
                if not logo_path:
                    library_file = Path(__file__).parent / 'logo_library.json'
                    if library_file.exists():
                        try:
                            lib = json.loads(library_file.read_text(encoding='utf-8'))
                            active = next((l for l in lib.get('logos', []) if l.get('active')), None)
                            if active:
                                fname = active.get('filename') or (active.get('url','').split('/')[-1])
                                if fname:
                                    cand_mss = Path(__file__).parent.parent / 'logos' / fname
                                    print(f"[LOGO-FIRST] Candidates => MSS: {cand_mss.exists()} {cand_mss}")
                                    logo_path = cand_mss if cand_mss.exists() else None
                        except Exception:
                            pass
                # 2) Position from thumbnail settings (ignore its logoUrl if file missing)
                ts_path = Path(__file__).parent.parent / "thumbnail_settings.json"
                if ts_path.exists():
                    try:
                        ts = json.loads(ts_path.read_text(encoding='utf-8'))
                        logo_position = ui_logo_position or ts.get('logoPosition', logo_position)
                        if not logo_path:
                            lu = ts.get('logoUrl') or ''
                            if lu:
                                fname = lu.split('/')[-1]
                                cand_mss = Path(__file__).parent.parent / 'logos' / fname
                                print(f"[LOGO-FIRST] Candidates => MSS: {cand_mss.exists()} {cand_mss}")
                                logo_path = cand_mss if cand_mss.exists() else None
                    except Exception:
                        pass
                if logo_path and logo_path.exists():
                    print(f"[LOGO-FIRST] ? Logo file found! Applying logo before avatar: {logo_path}")
                    logo_opacity = request.form.get('logo_opacity', '1.0')
                    try:
                        logo_opacity_val = max(0.0, min(1.0, float(logo_opacity)))
                    except Exception:
                        logo_opacity_val = 1.0
                    if logo_path and logo_path.exists():
                        print(f"[LOGO-FIRST] Starting ffmpeg logo overlay...")
                        import subprocess, imageio_ffmpeg
                        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                        position_map = {
                            'bottom-right': 'W-w-20:H-h-20',
                            'bottom-left': '20:H-h-20',
                            'top-right': 'W-w-20:20',
                            'top-left': '20:20',
                            'center': '(W-w)/2:(H-h)/2'
                        }
                        pos = position_map.get(logo_position, '20:H-h-20')
                        print(f"[LOGO-FIRST] Logo position: {logo_position} -> {pos}")
                        print(f"[LOGO-FIRST] Logo opacity: {logo_opacity_val}")
                        # Force fully opaque logo inside non-transparent regions, widen 25%, h=110
                        filter_complex = (
                            f"[1:v]scale=-1:110,scale=iw*1.25:ih,format=rgba,geq=a='if(gt(a,0),255,0)'[logo];"
                            f"[0:v][logo]overlay={pos}"
                        )
                        print(f"[LOGO-FIRST] Filter: {filter_complex}")
                        video_with_logo = outdir / f"video_with_logo_{int(time.time())}.mp4"
                        cmd = [
                            ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(current_video),
                            '-i', str(logo_path),
                            '-filter_complex', filter_complex,
                            '-c:v', 'libx264',
                            '-c:a', 'copy',
                            '-map', '0:a?',
                            '-y', str(video_with_logo)
                        ]
                        print(f"[LOGO-FIRST] Running ffmpeg command...")
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        print(f"[LOGO-FIRST] ffmpeg return code: {result.returncode}")
                        if result.returncode != 0:
                            print(f"[LOGO-FIRST] ? ffmpeg ERROR: {result.stderr}")
                        if result.returncode == 0 and video_with_logo.exists():
                            current_video = video_with_logo
                            logo_already_applied = True
                            print(f"[LOGO-FIRST] ? Logo applied successfully! Video: {video_with_logo}")
                        else:
                            print(f"[LOGO-FIRST] ? Logo application failed!")
                            print(f"[LOGO-FIRST] Logo overlay failed, continuing without early logo: {result.stderr[:300] if result.stderr else 'no stderr'}")
                else:
                    print(f"[LOGO-FIRST] ? No logo_path found or file doesn't exist")
        except Exception as e:
            print(f"[LOGO-FIRST] Exception while applying early logo: {e}")

        # Prepare audio for D-ID (will upload directly to D-ID, no Drive needed)
        if include_avatar and (not avatar_static) and (not skip_did):
            if not os.getenv('DID_API_KEY'):
                print("[AVATAR] Skipping D-ID: DID_API_KEY not set")
                skip_did = True
                audio_url = None
            else:
                # Pass local file path - generate_did_talking_avatar will upload to D-ID
                audio_url = str(audio_path)
                print(f"[AVATAR] Using local audio file for D-ID: {audio_url}")
        else:
            audio_url = None

        # Import additional functions we need
        from scripts.make_video import create_intro_outro_clips, create_avatar_clip, generate_did_talking_avatar
        from scripts.ffmpeg_render import create_intro_video, create_outro_video

        # Generate avatar if requested
        avatar_video_path = None
        selected_avatar = None  # Store the selected avatar for later use
        pre_applied_video = None  # If we directly composite onto base video

        # Check if user specified avatar ID preference
        avatar_id = request.form.get('avatar_id', None)
        print(f"[DEBUG] include_avatar={include_avatar}, avatar_static={avatar_static}, avatar_id={avatar_id}, DID_API_KEY exists={bool(os.getenv('DID_API_KEY'))}")

        if include_avatar:
            # Get avatar library
            # Avatar library is in parent directory (MSS/avatar_library.json)
            avatar_library_file = Path(__file__).parent.parent / "avatar_library.json"
            print(f"[DEBUG] Looking for avatar library at: {avatar_library_file}")
            print(f"[DEBUG] Avatar library exists: {avatar_library_file.exists()}")

            if avatar_library_file.exists():
                library = json.loads(avatar_library_file.read_text(encoding="utf-8"))
                print(f"[DEBUG] Found {len(library.get('avatars', []))} avatars in library")

                # Try to find avatar by ID
                if avatar_id:
                    selected_avatar = next((x for x in library.get('avatars', []) if x.get('id') == avatar_id), None)
                    if selected_avatar:
                        print(f"[AVATAR] User-selected avatar: {selected_avatar.get('name')} ({selected_avatar.get('gender')})")
                    else:
                        print(f"[AVATAR] Avatar ID {avatar_id} not found, falling back to auto-select")
                        selected_avatar = None

                # Fallback to auto-detection from voice in .env
                if not selected_avatar:
                    voice_name = os.getenv("TTS_VOICE_NAME", "en-US-Neural2-C")

                    # Determine voice gender from voice name patterns
                    avatar_gender = 'female'
                    # Male voice indicators: J, B, Q, L, D, A in voice names
                    male_indicators = ['J', 'B', 'Q', 'L', 'D', 'A']
                    voice_upper = voice_name.upper()

                    for indicator in male_indicators:
                        if f'-{indicator}' in voice_upper or voice_upper.endswith(f'-{indicator}'):
                            avatar_gender = 'male'
                            break

                    print(f"[AVATAR] Auto-detecting from .env voice: {voice_name} -> {avatar_gender}")

                    # Try to find avatar matching gender
                    selected_avatar = next((x for x in library.get('avatars', []) if x.get('gender') == avatar_gender), None)

                # Final fallback to any active avatar
                if not selected_avatar:
                    selected_avatar = next((x for x in library.get('avatars', []) if x.get('active')), None)
                    print(f"[AVATAR] Using active avatar as fallback")

                if selected_avatar:
                    avatar_filename = selected_avatar['image_url'].split('/')[-1]
                    # Avatar files are in parent directory (MSS/avatars)
                    avatar_local_path = Path(__file__).parent.parent / "avatars" / avatar_filename
                    print(f"[AVATAR] Using avatar: {selected_avatar.get('name')} ({selected_avatar.get('gender')})")
                    print(f"[AVATAR] Avatar path: {avatar_local_path}")

                    if avatar_local_path.exists():
                        if avatar_static:
                            # Static overlay directly on the base video; no D-ID, no animated clip
                            try:
                                print("[AVATAR] Applying static avatar overlay...")
                                from scripts.avatar_animator import add_avatar_to_video
                                static_out = outdir / f"video_with_avatar_{int(time.time())}.mp4"
                                add_avatar_to_video(
                                    base_video_path=current_video,
                                    avatar_image_path=avatar_local_path,
                                    output_path=static_out,
                                    avatar_position=selected_avatar.get('position', 'bottom-right'),
                                    avatar_scale=selected_avatar.get('scale', 25) / 100.0,
                                    animate=False
                                )
                                if static_out.exists():
                                    pre_applied_video = static_out
                                    print(f"[OK] Static avatar overlay created (pre-applied): {pre_applied_video}")
                            except Exception as e:
                                print(f"[!] Static avatar overlay failed: {e}")
                                avatar_video_path = None
                        else:
                            # Try D-ID first if not skipped and key exists
                            if (not skip_did) and os.getenv("DID_API_KEY"):
                                print("[AVATAR] Generating talking avatar with D-ID...")
                                avatar_video_path = outdir / f"did_avatar_{int(time.time())}.mp4"
                                result = generate_did_talking_avatar(
                                    str(avatar_local_path),
                                    audio_url,
                                    avatar_video_path
                                )

                                if result and avatar_video_path.exists():
                                    file_size = avatar_video_path.stat().st_size
                                    print(f"[OK] D-ID talking avatar generated: {avatar_video_path}")
                                    print(f"[OK] Avatar file size: {file_size} bytes")
                                    if file_size < 1000:
                                        print(f"[!] Avatar file suspiciously small, falling back to FFmpeg")
                                        avatar_video_path = None
                                else:
                                    print("[!] D-ID generation failed, falling back to FFmpeg animation")
                                    avatar_video_path = None

                            # Fallback (or forced) FFmpeg-based animation if D-ID is skipped/unavailable/failed
                            if not avatar_video_path:
                                print("[AVATAR] Using FFmpeg-based avatar animation (direct overlay)...")
                                from scripts.avatar_animator import add_avatar_to_video
                                try:
                                    pre_out = outdir / f"video_with_avatar_{int(time.time())}.mp4"
                                    add_avatar_to_video(
                                        base_video_path=current_video,
                                        avatar_image_path=avatar_local_path,
                                        output_path=pre_out,
                                        avatar_position=selected_avatar.get('position', 'bottom-right'),
                                        avatar_scale=selected_avatar.get('scale', 25) / 100.0,
                                        animate=True
                                    )
                                    if pre_out.exists():
                                        pre_applied_video = pre_out
                                        print(f"[OK] Animated avatar overlaid: {pre_applied_video}")
                                except Exception as e:
                                    print(f"[!] FFmpeg animated overlay failed: {e}")
                    else:
                        print(f"[!] Avatar file not found: {avatar_local_path}")
                else:
                    print("[!] No avatar found in library")
            else:
                print("[INFO] Avatar library file not found")

        # Add avatar overlay to video
        print("[COMPOSITE] Creating final video...")
        print(f"[DEBUG] Avatar video path: {avatar_video_path}")
        print(f"[DEBUG] Avatar exists: {Path(avatar_video_path).exists() if avatar_video_path else False}")
        print(f"[DEBUG] Selected avatar: {selected_avatar}")

        if pre_applied_video and Path(pre_applied_video).exists():
            video_with_avatar = pre_applied_video
            current_video = video_with_avatar
        elif avatar_video_path and Path(avatar_video_path).exists():
            # Overlay avatar on original video
            print("[OVERLAY] Overlaying talking avatar on video...")
            import subprocess
            import imageio_ffmpeg

            video_with_avatar = outdir / f"video_with_avatar_{int(time.time())}.mp4"
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

            # Use the avatar that was already selected based on gender
            # Don't re-fetch from library - that would ignore the gender matching!
            position = selected_avatar.get('position', 'bottom-right') if selected_avatar else 'bottom-right'
            scale = selected_avatar.get('scale', 25) / 100.0 if selected_avatar else 0.25

            # Position mapping for FFmpeg
            position_map = {
                'bottom-right': 'W-w-20:H-h-20',
                'bottom-left': '20:H-h-20',
                'top-right': 'W-w-20:20',
                'top-left': '20:20',
                'center': '(W-w)/2:(H-h)/2'
            }
            pos = position_map.get(position, 'W-w-20:H-h-20')

            # Avoid PiP of the same source; if avatar clip equals base, skip overlay
            try:
                same_source = (Path(avatar_video_path).resolve() == Path(current_video).resolve())
            except Exception:
                same_source = False
            if same_source:
                print("[OVERLAY] Avatar video equals base video; skipping overlay")
            else:
                # Overlay avatar on video
                # eof_action=pass means if avatar ends, continue with main video (avatar will fade out)
                filter_complex = f"[1:v]scale=iw*{scale}:ih*{scale}[avatar];[0:v][avatar]overlay={pos}:eof_action=pass"

                cmd = [
                    ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(current_video),
                    '-i', str(avatar_video_path),
                    '-filter_complex', filter_complex,
                    '-c:v', 'libx264',
                    '-c:a', 'aac',  # Re-encode audio to ensure compatibility
                    '-map', '0:a',  # Use audio from main video (input 0), not avatar
                    '-y',
                    str(video_with_avatar)
                ]

            print(f"[DEBUG] Avatar overlay command:")
            print(f"[DEBUG] FFmpeg: {ffmpeg}")
            print(f"[DEBUG] Main video: {current_video} (size: {Path(current_video).stat().st_size} bytes)")
            print(f"[DEBUG] Avatar video: {avatar_video_path} (size: {Path(avatar_video_path).stat().st_size} bytes)")
            print(f"[DEBUG] Filter: {filter_complex}")
            print(f"[DEBUG] Position: {position}, Scale: {scale}")
            print(f"[DEBUG] Output: {video_with_avatar}")

            result = subprocess.run(cmd, capture_output=True, text=True)

            print(f"[DEBUG] FFmpeg return code: {result.returncode}")
            if result.stdout:
                print(f"[DEBUG] FFmpeg stdout: {result.stdout[:500]}")
            if result.stderr:
                print(f"[DEBUG] FFmpeg stderr: {result.stderr[:500]}")

            if same_source:
                video_with_avatar = current_video
            elif result.returncode != 0:
                print(f"[!] Avatar overlay FAILED")
                print(f"[!] Full error: {result.stderr}")
                video_with_avatar = current_video
            else:
                if video_with_avatar.exists():
                    print(f"[OK] Avatar overlay SUCCESS")
                    print(f"[OK] Output size: {video_with_avatar.stat().st_size} bytes")
                    print(f"[OK] Video with avatar: {video_with_avatar}")
                else:
                    print(f"[!] Avatar overlay claimed success but file not found!")
                    video_with_avatar = current_video
        else:
            video_with_avatar = current_video
            # Try a last-resort static overlay directly onto the base video
            try:
                if selected_avatar and avatar_local_path and avatar_local_path.exists():
                    print("[OVERLAY] Animated avatar failed; applying static avatar overlay to base video...")
                    from scripts.avatar_animator import add_avatar_to_video
                    static_out = outdir / f"video_with_avatar_{int(time.time())}.mp4"
                    add_avatar_to_video(
                        base_video_path=current_video,
                        avatar_image_path=avatar_local_path,
                        output_path=static_out,
                        avatar_position=selected_avatar.get('position', 'bottom-right'),
                        avatar_scale=selected_avatar.get('scale', 25) / 100.0,
                        animate=False
                    )
                    if static_out.exists():
                        video_with_avatar = static_out
                        print(f"[OK] Static avatar overlay created: {video_with_avatar}")
            except Exception as e:
                print(f"[!] Static avatar overlay also failed: {e}")

        # Add logo overlay to video (late pass) if not already applied
        include_logo = request.form.get('include_logo', 'true').lower() == 'true'
        print(f"[LOGO] Late logo overlay... include_logo={include_logo} already_applied={logo_already_applied}")
        current_video = video_with_avatar

        if include_logo and (not logo_already_applied):
            # Resolve from UI override, then active library; use thumbnail settings only for position/fallback
            ui_logo_filename = (request.form.get('logo_filename') or '').strip()
            ui_logo_position = (request.form.get('logo_position') or '').strip()
            logo_position = ui_logo_position if ui_logo_position else 'bottom-left'
            logo_path = None
            if ui_logo_filename:
                cand_mss = Path(__file__).parent.parent / 'logos' / ui_logo_filename
                print(f"[LOGO-LATE] UI override => MSS: {cand_mss.exists()} {cand_mss}")
                logo_path = cand_mss if cand_mss.exists() else None
            # Active logo (check repo root and web/)
            if not logo_path:
                for library_file in [Path('logo_library.json'), Path(__file__).parent / 'logo_library.json']:
                    if not library_file.exists():
                        continue
                    try:
                        lib = json.loads(library_file.read_text(encoding='utf-8'))
                        active = next((l for l in lib.get('logos', []) if l.get('active')), None)
                        if active:
                            fname = active.get('filename') or (active.get('url','').split('/')[-1])
                            if fname:
                                for d in [Path(__file__).parent.parent / 'logos', Path(__file__).parent / 'logos', Path(__file__).parent / 'logos_migrated']:
                                    cand = d / fname
                                    print(f"[LOGO-LATE] Candidates => {cand.exists()} {cand}")
                                    if cand.exists():
                                        logo_path = cand
                                        break
                        if logo_path:
                            break
                    except Exception:
                        continue
            # Position / fallback URL
            ts_path = Path(__file__).parent.parent / 'thumbnail_settings.json'
            if ts_path.exists():
                try:
                    ts = json.loads(ts_path.read_text(encoding='utf-8'))
                    logo_position = ts.get('logoPosition', logo_position)
                    if not logo_path and ts.get('logoUrl'):
                        fname = ts.get('logoUrl').split('/')[-1]
                        for d in [Path(__file__).parent.parent / 'logos', Path(__file__).parent / 'logos', Path(__file__).parent / 'logos_migrated']:
                            cand = d / fname
                            print(f"[LOGO-LATE] Candidates => {cand.exists()} {cand}")
                            if cand.exists():
                                logo_path = cand
                                break
                except Exception:
                    pass
            if logo_path and logo_path.exists():
                print(f"[LOGO] Logo file found: {logo_path}")
                import subprocess
                import imageio_ffmpeg
                video_with_logo = outdir / f"video_with_logo_{int(time.time())}.mp4"
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                position_map = {
                    'bottom-right': 'W-w-20:H-h-20',
                    'bottom-left': '20:H-h-20',
                    'top-right': 'W-w-20:20',
                    'top-left': '20:20',
                    'center': '(W-w)/2:(H-h)/2'
                }
                pos = position_map.get(logo_position, '20:H-h-20')
                # Allow UI to control opacity; default to 1.0 (fully opaque)
                logo_opacity = request.form.get('logo_opacity', '1.0')
                try:
                    logo_opacity_val = max(0.0, min(1.0, float(logo_opacity)))
                except Exception:
                    logo_opacity_val = 1.0
                filter_complex = (
                    f"[1:v]scale=-1:110,scale=iw*1.25:ih,format=rgba,geq=a='if(gt(a,0),255,0)'[logo];"
                    f"[0:v][logo]overlay={pos}"
                )
                cmd = [
                    ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(current_video),
                    '-i', str(logo_path),
                    '-filter_complex', filter_complex,
                    '-c:v', 'libx264',
                    '-c:a', 'copy',  # Copy audio without re-encoding
                    '-map', '0:a?',
                    '-y',
                    str(video_with_logo)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0 and video_with_logo.exists():
                    print(f"[OK] Logo overlay SUCCESS")
                    current_video = video_with_logo
                else:
                    print(f"[!] Logo overlay FAILED (late)")

        # Update video path to include logo overlay if applied
        video_with_avatar = current_video

        # Create intro and outro videos
        print("[INTRO/OUTRO] Creating intro and outro videos...")
        import subprocess
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

        # If intro/outro are disabled, skip and return the current video
        if not add_intro_outro:
            print("[INFO] Skipping intro/outro per request flag")

            # Track usage for logged-in users
            if user_id:
                title = request.form.get('title', 'Untitled Video')
                database.increment_video_count(user_id)
                database.add_video_to_history(user_id, video_with_avatar.name, title)
                print(f"[AUTH] Video counted for user {user_id}")

            return jsonify({
                'success': True,
                'message': 'Video post-processed successfully (no intro/outro)',
                'files': {
                    'final_video': video_with_avatar.name,
                    'avatar_video': avatar_video_path.name if avatar_video_path else None
                }
            })

        # Robustly get video dimensions from the main video (ffprobe with fallback)
        import re
        import json as _json
        from pathlib import Path as _Path2

        def _find_ffprobe(_ffmpeg_path: str) -> str | None:
            try:
                import shutil as _shutil
                cand = _shutil.which('ffprobe')
                if cand:
                    return cand
                try:
                    p = _Path2(_ffmpeg_path).parent / ('ffprobe.exe' if os.name == 'nt' else 'ffprobe')
                    if p.exists():
                        return str(p)
                except Exception:
                    pass
            except Exception:
                pass
            return None

        def _get_video_dims(_path: _Path2) -> tuple[int, int] | None:
            ffprobe = _find_ffprobe(ffmpeg)
            if ffprobe:
                cmd = [
                    ffprobe,
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height',
                    '-of', 'json',
                    str(_path)
                ]
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode == 0 and r.stdout:
                    try:
                        d = _json.loads(r.stdout)
                        s = (d.get('streams') or [{}])[0]
                        w = int(s.get('width') or 0)
                        h = int(s.get('height') or 0)
                        if w and h:
                            return w, h
                    except Exception:
                        pass
            # Fallback: parse ffmpeg probe output
            probe_cmd = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(_path), '-hide_banner']
            probe_result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            m = re.search(r'Video:.*?(\d{3,})x(\d{3,})', probe_result.stdout)
            if not m:
                m = re.search(r'(\d{3,})x(\d{3,})', probe_result.stdout)
            if m:
                return int(m.group(1)), int(m.group(2))
            return None

        dims = _get_video_dims(video_with_avatar)
        if dims:
            width, height = dims
        else:
            # Default to common portrait size if all probes fail
            width, height = 1080, 1920

        print(f"[INFO] Video dimensions: {width}x{height}")

        # Load active intro/outro from library
        # Prefer new library at ./intro_outro/library.json, then legacy ./intro_outro_library.json
        active_intro = None
        active_outro = None
        # Legacy path (items may have `active: true` inline)
        legacy_lib = Path(__file__).parent.parent / "intro_outro_library.json"
        # New path (separate active map { intro, outro })
        new_lib = Path('intro_outro') / 'library.json'

        print(f"[DEBUG] Looking for intro/outro libraries: new={new_lib}, legacy={legacy_lib}")
        try:
            def _resolve_active(lib: dict, which: str, desired_id: str | None):
                items = lib.get(which, []) or []
                # 1) match by id from active map
                if desired_id:
                    hit = next((x for x in items if x.get('id') == desired_id), None)
                    if hit:
                        return hit
                # 2) any item marked active: true
                hit = next((x for x in items if x.get('active')), None)
                if hit:
                    return hit
                # 3) match by name if active map stored name
                if desired_id:
                    hit = next((x for x in items if (x.get('name') or '').strip() == str(desired_id).strip()), None)
                    if hit:
                        return hit
                return None

            if new_lib.exists():
                lib = json.loads(new_lib.read_text(encoding='utf-8') or '{}')
                act = (lib.get('active') or {}) if isinstance(lib, dict) else {}
                intro_id = act.get('intro')
                outro_id = act.get('outro')
                ai = _resolve_active(lib, 'intros', intro_id)
                ao = _resolve_active(lib, 'outros', outro_id)
                if ai:
                    active_intro = ai
                if ao:
                    active_outro = ao
            if (not active_intro or not active_outro) and legacy_lib.exists():
                legacy = json.loads(legacy_lib.read_text(encoding='utf-8') or '{}')
                if not active_intro:
                    active_intro = _resolve_active(legacy, 'intros', None)
                if not active_outro:
                    active_outro = _resolve_active(legacy, 'outros', None)
        except Exception as e:
            print(f"[WARN] Could not load intro/outro libraries: {e}")

        if active_intro:
            print(f"[INTRO] Active intro: {active_intro.get('name')}")
        else:
            print(f"[INTRO] No active intro selected; will use defaults")
        if active_outro:
            print(f"[OUTRO] Active outro: {active_outro.get('name')}")
        else:
            print(f"[OUTRO] No active outro selected; will use defaults")

        # UI override: simple intro/outro text if provided
        try:
            if intro_text and intro_text.strip():
                t = intro_text.strip()
                active_intro = (active_intro or {})
                active_intro.setdefault('name', 'UI Intro')
                active_intro['html'] = f"<div style='display:flex;align-items:center;justify-content:center;height:100%;'><div style='text-align:center;color:#E8EBFF;'><h1 style='color:#FFD700;margin:0;'>{t}</h1></div></div>"
                active_intro.setdefault('duration', 3.0)
                print(f"[INTRO] Overriding with UI intro text")
            if outro_text and outro_text.strip():
                t2 = outro_text.strip()
                active_outro = (active_outro or {})
                active_outro.setdefault('name', 'UI Outro')
                active_outro['html'] = f"<div style='display:flex;align-items:center;justify-content:center;height:100%;'><div style='text-align:center;color:#E8EBFF;'><h1 style='color:#FFD700;margin:0;'>{t2}</h1><div style='margin-top:8px;opacity:0.8;'>MANY SOURCES SAY</div></div></div>"
                active_outro.setdefault('duration', 3.0)
                print(f"[OUTRO] Overriding with UI outro text")
        except Exception:
            pass

        # Create intro video
        intro_path = outdir / f"intro_{int(time.time())}.mp4"

        # Prefer uploaded intro if provided
        uploaded_intro = request.files.get('intro_video')
        if uploaded_intro:
            uploaded_intro.save(intro_path)
            print(f"[INTRO] Using uploaded intro file: {intro_path}")
        elif active_intro and active_intro.get('videoUrl'):
            # Use uploaded video file
            print(f"[INTRO] Using uploaded video: {active_intro.get('videoUrl')}")
            # Download video from URL if it's a remote URL
            intro_url = active_intro['videoUrl']

            if intro_url.startswith('http'):
                # Extract filename from URL and check local file first
                import shutil
                local_intro_path = Path(intro_url.replace('http://localhost:5000/', ''))
                print(f"[DEBUG] Checking for local intro file: {local_intro_path}")

                if local_intro_path.exists():
                    shutil.copy(local_intro_path, intro_path)
                    print(f"[OK] Intro copied from local file: {intro_path}")
                else:
                    # Try downloading from URL
                    print(f"[INTRO] Local file not found, trying to download from URL")
                    import requests
                    try:
                        intro_download = requests.get(intro_url, timeout=10)
                        intro_download.raise_for_status()
                        intro_path.write_bytes(intro_download.content)
                        print(f"[OK] Intro downloaded: {intro_path}")
                    except Exception as e:
                        print(f"[WARN] Failed to download intro: {e}, creating default")
                        create_intro_video(intro_path, {}, 3.0, width, height, ffmpeg)
            else:
                # Local file path
                import shutil
                local_intro_path = Path(intro_url)
                if local_intro_path.exists():
                    shutil.copy(local_intro_path, intro_path)
                    print(f"[OK] Intro copied: {intro_path}")
                else:
                    print(f"[WARN] Intro file not found: {local_intro_path}, creating default")
                    create_intro_video(intro_path, {}, 3.0, width, height, ffmpeg)
        elif active_intro and active_intro.get('html'):
            # Generate from HTML template, prefer HTML->Video capture
            print(f"[INTRO] Generating from HTML template (HTML->Video if available)")
            try:
                intro_cfg = dict(active_intro)
                tts_path = None
                if active_intro.get('audio'):
                    try:
                        tts_path = outdir / f"intro_audio_{int(time.time())}.mp3"
                        google_tts(active_intro['audio'], tts_path)
                        if not (tts_path.exists() and tts_path.stat().st_size > 100):
                            tts_path = None
                    except Exception as e:
                        print(f"[WARN] Intro TTS failed: {e}")

                # Try Playwright-based HTML capture
                try:
                    from scripts.html_to_video import render_html_to_video
                    render_html_to_video(
                        intro_cfg.get('html', ''),
                        float(intro_cfg.get('duration', 3.0) or 3.0),
                        width,
                        height,
                        intro_path,
                        ffmpeg,
                        tts_audio_path=tts_path,
                    )
                    print(f"[OK] Intro rendered via HTML capture: {intro_path}")
                except Exception as e:
                    print(f"[WARN] HTML capture failed for intro: {e}. Falling back to ffmpeg text.")
                    if tts_path:
                        intro_cfg['audio_file'] = str(tts_path)
                    create_intro_video(intro_path, intro_cfg, intro_cfg.get('duration', 3.0), width, height, ffmpeg)
                if intro_path.exists():
                    print(f"[OK] Intro created from HTML: {intro_path} ({intro_path.stat().st_size} bytes)")
                else:
                    print(f"[WARN] HTML intro generation failed, using default")
                    create_intro_video(intro_path, {}, 3.0, width, height, ffmpeg)
            except Exception as e:
                print(f"[ERROR] Failed to create intro from HTML: {e}")
                print(f"[INTRO] Falling back to default intro")
                create_intro_video(intro_path, {}, 3.0, width, height, ffmpeg)
        else:
            # Use default intro
            print(f"[INTRO] No active intro found, using default HTML template")
            create_intro_video(intro_path, {}, 3.0, width, height, ffmpeg)
            print(f"[OK] Default intro created: {intro_path}")

        # Create outro video
        outro_path = outdir / f"outro_{int(time.time())}.mp4"

        # Prefer uploaded outro if provided
        uploaded_outro = request.files.get('outro_video')
        if uploaded_outro:
            uploaded_outro.save(outro_path)
            print(f"[OUTRO] Using uploaded outro file: {outro_path}")
        elif active_outro and active_outro.get('videoUrl'):
            # Use uploaded video file
            print(f"[OUTRO] Using uploaded video: {active_outro.get('videoUrl')}")
            outro_url = active_outro['videoUrl']

            if outro_url.startswith('http'):
                # Extract filename from URL and check local file first
                import shutil
                local_outro_path = Path(outro_url.replace('http://localhost:5000/', ''))
                print(f"[DEBUG] Checking for local outro file: {local_outro_path}")

                if local_outro_path.exists():
                    shutil.copy(local_outro_path, outro_path)
                    print(f"[OK] Outro copied from local file: {outro_path}")
                else:
                    # Try downloading from URL
                    print(f"[OUTRO] Local file not found, trying to download from URL")
                    import requests
                    try:
                        outro_download = requests.get(outro_url, timeout=10)
                        outro_download.raise_for_status()
                        outro_path.write_bytes(outro_download.content)
                        print(f"[OK] Outro downloaded: {outro_path}")
                    except Exception as e:
                        print(f"[WARN] Failed to download outro: {e}, creating default")
                        create_outro_video(outro_path, {}, 3.0, width, height, ffmpeg)
            else:
                # Local file path
                import shutil
                local_outro_path = Path(outro_url)
                if local_outro_path.exists():
                    shutil.copy(local_outro_path, outro_path)
                    print(f"[OK] Outro copied: {outro_path}")
                else:
                    print(f"[WARN] Outro file not found: {local_outro_path}, creating default")
                    create_outro_video(outro_path, {}, 3.0, width, height, ffmpeg)
        elif active_outro and active_outro.get('html'):
            # Generate from HTML template, prefer HTML->Video capture
            print(f"[OUTRO] Generating from HTML template (HTML->Video if available)")
            try:
                outro_cfg = dict(active_outro)
                tts_path = None
                if active_outro.get('audio'):
                    try:
                        tts_path = outdir / f"outro_audio_{int(time.time())}.mp3"
                        google_tts(active_outro['audio'], tts_path)
                        if not (tts_path.exists() and tts_path.stat().st_size > 100):
                            tts_path = None
                    except Exception as e:
                        print(f"[WARN] Outro TTS failed: {e}")

                # Try Playwright-based HTML capture
                try:
                    from scripts.html_to_video import render_html_to_video
                    render_html_to_video(
                        outro_cfg.get('html', ''),
                        float(outro_cfg.get('duration', 3.0) or 3.0),
                        width,
                        height,
                        outro_path,
                        ffmpeg,
                        tts_audio_path=tts_path,
                    )
                    print(f"[OK] Outro rendered via HTML capture: {outro_path}")
                except Exception as e:
                    print(f"[WARN] HTML capture failed for outro: {e}. Falling back to ffmpeg text.")
                    if tts_path:
                        outro_cfg['audio_file'] = str(tts_path)
                    create_outro_video(outro_path, outro_cfg, outro_cfg.get('duration', 3.0), width, height, ffmpeg)
                if outro_path.exists():
                    print(f"[OK] Outro created from HTML: {outro_path} ({outro_path.stat().st_size} bytes)")
                else:
                    print(f"[WARN] HTML outro generation failed, using default")
                    create_outro_video(outro_path, {}, 3.0, width, height, ffmpeg)
            except Exception as e:
                print(f"[ERROR] Failed to create outro from HTML: {e}")
                print(f"[OUTRO] Falling back to default outro")
                create_outro_video(outro_path, {}, 3.0, width, height, ffmpeg)
        else:
            # Use default outro
            print(f"[OUTRO] No active outro found, using default HTML template")
            create_outro_video(outro_path, {}, 3.0, width, height, ffmpeg)
            print(f"[OK] Default outro created: {outro_path}")

        # Ensure intro and outro match the main video dimensions
        print("[RESIZE] Ensuring intro/outro match main video dimensions...")

        def resize_video_if_needed(input_path, output_path, target_width, target_height):
            """Resize video to target dimensions if they don't match"""
            # Get current dimensions via robust probe
            dims_local = _get_video_dims(input_path)
            if dims_local:
                current_width, current_height = dims_local

                if current_width != target_width or current_height != target_height:
                    print(f"[RESIZE] Resizing {input_path.name} from {current_width}x{current_height} to {target_width}x{target_height}")
                    resize_cmd = [
                        ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(input_path),
                        '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2',
                        '-c:v', 'libx264',
                        '-c:a', 'aac',
                        '-y',
                        str(output_path)
                    ]
                    resize_result = subprocess.run(resize_cmd, capture_output=True, text=True)
                    if resize_result.returncode == 0:
                        print(f"[OK] Resized: {output_path}")
                        return output_path
                    else:
                        print(f"[WARN] Resize failed, using original: {resize_result.stderr[:200]}")
                        return input_path
                else:
                    print(f"[OK] {input_path.name} already correct size")
                    return input_path
            else:
                # If probe fails, still scale/pad to target to ensure concat compatibility
                print(f"[WARN] Probe failed for {input_path.name}; forcing {target_width}x{target_height}")
                force_out = output_path
                resize_cmd = [
                    ffmpeg,
                    '-i', str(input_path),
                    '-vf', f'scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2',
                    '-c:v', 'libx264',
                    '-c:a', 'copy',
                    '-y',
                    str(force_out)
                ]
                resize_result = subprocess.run(resize_cmd, capture_output=True, text=True)
                if resize_result.returncode == 0:
                    print(f"[OK] Resized: {force_out}")
                    return force_out
                else:
                    print(f"[WARN] Resize failed, using original: {resize_result.stderr[:200]}")
                    return input_path

        intro_path_resized = resize_video_if_needed(intro_path, outdir / f"intro_resized_{int(time.time())}.mp4", width, height)
        outro_path_resized = resize_video_if_needed(outro_path, outdir / f"outro_resized_{int(time.time())}.mp4", width, height)

        # Verify all files exist before concatenation
        print("[VERIFY] Checking all video files before concatenation...")
        print(f"[VERIFY] Intro: {intro_path_resized} - Exists: {intro_path_resized.exists()}")
        print(f"[VERIFY] Main video: {video_with_avatar} - Exists: {video_with_avatar.exists()}")
        # Use the latest processed video (may include logo overlay)
        current_video = video_with_avatar
        print(f"[VERIFY] Using current video: {current_video} - Exists: {current_video.exists()}")
        print(f"[VERIFY] Outro: {outro_path_resized} - Exists: {outro_path_resized.exists()}")

        if not intro_path_resized.exists():
            raise Exception(f"Intro video not found: {intro_path_resized}")
        if not current_video.exists():
            raise Exception(f"Main video not found: {current_video}")
        if not outro_path_resized.exists():
            raise Exception(f"Outro video not found: {outro_path_resized}")
        concat_list_path = None

        # Demuxer concat path (default on Windows): normalize -> TS remux -> concat
        ts_now = int(time.time())
        final_video = outdir / f"final_with_intro_outro_{ts_now}.mp4"
        print("[CONCAT] Using demuxer concat path (normalize -> TS).")
        # Normalize each clip, then concat using demuxer
        print("[FALLBACK] Normalizing clips and concatenating via demuxer...")
        def normalize_clip(src_path: Path, out_path: Path):
            print(f"[NORM] Normalizing clip: {src_path} -> {out_path}")
            # Fast path: try pure remux/copy (works when codecs are already compatible)
            quick_cmd = [
                ffmpeg, '-hide_banner', '-loglevel', 'error',
                '-i', str(src_path),
                '-c', 'copy',
                '-movflags', '+faststart',
                '-y', str(out_path)
            ]
            res_quick = subprocess.run(quick_cmd, capture_output=True, text=True)
            if res_quick.returncode == 0:
                return

            # Encode path: re-encode with ultrafast preset, align fps/pixel format/audio
            norm_cmd = [
                ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(src_path),
                '-vf', 'fps=30,format=yuv420p,setsar=1/1',
                '-af', 'aformat=sample_fmts=s16:channel_layouts=stereo,aresample=async=1:first_pts=0,asetpts=N/SR/TB,apad',
                '-ar', '44100',
                '-ac', '2',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
                '-c:a', 'aac',
                '-movflags', '+faststart',
                '-y', str(out_path)
            ]
            res = subprocess.run(norm_cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[WARN] Normalize pass1 failed: {res.stderr[:300]}")
                norm2_cmd = [
                    ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(src_path),
                    '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                    '-vf', 'fps=30,format=yuv420p,setsar=1/1',
                    '-map', '0:v:0',
                    '-map', '1:a:0',
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
                    '-c:a', 'aac',
                    '-shortest',
                    '-movflags', '+faststart',
                    '-y', str(out_path)
                ]
                res2 = subprocess.run(norm2_cmd, capture_output=True, text=True)
                if res2.returncode != 0:
                    print(f"[!] Normalize pass2 failed: {res2.stderr[:300]}")
                    raise Exception(f"Normalize failed: {src_path}")

        # Normalize each source to stable MP4 (H.264/AAC) with simple caching for intro/outro
        def _norm_cache_path(src: Path) -> Path:
            try:
                cache_dir = Path('out') / 'cache_norm'
                cache_dir.mkdir(parents=True, exist_ok=True)
                st = src.stat()
                key = f"{src.stem}_{st.st_size}_{int(st.st_mtime)}.mp4"
                return cache_dir / key
            except Exception:
                # Fallback to non-cached path if something goes wrong
                return Path('out') / f"n_{src.stem}_{int(time.time())}.mp4"

        # Cache intro/outro (often reused); main video is per-upload so keep temp
        n_intro = _norm_cache_path(intro_path_resized)
        if not n_intro.exists():
            normalize_clip(intro_path_resized, n_intro)

        n_main = outdir / f"n_main_{int(time.time())}.mp4"
        normalize_clip(current_video, n_main)

        n_outro = _norm_cache_path(outro_path_resized)
        if not n_outro.exists():
            normalize_clip(outro_path_resized, n_outro)

        # Remux normalized MP4s to TS and concat via concat: protocol
        print("[FALLBACK] Remuxing to TS and concatenating via concat protocol...")

        ts_intro = outdir / f"ts_intro_{int(time.time())}.ts"
        ts_main = outdir / f"ts_main_{int(time.time())}.ts"
        ts_outro = outdir / f"ts_outro_{int(time.time())}.ts"

        def remux_to_ts(src: Path, dst: Path):
            cmd = [
                ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(src),
                '-c', 'copy',
                '-bsf:v', 'h264_mp4toannexb',
                '-f', 'mpegts',
                str(dst)
            ]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"[!] TS remux failed for {src}: {r.stderr[:300]}")
                raise Exception('TS remux failed')

        remux_to_ts(n_intro, ts_intro)
        remux_to_ts(n_main, ts_main)
        remux_to_ts(n_outro, ts_outro)

        concat_input = f"concat:{ts_intro.absolute()}|{ts_main.absolute()}|{ts_outro.absolute()}"
        ts_concat_cmd = [
            ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', concat_input,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-movflags', '+faststart',
            '-y', str(final_video)
        ]
        print(f"[FALLBACK] TS concat: {' '.join(ts_concat_cmd)}")
        ts_res = subprocess.run(ts_concat_cmd, capture_output=True, text=True)
        if ts_res.returncode != 0:
            print(f"[!] TS concat failed: {ts_res.stderr[:500]}")
            raise Exception(f"Concatenation failed: {ts_res.stderr}")

        print(f"[OK] Final video with intro/outro created: {final_video}")
        print(f"[OK] File size: {final_video.stat().st_size} bytes")

        # Optional wide (16:9) render
        make_wide = (request.form.get('make_wide', 'true') or 'true').lower() in {'true', '1', 'yes'}
        wide_blur = (request.form.get('wide_blur', 'false') or 'false').lower() in {'true', '1', 'yes'}
        final_wide = None
        if make_wide:
            try:
                target_w, target_h = 1920, 1080
                out_wide = outdir / f"final_with_intro_outro_wide_{ts_now}.mp4"
                print(f"[WIDE] Creating 16:9 variant (blur={wide_blur}) -> {out_wide}")
                if wide_blur:
                    vf = (
                        f"[0:v]scale={target_w}:{target_h},boxblur=luma_radius=20:luma_power=1:chroma_radius=20:chroma_power=1[bg];"
                        f"[0:v]scale=-2:{target_h}[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
                    )
                    cmd = [
                        ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(final_video),
                        '-vf', vf,
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
                        '-c:a', 'copy',
                        '-movflags', '+faststart', '-y', str(out_wide)
                    ]
                else:
                    # Plain pad to 1920x1080 with black side fill
                    vf = (
                        f"scale=-2:{target_h}:flags=lanczos,"
                        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
                    )
                    cmd = [
                        ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(final_video),
                        '-vf', vf,
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
                        '-c:a', 'copy',
                        '-movflags', '+faststart', '-y', str(out_wide)
                    ]
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode == 0 and out_wide.exists():
                    final_wide = out_wide
                    print(f"[OK] Wide variant created: {final_wide}")
                else:
                    print(f"[WARN] Wide variant failed: {r.stderr[:300]}")
            except Exception as _werr:
                print(f"[WARN] Wide variant error: {_werr}")

        # Clean up temporary files
        # No temp concat list to clean up with filter_complex

        # Track usage for logged-in users
        if user_id:
            title = request.form.get('title', 'Untitled Video')
            database.increment_video_count(user_id)
            database.add_video_to_history(user_id, final_video.name, title)
            print(f"[AUTH] Video counted for user {user_id}")

        # Save topic metadata as sidecar file for the video
        try:
            topic_selected_path = outdir / 'topic_selected.json'
            if topic_selected_path.exists():
                metadata_path = final_video.with_suffix('.metadata.json')
                import shutil
                shutil.copy(topic_selected_path, metadata_path)
                print(f"[METADATA] Saved topic data to {metadata_path.name}")

                # Also save for wide variant if it exists
                if final_wide:
                    wide_metadata_path = final_wide.with_suffix('.metadata.json')
                    shutil.copy(topic_selected_path, wide_metadata_path)
                    print(f"[METADATA] Saved topic data to {wide_metadata_path.name}")
        except Exception as meta_err:
            print(f"[METADATA] Warning: Could not save metadata: {meta_err}")

        return jsonify({
            'success': True,
            'message': 'Video post-processed successfully',
            'files': {
                'final_video': final_video.name,
                'final_wide': final_wide.name if final_wide else None,
                'avatar_video': avatar_video_path.name if avatar_video_path else None
            }
        })

    except Exception as e:
        print(f"Error post-processing video: {e}")
        # If this is a Windows path/handle error (OSError 22) and we saved the upload, return it as-is
        try:
            import errno
            is_oserr_22 = isinstance(e, OSError) and getattr(e, 'errno', None) in (22, errno.EINVAL)
        except Exception:
            is_oserr_22 = False
        try:
            saved_name = Path(video_path).name if 'video_path' in locals() and video_path else None
        except Exception:
            saved_name = None
        if is_oserr_22 and saved_name:
            print(f"[FALLBACK] OSError(22) encountered; returning uploaded video {saved_name} without processing")
            return jsonify({
                'success': True,
                'message': 'OSError(22) encountered; returning uploaded video as-is.',
                'files': {
                    'final_video': saved_name,
                    'avatar_video': None
                }
            })
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get-recent-videos', methods=['GET'])
def get_recent_videos():
    """Get list of recent video files from out directory"""
    try:
        outdir = Path("out")
        if not outdir.exists():
            return jsonify({'success': True, 'videos': []})

        # Get all video files
        video_files = []
        for pattern in ['*.mp4', '*.mov']:
            video_files.extend(outdir.glob(pattern))

        # Filter for processed videos (with avatar, final, etc.)
        processed_videos = [
            f for f in video_files
            if any(keyword in f.name for keyword in ['video_with_avatar', 'final', 'did_avatar', 'shorts', 'wide'])
        ]

        # Sort by modification time (most recent first)
        processed_videos.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # Return top 10 most recent
        videos = []
        for video_file in processed_videos[:10]:
            stat = video_file.stat()
            size_mb = stat.st_size / (1024 * 1024)
            mtime = stat.st_mtime

            # Format size
            if size_mb > 1024:
                size_str = f"{size_mb/1024:.1f} GB"
            else:
                size_str = f"{size_mb:.1f} MB"

            # Format date
            from datetime import datetime
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

            videos.append({
                'name': video_file.name,
                'size': size_str,
                'date': date_str,
                'path': str(video_file)
            })

        return jsonify({'success': True, 'videos': videos})

    except Exception as e:
        print(f"Error getting recent videos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete-video', methods=['POST'])
def delete_video():
    """Delete a video file from the out directory"""
    try:
        data = request.get_json()
        filename = data.get('filename')

        if not filename:
            return jsonify({'success': False, 'error': 'No filename provided'}), 400

        # Security: prevent path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'success': False, 'error': 'Invalid filename'}), 400

        # Only allow deletion from out directory
        outdir = Path("out")
        video_path = outdir / filename

        if not video_path.exists():
            return jsonify({'success': False, 'error': 'Video file not found'}), 404

        # Check if file is actually in out directory (security check)
        if not str(video_path.resolve()).startswith(str(outdir.resolve())):
            return jsonify({'success': False, 'error': 'Invalid file path'}), 403

        # Delete the file
        video_path.unlink()
        print(f"[DELETE] Deleted video: {filename}")

        return jsonify({
            'success': True,
            'message': f'Video "{filename}" deleted successfully'
        })

    except Exception as e:
        print(f"Error deleting video: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get-latest-output', methods=['GET'])
def get_latest_output():
    """Get the latest video output for preview"""
    try:
        outdir = Path("out")

        # Check if output directory exists
        if not outdir.exists():
            return jsonify({
                'success': False,
                'error': 'No output directory found. Generate a video first.'
            }), 404

        # Load script data
        script_file = outdir / "script.json"
        if not script_file.exists():
            return jsonify({
                'success': False,
                'error': 'No script found. Generate a video first.'
            }), 404

        script_data = json.loads(script_file.read_text(encoding="utf-8"))

        # Find video files
        shorts_file = None
        wide_file = None
        for f in outdir.glob("*.mp4"):
            if "shorts" in f.name.lower():
                shorts_file = f.name
            elif "wide" in f.name.lower():
                wide_file = f.name

        # Find thumbnail files
        thumbnail_files = []
        ai_thumbnail = None
        for f in outdir.glob("thumb_*.jpg"):
            if "ai_dalle" in f.name:
                ai_thumbnail = f.name
            else:
                thumbnail_files.append(f.name)

        return jsonify({
            'success': True,
            'output_dir': str(outdir.absolute()),
            'files': {
                'shorts': shorts_file,
                'wide': wide_file,
                'thumbnail_files': thumbnail_files,
                'ai_thumbnail': ai_thumbnail
            },
            'script': {
                'title': script_data.get('title', ''),
                'narration': script_data.get('narration', ''),
                'overlays': script_data.get('overlays', []),
                'keywords': script_data.get('keywords', [])
            }
        })

    except Exception as e:
        print(f"Error fetching latest output: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/out/<path:filename>', methods=['GET'])
def serve_output_file(filename):
    """Serve files from the output directory"""
    try:
        outdir = Path("out").absolute()
        return send_from_directory(outdir, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/avatars/<path:filename>', methods=['GET'])
def serve_avatar_file(filename):
    """Serve files from the avatars directory"""
    try:
        # Avatar files are in parent directory (MSS/avatars)
        avatars_dir = Path(__file__).parent.parent / "avatars"
        return send_from_directory(avatars_dir, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/thumbnails/<path:filename>', methods=['GET'])
def serve_thumbnail_file(filename):
    """Serve generated thumbnail/background images"""
    try:
        thumbnails_dir = (Path(__file__).parent.parent / 'thumbnails').absolute()
        return send_from_directory(thumbnails_dir, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/thumbnails', methods=['GET'])
def api_list_thumbnails():
    """Return a JSON listing of generated thumbnails/backgrounds."""
    try:
        from urllib.parse import urljoin
        base = request.host_url if hasattr(request, 'host_url') else 'http://127.0.0.1:5000/'
        thumbnails_dir = Path('thumbnails').absolute()
        items = []
        if thumbnails_dir.exists():
            files = []
            for ext in ('*.png', '*.jpg', '*.jpeg', '*.webp'):
                files.extend(thumbnails_dir.glob(ext))
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for f in files:
                try:
                    items.append({
                        'filename': f.name,
                        'size': f.stat().st_size,
                        'mtime': f.stat().st_mtime,
                        'url': urljoin(base, f'thumbnails/{f.name}')
                    })
                except Exception:
                    pass
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/thumbnails', methods=['GET'])
def browse_thumbnails():
    """Simple HTML index to browse thumbnails/backgrounds."""
    try:
        from urllib.parse import urljoin
        base = request.host_url if hasattr(request, 'host_url') else 'http://127.0.0.1:5000/'
        thumbnails_dir = Path('thumbnails').absolute()
        rows = []
        if thumbnails_dir.exists():
            files = []
            for ext in ('*.png', '*.jpg', '*.jpeg', '*.webp'):
                files.extend(thumbnails_dir.glob(ext))
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            for f in files:
                url = urljoin(base, f'thumbnails/{f.name}')
                rows.append(f'<div style="margin:8px 0;"><a href="{url}">{f.name}</a><br><img src="{url}" style="max-width:420px; height:auto; border:1px solid #334; border-radius:6px;"/></div>')
        html = (
            '<!DOCTYPE html><html><head><meta charset="utf-8"/>'
            '<title>Thumbnails</title>'
            '<style>body{background:#0B0F19;color:#E8EBFF;font-family:system-ui,Segoe UI,Arial; padding:16px;} a{color:#60a5fa;}</style>'
            '</head><body>'
            '<h1>Thumbnails</h1>' + (''.join(rows) if rows else '<p>No thumbnails found.</p>') + '</body></html>'
        )
        return html
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check for rendering stack.

    Query params:
    - deep=1 to attempt a quick Chromium launch test.
    """
    try:
        import shutil
        import imageio_ffmpeg
        from pathlib import Path as _PathH

        # ffmpeg
        try:
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            ffmpeg_ok = bool(ffmpeg_path)
        except Exception:
            ffmpeg_path = None
            ffmpeg_ok = False

        # ffprobe (PATH or alongside ffmpeg)
        ffprobe_path = shutil.which('ffprobe')
        if not ffprobe_path and ffmpeg_path:
            try:
                cand = _PathH(ffmpeg_path).parent / ('ffprobe.exe' if os.name == 'nt' else 'ffprobe')
                if cand.exists():
                    ffprobe_path = str(cand)
            except Exception:
                pass
        ffprobe_ok = bool(ffprobe_path)

        # Playwright status
        playwright_importable = False
        chromium_ready = None
        check_mode = 'shallow'
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
            playwright_importable = True
            if (request.args.get('deep') or '').lower() in {'1', 'true', 'yes'}:
                check_mode = 'deep'
                try:
                    with sync_playwright() as p:
                        b = p.chromium.launch(headless=True)
                        b.close()
                    chromium_ready = True
                except Exception:
                    chromium_ready = False
        except Exception:
            playwright_importable = False

        return jsonify({
            'success': True,
            'ffmpeg': {'available': ffmpeg_ok, 'path': ffmpeg_path},
            'ffprobe': {'available': ffprobe_ok, 'path': ffprobe_path},
            'playwright': {
                'importable': playwright_importable,
                'chromium_ready': chromium_ready,
                'check': check_mode
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/usage', methods=['GET'])
def api_usage():
    try:
        usage = {
            'videos_this_month': 0,
            'monthly_limit': 999,
            'videos_remaining': 999,
            'at_limit': False,
            'tier': 'dev'
        }
        return jsonify({'success': True, 'usage': usage})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 200


@app.route('/youtube-categories', methods=['GET'])
def youtube_categories():
    cats = {
        '1': 'Film & Animation',
        '2': 'Autos & Vehicles',
        '10': 'Music',
        '15': 'Pets & Animals',
        '17': 'Sports',
        '19': 'Travel & Events',
        '20': 'Gaming',
        '22': 'People & Blogs',
        '23': 'Comedy',
        '24': 'Entertainment',
        '25': 'News & Politics',
        '26': 'Howto & Style',
        '27': 'Education',
        '28': 'Science & Technology',
    }
    return jsonify({'success': True, 'categories': cats})
@app.route('/logos/<path:filename>', methods=['GET'])
def serve_logo_file(filename):
    """Serve logo files. Prefer ./logos, then ./web/logos, then ./web/logos_migrated.

    This keeps existing projects working even if files were dragged into the web folder.
    """
    try:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        safe_name = ''.join(ch for ch in Path(filename).name if ch in allowed)
        if not safe_name:
            return jsonify({'error': 'Invalid filename'}), 404

        candidates = [
            Path(__file__).parent.parent / 'logos' / safe_name,
            Path(__file__).parent / 'logos' / safe_name,
            Path(__file__).parent / 'logos_migrated' / safe_name,
        ]
        for p in candidates:
            if p.exists():
                return send_from_directory(p.parent, p.name)

        return jsonify({'error': 'Logo not found', 'filename': safe_name}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/logo-files', methods=['GET'])
def api_logo_files():
    try:
        dirs = [
            Path(__file__).parent.parent / 'logos',
            Path(__file__).parent / 'logos',
            Path(__file__).parent / 'logos_migrated',
        ]
        seen = set()
        items = []
        for d in dirs:
            if not d.exists():
                continue
            for ext in ('*.png', '*.jpg', '*.jpeg', '*.svg', '*.webp'):
                for f in d.glob(ext):
                    if f.name in seen:
                        continue
                    seen.add(f.name)
                    try:
                        items.append({
                            'filename': f.name,
                            'url': f"http://127.0.0.1:5000/logos/{f.name}",
                            'size': f.stat().st_size,
                        })
                    except Exception:
                        pass
        # Sort by mtime across possible dirs
        def _mtime(name: str) -> float:
            for d in dirs:
                p = d / name
                if p.exists():
                    return p.stat().st_mtime
            return 0.0
        items.sort(key=lambda x: _mtime(x['filename']), reverse=True)
        return jsonify({'success': True, 'logos': items})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get-logo-library', methods=['GET'])
def get_logo_library_route():
    try:
        path = Path('logo_library.json')
        dirs = [
            Path(__file__).parent.parent / 'logos',
            Path(__file__).parent / 'logos',
            Path(__file__).parent / 'logos_migrated',
        ]
        if not path.exists():
            return jsonify({'success': True, 'logos': []})

        # Load library; tolerate empty/invalid content
        try:
            raw = path.read_text(encoding='utf-8')
            data = json.loads(raw or '{}') if raw is not None else {}
            raw_list = data.get('logos', []) if isinstance(data, dict) else []
        except Exception:
            raw_list = []

        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        uniq = {}
        for item in raw_list:
            try:
                url = (item.get('url') or '').strip()
                fname = (item.get('filename') or (url.split('/')[-1] if url else '')).strip()
                fname = ''.join(ch for ch in Path(fname).name if ch in allowed)
                if not fname:
                    continue
                exists = any((d / fname).exists() for d in dirs)
                if not exists:
                    continue
                normalized_url = f"http://127.0.0.1:5000/logos/{fname}"
                name = (item.get('name') or '').strip() or fname
                uniq[fname] = {
                    'id': item.get('id') or fname,
                    'name': name,
                    'url': normalized_url,
                    'filename': fname,
                    'active': bool(item.get('active', False)),
                }
            except Exception:
                continue

        def _mtime(fname: str) -> float:
            for d in dirs:
                p = d / fname
                if p.exists():
                    try:
                        return p.stat().st_mtime
                    except Exception:
                        return 0
            return 0

        cleaned = list(uniq.values())
        cleaned.sort(key=lambda x: _mtime(x['filename']), reverse=True)
        return jsonify({'success': True, 'logos': cleaned})
    except Exception:
        return jsonify({'success': True, 'logos': []})

@app.route('/set-active-logo', methods=['POST'])
def set_active_logo():
    try:
        data = request.get_json(force=True) or {}
        logo_id = (data.get('id') or '').strip()
        if not logo_id:
            return jsonify({'success': False, 'error': 'No logo ID provided'}), 400
        lib_path = Path('logo_library.json')
        if not lib_path.exists():
            return jsonify({'success': False, 'error': 'Logo library not found'}), 404
        library = json.loads(lib_path.read_text(encoding='utf-8') or '{}')
        logos = library.get('logos', []) if isinstance(library, dict) else []
        for l in logos: l['active']=False
        active_url=None; found=False
        for l in logos:
            if l.get('id') == logo_id:
                l['active']=True
                active_url=l.get('url')
                found=True
                break
        if not found:
            return jsonify({'success': False, 'error': 'Logo not found'}), 404
        lib_path.write_text(json.dumps({'logos': logos}, indent=2), encoding='utf-8')
        return jsonify({'success': True, 'logoUrl': active_url})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/delete-logo', methods=['POST'])
def delete_logo():
    try:
        data = request.get_json(force=True) or {}
        logo_id = (data.get('id') or '').strip()
        if not logo_id:
            return jsonify({'success': False, 'error': 'No logo ID provided'}), 400
        lib_path = Path('logo_library.json')
        if not lib_path.exists():
            return jsonify({'success': False, 'error': 'Logo library not found'}), 404
        library = json.loads(lib_path.read_text(encoding='utf-8') or '{}')
        logos = library.get('logos', []) if isinstance(library, dict) else []
        target = next((l for l in logos if l.get('id') == logo_id), None)
        if not target:
            return jsonify({'success': False, 'error': 'Logo not found'}), 404
        fname = (target.get('filename') or '').strip()
        if fname:
            p = Path(__file__).parent.parent / 'logos' / Path(fname).name
            try:
                if p.exists(): p.unlink()
            except Exception:
                pass
        logos = [l for l in logos if l.get('id') != logo_id]
        lib_path.write_text(json.dumps({'logos': logos}, indent=2), encoding='utf-8')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/upload-logo-to-library', methods=['POST'])
def upload_logo_to_library():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        file = request.files['file']
        name = request.form.get('name', file.filename)
        logos_dir = Path(__file__).parent.parent / 'logos'
        logos_dir.mkdir(exist_ok=True)
        ext = Path(file.filename).suffix or '.png'
        unique = f"logo_{int(time.time())}{ext}"
        dest = logos_dir / unique
        file.save(str(dest))
        url = f"http://127.0.0.1:5000/logos/{dest.name}"
        lib_path = Path('logo_library.json')
        library = {'logos': []}
        if lib_path.exists():
            try: library = json.loads(lib_path.read_text(encoding='utf-8') or '{}')
            except Exception: library = {'logos': []}
        entry = {
            'id': str(int(time.time()*1000)),
            'name': name,
            'url': url,
            'filename': dest.name,
            'active': False,
            'uploadedAt': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        library.setdefault('logos', []).append(entry)
        lib_path.write_text(json.dumps(library, indent=2), encoding='utf-8')
        return jsonify({'success': True, 'url': url, 'logo': entry})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===========================================
# TREND ALERTS & AI CONTENT CALENDAR API
# ===========================================

# Force add current directory to path
import sys
if '.' not in sys.path:
    sys.path.insert(0, '.')

trend_manager = None
try:
    print("[TRENDS] Attempting import from web.trend_calendar...")
    from web.trend_calendar import TrendCalendarManager
    trend_manager = TrendCalendarManager()
    print("[TRENDS] TrendCalendarManager loaded successfully (web.trend_calendar)")
except Exception as e1:
    print(f"[TRENDS] Failed to import from web.trend_calendar: {e1}")
    import traceback
    traceback.print_exc()
    try:
        print("[TRENDS] Attempting import from trend_calendar...")
        from trend_calendar import TrendCalendarManager
        trend_manager = TrendCalendarManager()
        print("[TRENDS] TrendCalendarManager loaded successfully (trend_calendar)")
    except Exception as e2:
        print(f"[TRENDS] Failed to import from trend_calendar: {e2}")
        traceback.print_exc()
        trend_manager = None
        print("[TRENDS] WARNING: Trend manager not available - endpoints will return 500")

print(f"[TRENDS] Final status: trend_manager = {trend_manager}")

# ===========================================
# ANALYTICS MODULE
# ===========================================

analytics_manager = None
try:
    print("[ANALYTICS] Attempting import from web.analytics...")
    from web.analytics import AnalyticsManager
    analytics_manager = AnalyticsManager()
    print("[ANALYTICS] AnalyticsManager loaded successfully")
except Exception as e1:
    print(f"[ANALYTICS] Failed to import from web.analytics: {e1}")
    try:
        print("[ANALYTICS] Attempting import from analytics...")
        from analytics import AnalyticsManager
        analytics_manager = AnalyticsManager()
        print("[ANALYTICS] AnalyticsManager loaded successfully (analytics)")
    except Exception as e2:
        print(f"[ANALYTICS] Failed to import from analytics: {e2}")
        analytics_manager = None
        print("[ANALYTICS] WARNING: Analytics manager not available")

print(f"[ANALYTICS] Final status: analytics_manager = {analytics_manager}")

# ===========================================
# MULTI-PLATFORM PUBLISHER MODULE
# ===========================================

multi_platform = None
try:
    print("[MULTIPLATFORM] Attempting import from web.multi_platform...")
    from web.multi_platform import MultiPlatformPublisher
    multi_platform = MultiPlatformPublisher()
    print("[MULTIPLATFORM] MultiPlatformPublisher loaded successfully")
except Exception as e1:
    print(f"[MULTIPLATFORM] Failed to import from web.multi_platform: {e1}")
    try:
        print("[MULTIPLATFORM] Attempting import from multi_platform...")
        from multi_platform import MultiPlatformPublisher
        multi_platform = MultiPlatformPublisher()
        print("[MULTIPLATFORM] MultiPlatformPublisher loaded successfully (multi_platform)")
    except Exception as e2:
        print(f"[MULTIPLATFORM] Failed to import from multi_platform: {e2}")
        multi_platform = None
        print("[MULTIPLATFORM] WARNING: Multi-platform publisher not available")

print(f"[MULTIPLATFORM] Final status: multi_platform = {multi_platform}")

# ===========================================
# PLATFORM API INTEGRATION MODULE
# ===========================================

platform_api = None
try:
    print("[PLATFORM_API] Attempting import from web.platform_apis...")
    from web.platform_apis import PlatformAPIManager
    platform_api = PlatformAPIManager()
    print("[PLATFORM_API] PlatformAPIManager loaded successfully")
except Exception as e1:
    print(f"[PLATFORM_API] Failed to import from web.platform_apis: {e1}")
    try:
        print("[PLATFORM_API] Attempting import from platform_apis...")
        from platform_apis import PlatformAPIManager
        platform_api = PlatformAPIManager()
        print("[PLATFORM_API] PlatformAPIManager loaded successfully (platform_apis)")
    except Exception as e2:
        print(f"[PLATFORM_API] Failed to import from platform_apis: {e2}")
        platform_api = None
        print("[PLATFORM_API] WARNING: Platform API manager not available")

print(f"[PLATFORM_API] Final status: platform_api = {platform_api}")

def _get_user_from_session():
    """Helper to get user email from session"""
    session_id = request.cookies.get('session_id')
    if not session_id:
        return None, jsonify({'success': False, 'error': 'Not authenticated'}), 401

    result = database.get_session(session_id)
    if not result.get('success'):
        return None, jsonify({'success': False, 'error': 'Invalid or expired session'}), 401

    return result['user']['email'], None, None

@app.route('/api/trends/status', methods=['GET'])
def trends_status():
    """Debug endpoint to check trend manager status"""
    return jsonify({
        'trend_manager_loaded': trend_manager is not None,
        'trend_manager_type': str(type(trend_manager)) if trend_manager else None,
        'db_path': trend_manager.db_path if trend_manager else None
    })

@app.route('/api/trends', methods=['GET'])
def get_trends():
    """Get trending topics for the user"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    # Get user from session
    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    niche = request.args.get('niche', None)

    try:
        trends = trend_manager.get_trending_topics(user_email, niche)
        return jsonify({'success': True, 'trends': trends})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trends/save', methods=['POST'])
def save_trend_alert():
    """Save a trend alert for the user"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code
    data = request.get_json()

    try:
        alert_id = trend_manager.save_trend_alert(user_email, data)
        return jsonify({'success': True, 'alert_id': alert_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trends/alerts', methods=['GET'])
def get_trend_alerts():
    """Get user's saved trend alerts"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code
    include_dismissed = request.args.get('include_dismissed', 'false').lower() == 'true'

    try:
        alerts = trend_manager.get_user_alerts(user_email, include_dismissed)
        return jsonify({'success': True, 'alerts': alerts})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trends/dismiss/<int:alert_id>', methods=['POST'])
def dismiss_trend_alert(alert_id):
    """Dismiss a trend alert"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        success = trend_manager.dismiss_alert(alert_id, user_email)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/calendar/generate', methods=['GET'])
def generate_content_calendar():
    """Generate AI-powered content calendar"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code
    days_ahead = int(request.args.get('days', 30))

    try:
        suggestions = trend_manager.generate_content_calendar(user_email, days_ahead)
        return jsonify({'success': True, 'suggestions': suggestions})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/calendar', methods=['GET'])
def get_calendar_entries():
    """Get user's calendar entries"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    try:
        entries = trend_manager.get_calendar_entries(user_email, start_date, end_date)
        return jsonify({'success': True, 'entries': entries})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/calendar', methods=['POST'])
def save_calendar_entry():
    """Save a calendar entry and optionally add to Google Calendar"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code
    data = request.get_json()

    try:
        # Save to MSS database
        entry_id = trend_manager.save_calendar_entry(user_email, data)

        # Try to add to Google Calendar if connected
        google_calendar_result = None
        if platform_api:
            try:
                google_calendar_result = platform_api.add_calendar_event(user_email, data)
                if google_calendar_result.get('success'):
                    print(f"[CALENDAR] Event added to Google Calendar: {google_calendar_result.get('html_link')}")
            except Exception as e:
                print(f"[CALENDAR] Could not add to Google Calendar: {e}")
                # Don't fail the whole request if Google Calendar fails

        return jsonify({
            'success': True,
            'entry_id': entry_id,
            'google_calendar': google_calendar_result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/calendar/<int:entry_id>/export.ics', methods=['GET'])
def export_calendar_entry_ics(entry_id):
    """Export a calendar entry as .ics file"""
    if not trend_manager:
        return "Calendar not available", 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        # Get the calendar entry
        entries = trend_manager.get_calendar_entries(user_email)
        entry = None
        for e in entries:
            if e['id'] == entry_id:
                entry = e
                break

        if not entry:
            return "Calendar entry not found", 404

        # Generate .ics content
        from datetime import datetime as dt

        # Parse date and time
        event_date = entry['scheduled_date']  # Format: YYYY-MM-DD
        event_time = entry.get('scheduled_time', '10:00')  # Format: HH:MM

        # Combine date and time
        event_datetime = dt.strptime(f"{event_date} {event_time}", "%Y-%m-%d %H:%M")

        # Format for .ics (YYYYMMDDTHHMMSS)
        dtstart = event_datetime.strftime("%Y%m%dT%H%M%S")

        # Event duration: 1 hour
        from datetime import timedelta
        dtend = (event_datetime + timedelta(hours=1)).strftime("%Y%m%dT%H%M%S")

        # Current timestamp for DTSTAMP
        dtstamp = dt.utcnow().strftime("%Y%m%dT%H%M%SZ")

        # Create unique UID
        uid = f"mss-calendar-{entry_id}@mss.local"

        # Build .ics content
        title = entry.get('title', 'Content Creation')
        description = entry.get('description', entry.get('topic', ''))
        if entry.get('reason'):
            description += f"\\n\\n{entry['reason']}"
        
        # Replace newlines before using in f-string (can't use backslash in f-string expressions)
        description_escaped = description.replace(chr(10), '\\n')

        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//MSS Studio//Content Calendar//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{title}
DESCRIPTION:{description_escaped}
LOCATION:MSS Studio
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""

        # Return as downloadable .ics file
        from flask import Response
        response = Response(ics_content, mimetype='text/calendar')
        response.headers['Content-Disposition'] = f'attachment; filename="mss-event-{entry_id}.ics"'
        return response

    except Exception as e:
        print(f"[CALENDAR] Error exporting .ics: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500

@app.route('/api/calendar/<int:entry_id>', methods=['PUT'])
def update_calendar_entry(entry_id):
    """Update a calendar entry"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code
    data = request.get_json()

    try:
        success = trend_manager.update_calendar_entry(entry_id, user_email, data)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/calendar/<int:entry_id>', methods=['DELETE'])
def delete_calendar_entry(entry_id):
    """Delete a calendar entry"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        success = trend_manager.delete_calendar_entry(entry_id, user_email)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/preferences', methods=['GET'])
def get_user_preferences():
    """Get user preferences for trends/calendar"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        prefs = trend_manager.get_user_preferences(user_email)
        return jsonify({'success': True, 'preferences': prefs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/preferences', methods=['POST'])
def save_user_preferences():
    """Save user preferences for trends/calendar"""
    if not trend_manager:
        return jsonify({'success': False, 'error': 'Trend manager not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code
    data = request.get_json()

    try:
        success = trend_manager.save_user_preferences(user_email, data)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ===========================================
# ANALYTICS API ENDPOINTS
# ===========================================

@app.route('/api/analytics/dashboard', methods=['GET'])
def get_analytics_dashboard():
    """Get comprehensive analytics dashboard data"""
    if not analytics_manager:
        return jsonify({'success': False, 'error': 'Analytics not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    days = request.args.get('days', 30, type=int)

    try:
        stats = analytics_manager.get_dashboard_stats(user_email, days)
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/videos', methods=['GET'])
def get_analytics_videos():
    """Get all videos with metrics"""
    if not analytics_manager:
        return jsonify({'success': False, 'error': 'Analytics not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    limit = request.args.get('limit', 50, type=int)

    try:
        videos = analytics_manager.get_user_videos(user_email, limit)
        return jsonify({'success': True, 'videos': videos})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/track-video', methods=['POST'])
def track_video_creation():
    """Track a new video creation"""
    if not analytics_manager:
        return jsonify({'success': False, 'error': 'Analytics not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    data = request.get_json()

    try:
        video_id = analytics_manager.track_video_creation(user_email, data)
        return jsonify({'success': True, 'video_id': video_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/update-metrics', methods=['POST'])
def update_video_metrics():
    """Update metrics for a video"""
    if not analytics_manager:
        return jsonify({'success': False, 'error': 'Analytics not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    data = request.get_json()
    video_id = data.get('video_id')
    metrics = data.get('metrics', {})
    platform = data.get('platform', 'youtube')

    if not video_id:
        return jsonify({'success': False, 'error': 'video_id required'}), 400

    try:
        metric_id = analytics_manager.record_video_metrics(video_id, metrics, platform)
        return jsonify({'success': True, 'metric_id': metric_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/analytics-dashboard')
def analytics_dashboard_page():
    """Serve the analytics dashboard page"""
    return send_from_directory('topic-picker-standalone', 'analytics-dashboard.html')

@app.route('/channel-manager')
def channel_manager_page():
    """Serve the channel manager page"""
    return send_from_directory('topic-picker-standalone', 'channel-manager.html')


# ===========================================
# MULTI-PLATFORM PUBLISHER API ENDPOINTS
# ===========================================

@app.route('/api/platforms/presets', methods=['GET'])
def get_platform_presets():
    """Get all platform optimization presets"""
    if not multi_platform:
        return jsonify({'success': False, 'error': 'Multi-platform publisher not available'}), 500

    try:
        presets = multi_platform.get_platform_presets()
        return jsonify({'success': True, 'presets': presets})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/optimize', methods=['POST'])
def optimize_video():
    """Optimize video for specific platform"""
    if not multi_platform:
        return jsonify({'success': False, 'error': 'Multi-platform publisher not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    data = request.get_json()
    video_filename = data.get('video_filename')
    platform = data.get('platform')

    if not video_filename or not platform:
        return jsonify({'success': False, 'error': 'video_filename and platform required'}), 400

    # Construct input path
    input_path = os.path.join('out', video_filename)

    try:
        result = multi_platform.optimize_video_for_platform(input_path, platform)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload/video', methods=['POST'])
def upload_video():
    """Upload video file to out/ directory"""
    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    if 'video' not in request.files:
        return jsonify({'success': False, 'error': 'No video file provided'}), 400

    video_file = request.files['video']

    if video_file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    # Validate file extension
    allowed_extensions = {'mp4', 'mov', 'avi', 'mkv'}
    file_ext = video_file.filename.rsplit('.', 1)[1].lower() if '.' in video_file.filename else ''

    if file_ext not in allowed_extensions:
        return jsonify({'success': False, 'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'}), 400

    try:
        # Generate unique filename
        timestamp = int(time.time())
        # Use original filename but make it safe
        original_name = video_file.filename.rsplit('.', 1)[0]
        safe_name = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in original_name)
        safe_filename = f"{safe_name}_{timestamp}.{file_ext}"
        video_path = os.path.join('out', safe_filename)

        # Save the file
        video_file.save(video_path)

        print(f"[UPLOAD] Video uploaded: {video_path}")

        return jsonify({
            'success': True,
            'video_path': safe_filename,
            'message': 'Video uploaded successfully'
        })

    except Exception as e:
        print(f"[UPLOAD] Video upload error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload/thumbnail', methods=['POST'])
def upload_thumbnail():
    """Upload thumbnail image for video publishing"""
    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    if 'thumbnail' not in request.files:
        return jsonify({'success': False, 'error': 'No thumbnail file provided'}), 400

    thumbnail_file = request.files['thumbnail']

    if thumbnail_file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    # Validate file extension
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_ext = thumbnail_file.filename.rsplit('.', 1)[1].lower() if '.' in thumbnail_file.filename else ''

    if file_ext not in allowed_extensions:
        return jsonify({'success': False, 'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'}), 400

    try:
        # Create thumbnails directory if it doesn't exist
        thumbnails_dir = os.path.join('out', 'thumbnails')
        os.makedirs(thumbnails_dir, exist_ok=True)

        # Generate unique filename
        timestamp = int(time.time())
        safe_filename = f"thumbnail_{timestamp}.{file_ext}"
        thumbnail_path = os.path.join(thumbnails_dir, safe_filename)

        # Save the file
        thumbnail_file.save(thumbnail_path)

        return jsonify({
            'success': True,
            'thumbnail_path': thumbnail_path,
            'message': 'Thumbnail uploaded successfully'
        })

    except Exception as e:
        print(f"[UPLOAD] Thumbnail upload error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/video/delete/<path:filename>', methods=['DELETE'])
def delete_video_file(filename):
    """Delete a video file from out/ directory"""
    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        video_path = os.path.join('out', filename)

        # Security check: make sure the path is within 'out' directory
        if not os.path.abspath(video_path).startswith(os.path.abspath('out')):
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400

        if not os.path.exists(video_path):
            return jsonify({'success': False, 'error': 'Video file not found'}), 404

        # Move to trash instead of deleting permanently
        trash_dir = os.path.join('out', '.trash')
        os.makedirs(trash_dir, exist_ok=True)

        trash_path = os.path.join(trash_dir, filename)
        os.rename(video_path, trash_path)

        print(f"[DELETE] Video moved to trash: {filename}")

        return jsonify({
            'success': True,
            'message': 'Video moved to trash'
        })

    except Exception as e:
        print(f"[DELETE] Error deleting video: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/queue', methods=['POST'])
def queue_publication():
    """Add video to publishing queue"""
    if not multi_platform:
        return jsonify({'success': False, 'error': 'Multi-platform publisher not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    data = request.get_json()
    video_filename = data.get('video_filename')
    platforms = data.get('platforms', [])
    title = data.get('title', '')
    description = data.get('description', '')
    tags = data.get('tags', [])
    scheduled_time = data.get('scheduled_time')
    thumbnail_path = data.get('thumbnail_path')

    if not video_filename or not platforms:
        return jsonify({'success': False, 'error': 'video_filename and platforms required'}), 400

    try:
        queue_id = multi_platform.queue_publication(
            user_email, video_filename, platforms, title, description, tags, scheduled_time, thumbnail_path
        )
        return jsonify({'success': True, 'queue_id': queue_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/queue', methods=['GET'])
def get_publishing_queue():
    """Get publishing queue for user"""
    if not multi_platform:
        return jsonify({'success': False, 'error': 'Multi-platform publisher not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    status = request.args.get('status')

    try:
        queue = multi_platform.get_publishing_queue(user_email, status)
        return jsonify({'success': True, 'queue': queue})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/queue/<int:queue_id>', methods=['DELETE'])
def delete_queue_item(queue_id):
    """Delete a queue item"""
    if not multi_platform:
        return jsonify({'success': False, 'error': 'Multi-platform publisher not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        success = multi_platform.delete_queue_item(user_email, queue_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/queue/clear-completed', methods=['POST'])
def clear_completed_queue():
    """Clear all completed and failed queue items"""
    if not multi_platform:
        return jsonify({'success': False, 'error': 'Multi-platform publisher not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        deleted = multi_platform.clear_completed_queue(user_email)
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/queue/<int:queue_id>/process', methods=['POST'])
def process_queue_item(queue_id):
    """Process a queue item and publish to platforms"""
    if not multi_platform or not platform_api:
        return jsonify({'success': False, 'error': 'Multi-platform publisher not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        # Get queue item
        queue_items = multi_platform.get_publishing_queue(user_email)
        queue_item = next((item for item in queue_items if item['id'] == queue_id), None)

        if not queue_item:
            return jsonify({'success': False, 'error': 'Queue item not found'}), 404

        # Parse platforms
        platforms = json.loads(queue_item['platforms'])
        video_filename = queue_item['video_filename']
        title = queue_item['title']
        description = queue_item.get('description', '')
        tags = json.loads(queue_item.get('tags', '[]'))
        thumbnail_path = queue_item.get('thumbnail_path')
        scheduled_time = queue_item.get('scheduled_time')

        # Construct video path
        video_path = os.path.join('out', video_filename)

        if not os.path.exists(video_path):
            multi_platform.update_queue_status(queue_id, 'failed', f'Video file not found: {video_filename}')
            return jsonify({'success': False, 'error': f'Video file not found: {video_filename}'}), 404

        # Update status to processing
        multi_platform.update_queue_status(queue_id, 'processing')

        results = {}
        errors = []

        # Process each platform
        for platform in platforms:
            try:
                if platform == 'youtube' or platform == 'youtube_shorts':
                    # Upload to YouTube
                    result = platform_api.upload_to_youtube(
                        user_email,
                        video_path,
                        title,
                        description,
                        tags,
                        category_id='22',
                        privacy='public',
                        thumbnail_path=thumbnail_path,
                        publish_at=scheduled_time
                    )

                    if result.get('success'):
                        results[platform] = {
                            'success': True,
                            'url': result.get('url'),
                            'video_id': result.get('video_id')
                        }

                        # Record publication
                        multi_platform.record_publication(
                            user_email,
                            None,  # video_id from database
                            platform,
                            result.get('video_id', ''),
                            result.get('url', ''),
                            title,
                            description
                        )
                    else:
                        errors.append(f"{platform}: {result.get('error', 'Unknown error')}")
                        results[platform] = {'success': False, 'error': result.get('error')}
                else:
                    errors.append(f"{platform}: Platform not yet implemented")
                    results[platform] = {'success': False, 'error': 'Platform not yet implemented'}

            except Exception as e:
                error_msg = str(e)
                errors.append(f"{platform}: {error_msg}")
                results[platform] = {'success': False, 'error': error_msg}

        # Update final status
        if errors:
            multi_platform.update_queue_status(queue_id, 'failed', '; '.join(errors))
            return jsonify({
                'success': False,
                'error': 'Some platforms failed',
                'results': results,
                'errors': errors
            }), 500
        else:
            multi_platform.update_queue_status(queue_id, 'completed')
            return jsonify({
                'success': True,
                'message': 'Published to all platforms successfully',
                'results': results
            })

    except Exception as e:
        print(f"[QUEUE] Error processing queue item {queue_id}: {e}")
        import traceback
        traceback.print_exc()
        multi_platform.update_queue_status(queue_id, 'failed', str(e))
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/published', methods=['GET'])
def get_published_videos():
    """Get published videos for user"""
    if not multi_platform:
        return jsonify({'success': False, 'error': 'Multi-platform publisher not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    platform = request.args.get('platform')

    try:
        published = multi_platform.get_published_videos(user_email, platform)
        return jsonify({'success': True, 'published': published})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/connected', methods=['GET'])
def get_connected_platforms():
    """Get connected platforms for user"""
    if not multi_platform:
        return jsonify({'success': False, 'error': 'Multi-platform publisher not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        platforms = multi_platform.get_connected_platforms(user_email)
        return jsonify({'success': True, 'platforms': platforms})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/multi-platform')
def multi_platform_page():
    """Serve the multi-platform publisher page"""
    return send_from_directory('topic-picker-standalone', 'multi-platform.html')


# ===========================================
# PLATFORM API OAUTH & UPLOAD ENDPOINTS
# ===========================================

@app.route('/api/oauth/youtube/authorize', methods=['GET'])
def youtube_oauth_authorize():
    """Start YouTube OAuth flow"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        print("[YOUTUBE] Authorize: Failed to get user from session")
        return error_response, error_code

    print(f"[YOUTUBE] Authorize: Starting OAuth for user: {user_email}")

    redirect_uri = request.args.get('redirect_uri', request.host_url + 'api/oauth/youtube/callback')

    try:
        auth_url = platform_api.get_youtube_auth_url(user_email, redirect_uri)
        if auth_url:
            # Redirect to Google OAuth instead of returning JSON
            from flask import redirect
            return redirect(auth_url)
        else:
            return jsonify({'success': False, 'error': 'Failed to generate auth URL. Check YouTube credentials.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/oauth/youtube/callback', methods=['GET'])
def youtube_oauth_callback():
    """Handle YouTube/Google Calendar OAuth callback (shared endpoint)"""
    if not platform_api:
        return "Platform API not available", 500

    code = request.args.get('code')
    state = request.args.get('state')

    if not code or not state:
        return "Missing code or state", 400

    # Get user from session
    session_id = request.cookies.get('session_id')
    print(f"[OAUTH] Callback: session_id from cookie: {session_id[:10] if session_id else 'None'}...")

    if not session_id:
        print("[OAUTH] Callback: No session_id cookie found")
        return "Not authenticated", 401

    result = database.get_session(session_id)
    if not result.get('success'):
        print(f"[OAUTH] Callback: Invalid session for session_id: {session_id[:10]}...")
        return "Invalid session", 401

    user_email = result['user']['email']
    print(f"[OAUTH] Callback: Retrieved user email from session: {user_email}")

    redirect_uri = request.host_url + 'api/oauth/youtube/callback'

    # Check which OAuth flow this is by checking stored state
    is_calendar = False
    try:
        calendar_state = platform_api._get_oauth_state(user_email, 'google_calendar')
        if calendar_state == state:
            is_calendar = True
            print(f"[OAUTH] Detected Google Calendar OAuth flow")
    except:
        pass

    try:
        if is_calendar:
            # Handle Google Calendar callback
            success = platform_api.handle_google_calendar_callback(user_email, code, state, redirect_uri)
            if success:
                return """
                    <html>
                    <body style="font-family:Arial; text-align:center; padding-top:100px; background:#111827; color:#E8EBFF;">
                        <h2 style="color:#22c55e;">✓ Google Calendar Connected Successfully!</h2>
                        <p>Calendar events will now be automatically synced.</p>
                        <p style="color:#A8B3CF;">Redirecting back to Channel Manager...</p>
                        <script>
                            setTimeout(() => { window.location.href = '/channel-manager'; }, 2000);
                        </script>
                    </body>
                    </html>
                """
        else:
            # Handle YouTube callback
            success = platform_api.handle_youtube_callback(user_email, code, state, redirect_uri)
            if success:
                # Fetch and store channel info
                if analytics_manager:
                    try:
                        channel_info = platform_api.get_and_store_youtube_channel(user_email, analytics_manager)
                        if channel_info.get('success'):
                            print(f"[YOUTUBE] Channel stored: {channel_info.get('title')} (ID: {channel_info.get('channel_id')})")
                        else:
                            print(f"[YOUTUBE] Warning: Could not fetch channel info: {channel_info.get('error')}")
                    except Exception as e:
                        print(f"[YOUTUBE] Warning: Error storing channel info: {e}")

                return """
                    <html>
                    <body>
                        <h2>YouTube Connected Successfully!</h2>
                        <p>You can now close this window and return to MSS.</p>
                        <script>
                            setTimeout(() => { window.location.href = '/channel-manager'; }, 2000);
                        </script>
                    </body>
                    </html>
                """

        print(f"[OAUTH] OAuth callback returned False for user: {user_email}")
        return "OAuth callback failed - Check server logs for details", 500
    except Exception as e:
        print(f"[OAUTH] Callback error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error: {str(e)}", 500

@app.route('/api/platform/connections', methods=['GET'])
def get_platform_connections():
    """Get user's connected platforms"""
    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    # Import at function level to avoid initialization issues
    from multi_platform import MultiPlatformPublisher

    try:
        mp = MultiPlatformPublisher()
        platforms = mp.get_connected_platforms(user_email)
        return jsonify({'success': True, 'platforms': platforms})
    except Exception as e:
        print(f"[PLATFORM-CONNECTIONS] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/oauth/google-calendar/authorize', methods=['GET'])
def google_calendar_oauth_authorize():
    """Start Google Calendar OAuth flow (uses YouTube callback)"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        print("[GOOGLE-CAL] Authorize: Failed to get user from session")
        return error_response, error_code

    print(f"[GOOGLE-CAL] Authorize: Starting OAuth for user: {user_email}")

    # Use YouTube callback URI (already registered in Google Cloud Console)
    redirect_uri = request.host_url + 'api/oauth/youtube/callback'

    try:
        auth_url = platform_api.get_google_calendar_auth_url(user_email, redirect_uri)
        if auth_url:
            from flask import redirect
            return redirect(auth_url)
        else:
            return jsonify({'success': False, 'error': 'Failed to generate auth URL. Check Google Calendar credentials.'}), 500
    except Exception as e:
        print(f"[GOOGLE-CAL] Authorize error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/oauth/google-calendar/callback', methods=['GET'])
def google_calendar_oauth_callback():
    """Handle Google Calendar OAuth callback"""
    if not platform_api:
        return "Platform API not available", 500

    code = request.args.get('code')
    state = request.args.get('state')

    if not code or not state:
        return "Missing code or state", 400

    # Get user from session
    session_id = request.cookies.get('session_id')
    print(f"[GOOGLE-CAL] Callback: session_id from cookie: {session_id[:10] if session_id else 'None'}...")

    if not session_id:
        print("[GOOGLE-CAL] Callback: No session_id cookie found")
        return "Not authenticated", 401

    result = database.get_session(session_id)
    if not result.get('success'):
        print(f"[GOOGLE-CAL] Callback: Invalid session for session_id: {session_id[:10]}...")
        return "Invalid session", 401

    user_email = result['user']['email']
    print(f"[GOOGLE-CAL] Callback: Retrieved user email from session: {user_email}")

    redirect_uri = request.host_url + 'api/oauth/google-calendar/callback'

    try:
        success = platform_api.handle_google_calendar_callback(user_email, code, state, redirect_uri)
        if success:
            return """
                <html>
                <body style="font-family:Arial; text-align:center; padding-top:100px; background:#111827; color:#E8EBFF;">
                    <h2 style="color:#22c55e;">✓ Google Calendar Connected Successfully!</h2>
                    <p>Calendar events will now be automatically synced.</p>
                    <p style="color:#A8B3CF;">Redirecting back to Channel Manager...</p>
                    <script>
                        setTimeout(() => { window.location.href = '/channel-manager'; }, 2000);
                    </script>
                </body>
                </html>
            """
        else:
            print(f"[GOOGLE-CAL] OAuth callback returned False for user: {user_email}")
            return "OAuth callback failed - Check server logs for details", 500
    except Exception as e:
        print(f"[GOOGLE-CAL] Callback error: {e}")
        return f"Error: {str(e)}", 500

@app.route('/api/oauth/tiktok/authorize', methods=['GET'])
def tiktok_oauth_authorize():
    """Start TikTok OAuth flow"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    redirect_uri = request.args.get('redirect_uri', request.host_url + 'api/oauth/tiktok/callback')

    try:
        auth_url = platform_api.get_tiktok_auth_url(user_email, redirect_uri)
        if auth_url:
            return jsonify({'success': True, 'auth_url': auth_url})
        else:
            return jsonify({'success': False, 'error': 'Failed to generate auth URL. Check TikTok credentials.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/oauth/tiktok/callback', methods=['GET'])
def tiktok_oauth_callback():
    """Handle TikTok OAuth callback"""
    if not platform_api:
        return "Platform API not available", 500

    code = request.args.get('code')
    state = request.args.get('state')

    if not code or not state:
        return "Missing code or state", 400

    session_id = request.cookies.get('session_id')
    if not session_id:
        return "Not authenticated", 401

    result = database.get_session(session_id)
    if not result.get('success'):
        return "Invalid session", 401

    user_email = result['user']['email']

    try:
        success = platform_api.handle_tiktok_callback(user_email, code, state)
        if success:
            return """
                <html>
                <body>
                    <h2>TikTok Connected Successfully!</h2>
                    <p>You can now close this window and return to MSS.</p>
                    <script>
                        setTimeout(() => window.close(), 2000);
                    </script>
                </body>
                </html>
            """
        else:
            return "OAuth callback failed", 500
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/oauth/instagram/authorize', methods=['GET'])
def instagram_oauth_authorize():
    """Start Instagram OAuth flow"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    redirect_uri = request.args.get('redirect_uri', request.host_url + 'api/oauth/instagram/callback')

    try:
        auth_url = platform_api.get_instagram_auth_url(user_email, redirect_uri)
        if auth_url:
            return jsonify({'success': True, 'auth_url': auth_url})
        else:
            return jsonify({'success': False, 'error': 'Failed to generate auth URL. Check Instagram credentials.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/oauth/instagram/callback', methods=['GET'])
def instagram_oauth_callback():
    """Handle Instagram OAuth callback"""
    if not platform_api:
        return "Platform API not available", 500

    code = request.args.get('code')
    state = request.args.get('state')

    if not code or not state:
        return "Missing code or state", 400

    session_id = request.cookies.get('session_id')
    if not session_id:
        return "Not authenticated", 401

    result = database.get_session(session_id)
    if not result.get('success'):
        return "Invalid session", 401

    user_email = result['user']['email']
    redirect_uri = request.host_url + 'api/oauth/instagram/callback'

    try:
        success = platform_api.handle_instagram_callback(user_email, code, state, redirect_uri)
        if success:
            return """
                <html>
                <body>
                    <h2>Instagram Connected Successfully!</h2>
                    <p>You can now close this window and return to MSS.</p>
                    <script>
                        setTimeout(() => window.close(), 2000);
                    </script>
                </body>
                </html>
            """
        else:
            return "OAuth callback failed", 500
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/oauth/facebook/authorize', methods=['GET'])
def facebook_oauth_authorize():
    """Start Facebook OAuth flow"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    redirect_uri = request.args.get('redirect_uri', request.host_url + 'api/oauth/facebook/callback')

    try:
        auth_url = platform_api.get_facebook_auth_url(user_email, redirect_uri)
        if auth_url:
            # Redirect directly to Facebook auth (like YouTube does)
            return redirect(auth_url)
        else:
            return jsonify({'success': False, 'error': 'Failed to generate auth URL. Check Facebook credentials.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/oauth/facebook/callback', methods=['GET'])
def facebook_oauth_callback():
    """Handle Facebook OAuth callback"""
    if not platform_api:
        return "Platform API not available", 500

    code = request.args.get('code')
    state = request.args.get('state')

    if not code or not state:
        return "Missing code or state", 400

    session_id = request.cookies.get('session_id')
    if not session_id:
        return "Not authenticated", 401

    result = database.get_session(session_id)
    if not result.get('success'):
        return "Invalid session", 401

    user_email = result['user']['email']
    redirect_uri = request.host_url + 'api/oauth/facebook/callback'

    try:
        success = platform_api.handle_facebook_callback(user_email, code, state, redirect_uri)
        if success:
            return """
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h2 style="color: #1877F2;">Facebook Connected Successfully!</h2>
                    <p>You can now close this window and return to MSS.</p>
                    <script>
                        setTimeout(() => {
                            window.opener.postMessage({type: 'oauth_complete', platform: 'facebook'}, '*');
                            window.close();
                        }, 2000);
                    </script>
                </body>
                </html>
            """
        else:
            return "OAuth callback failed", 500
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/platforms/upload/youtube', methods=['POST'])
def upload_youtube():
    """Upload video to YouTube"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    data = request.get_json()
    video_filename = data.get('video_filename')
    title = data.get('title')
    description = data.get('description', '')
    tags = data.get('tags', [])
    category_id = data.get('category_id', '22')
    privacy = data.get('privacy', 'public')

    if not video_filename or not title:
        return jsonify({'success': False, 'error': 'video_filename and title required'}), 400

    # Construct video path
    video_path = os.path.join('out', video_filename)

    try:
        result = platform_api.upload_to_youtube(
            user_email, video_path, title, description, tags, category_id, privacy
        )

        # Track in analytics if successful
        if result.get('success') and analytics_manager:
            try:
                # Track video
                video_id = analytics_manager.track_video_creation(user_email, {
                    'title': title,
                    'description': description,
                    'filename': video_filename,
                    'topic_data': {}
                })

                # Mark as published
                analytics_manager.update_video_published(video_id, 'youtube')

                # Record publication in multi-platform
                if multi_platform:
                    multi_platform.record_publication(
                        user_email, video_id, 'youtube',
                        result.get('video_id'), result.get('url'),
                        title, description
                    )
            except Exception as e:
                print(f"[YOUTUBE] Error tracking in analytics: {e}")

        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/upload/tiktok', methods=['POST'])
def upload_tiktok():
    """Upload video to TikTok"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    data = request.get_json()
    video_filename = data.get('video_filename')
    title = data.get('title')
    description = data.get('description', '')
    privacy_level = data.get('privacy_level', 'PUBLIC_TO_EVERYONE')

    if not video_filename or not title:
        return jsonify({'success': False, 'error': 'video_filename and title required'}), 400

    video_path = os.path.join('out', video_filename)

    try:
        result = platform_api.upload_to_tiktok(user_email, video_path, title, description, privacy_level)

        # Track in analytics if successful
        if result.get('success') and analytics_manager:
            try:
                video_id = analytics_manager.track_video_creation(user_email, {
                    'title': title,
                    'description': description,
                    'filename': video_filename,
                    'topic_data': {}
                })
                analytics_manager.update_video_published(video_id, 'tiktok')

                if multi_platform:
                    multi_platform.record_publication(
                        user_email, video_id, 'tiktok',
                        result.get('video_id'), '',
                        title, description
                    )
            except Exception as e:
                print(f"[TIKTOK] Error tracking in analytics: {e}")

        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/connection-status', methods=['GET'])
def platform_connection_status():
    """Get connection status for all platforms"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        platforms = ['youtube', 'tiktok', 'instagram']
        status = {}

        for platform in platforms:
            status[platform] = platform_api.is_platform_connected(user_email, platform)

        connected_list = platform_api.get_connected_platforms_list(user_email)

        return jsonify({
            'success': True,
            'status': status,
            'connected': connected_list
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/platforms/disconnect/<platform>', methods=['POST'])
def disconnect_platform_endpoint(platform):
    """Disconnect a platform"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        success = platform_api.disconnect_platform(user_email, platform)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/youtube/channel-info', methods=['GET'])
def youtube_channel_info():
    """Get YouTube channel information for the authenticated user"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        result = platform_api.get_youtube_channel_info(user_email)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/youtube/video-stats/<video_id>', methods=['GET'])
def youtube_video_stats(video_id):
    """Get statistics for a specific YouTube video"""
    if not platform_api:
        return jsonify({'success': False, 'error': 'Platform API not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        result = platform_api.get_youtube_video_stats(user_email, video_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/youtube/sync-metrics', methods=['POST'])
def youtube_sync_metrics():
    """Sync all YouTube video metrics to analytics database"""
    if not platform_api or not analytics_manager:
        return jsonify({'success': False, 'error': 'Platform API or Analytics not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        # First, get and store the YouTube channel info
        channel_info = platform_api.get_and_store_youtube_channel(user_email, analytics_manager)

        if not channel_info.get('success'):
            return jsonify(channel_info), 500

        channel_account_id = channel_info.get('channel_account_id')

        # Get all videos from YouTube channel
        result = platform_api.get_youtube_channel_videos(user_email, max_results=50)

        if not result.get('success'):
            return jsonify(result), 500

        videos = result.get('videos', [])
        synced_count = 0
        updated_count = 0

        for video in videos:
            video_id_yt = video['video_id']

            # Check if this video already exists in analytics by platform_video_id
            conn = sqlite3.connect(analytics_manager.db_path)
            c = conn.cursor()
            c.execute('''
                SELECT v.id FROM videos v
                JOIN published_videos pv ON v.id = pv.video_id
                WHERE pv.platform_video_id = ? AND v.user_email = ?
            ''', (video_id_yt, user_email))
            existing = c.fetchone()
            conn.close()

            if existing:
                # Update existing video metrics
                analytics_manager.record_video_metrics(existing[0], {
                    'views': video['views'],
                    'likes': video['likes'],
                    'comments': video['comments'],
                    'shares': 0,
                    'watch_time_minutes': 0,
                    'ctr': 0,
                    'avg_view_duration': 0
                }, 'youtube')
                updated_count += 1
            else:
                # Create new video entry with channel_account_id
                video_data = {
                    'title': video['title'],
                    'description': video['description'],
                    'filename': f"youtube_{video_id_yt}.mp4",
                    'topic_data': {}
                }
                video_id = analytics_manager.track_video_creation(user_email, video_data)

                # Link video to channel account
                if channel_account_id:
                    conn = sqlite3.connect(analytics_manager.db_path)
                    c = conn.cursor()
                    c.execute('UPDATE videos SET channel_account_id = ? WHERE id = ?',
                             (channel_account_id, video_id))
                    conn.commit()
                    conn.close()

                # Mark as published on YouTube
                analytics_manager.update_video_published(video_id, 'youtube')

                # Record initial metrics
                analytics_manager.record_video_metrics(video_id, {
                    'views': video['views'],
                    'likes': video['likes'],
                    'comments': video['comments'],
                    'shares': 0,
                    'watch_time_minutes': 0,
                    'ctr': 0,
                    'avg_view_duration': 0
                }, 'youtube')

                # Record in multi-platform if available
                if multi_platform:
                    multi_platform.record_publication(
                        user_email, video_id, 'youtube',
                        video_id_yt, f"https://www.youtube.com/watch?v={video_id_yt}",
                        video['title'], video['description']
                    )

                synced_count += 1

        # Update last sync time for channel
        if channel_account_id:
            analytics_manager.update_channel_sync_time(channel_account_id)

        return jsonify({
            'success': True,
            'synced': synced_count,
            'updated': updated_count,
            'total': len(videos),
            'channel': channel_info.get('title'),
            'message': f"Synced {synced_count} new videos, updated {updated_count} existing videos from {channel_info.get('title')}"
        })

    except Exception as e:
        print(f"[YOUTUBE] Sync error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/channels/list', methods=['GET'])
def list_channels():
    """Get all YouTube channels for the user"""
    if not analytics_manager:
        return jsonify({'success': False, 'error': 'Analytics not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        platform = request.args.get('platform', 'youtube')
        channels = analytics_manager.get_user_channels(user_email, platform)

        return jsonify({
            'success': True,
            'channels': channels,
            'count': len(channels)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/channels/set-default', methods=['POST'])
def set_default_channel():
    """Set a channel as the default"""
    if not analytics_manager:
        return jsonify({'success': False, 'error': 'Analytics not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    data = request.get_json()
    channel_account_id = data.get('channel_account_id')

    if not channel_account_id:
        return jsonify({'success': False, 'error': 'channel_account_id required'}), 400

    try:
        success = analytics_manager.set_default_channel(user_email, channel_account_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/channels/remove', methods=['POST'])
def remove_channel():
    """Remove a channel account"""
    if not analytics_manager:
        return jsonify({'success': False, 'error': 'Analytics not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    data = request.get_json()
    channel_account_id = data.get('channel_account_id')

    if not channel_account_id:
        return jsonify({'success': False, 'error': 'channel_account_id required'}), 400

    try:
        success = analytics_manager.remove_channel_account(user_email, channel_account_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/channels/add-youtube', methods=['POST'])
def add_youtube_channel():
    """
    Manually add a YouTube channel by connecting via OAuth
    (Triggers OAuth flow for additional channel)
    """
    if not platform_api or not analytics_manager:
        return jsonify({'success': False, 'error': 'Platform API or Analytics not available'}), 500

    user_email, error_response, error_code = _get_user_from_session()
    if error_response:
        return error_response, error_code

    try:
        # Get and store the connected YouTube channel
        channel_info = platform_api.get_and_store_youtube_channel(user_email, analytics_manager)

        return jsonify(channel_info)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/proxy-image')
def proxy_image():
    """Proxy external images to avoid CORS issues (e.g., YouTube thumbnails)"""
    try:
        url = request.args.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        # Security: Only allow specific domains
        allowed_domains = ['yt3.ggpht.com', 'yt3.googleusercontent.com', 'i.ytimg.com']
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        if domain not in allowed_domains:
            return jsonify({'error': 'Domain not allowed'}), 403

        # Fetch the image
        response = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()

        # Return the image with appropriate headers
        return Response(
            response.content,
            mimetype=response.headers.get('Content-Type', 'image/jpeg'),
            headers={
                'Cache-Control': 'public, max-age=86400',  # Cache for 1 day
                'Access-Control-Allow-Origin': '*'
            }
        )
    except Exception as e:
        print(f"[PROXY-IMAGE] Error proxying image: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    print(f"\n[SERVER] Starting Flask server on http://127.0.0.1:{port}")
    print(f"[SERVER] Debug mode: {debug}")
    print(f"[SERVER] Registered routes:")
    for rule in app.url_map.iter_rules():
        if 'proxy' in str(rule):
            print(f"  - {rule}")
    app.run(host='127.0.0.1', port=port, debug=debug, threaded=True)

