"""
Standalone API server for MSS web UI
No n8n required - directly calls Python functions
"""
import os
import json
import time
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from PIL import Image, ImageDraw, ImageFont
import io
import requests

# Add parent directory to path so we can import scripts
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

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
CORS(app)  # Enable CORS for local development

@app.route('/')
def _root_health():
    return jsonify({
        'ok': True,
        'service': 'MSS API',
        'endpoints': ['/post-process-video', '/get-avatar-library', '/out/<file>']
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

        outdir = Path('thumbnails')
        outdir.mkdir(exist_ok=True)

        # Prefer AI image generation with NO TEXT
        def _openai_background(prompt: str, outdir: Path) -> Path:
            from openai import OpenAI
            import requests as _req
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
            resp = client.images.generate(
                model=model,
                prompt=prompt,
                size="1792x1024",
                quality="standard",
                n=1,
            )
            image_url = resp.data[0].url
            r = _req.get(image_url, timeout=30)
            r.raise_for_status()
            fname = f"meme_bg_{int(time.time())}.png"
            path = outdir / fname
            path.write_bytes(r.content)
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

        img_path = None
        source = None
        try:
            if os.getenv("OPENAI_API_KEY"):
                bg_prompt = (
                    f"Design a cinematic, high-contrast abstract background for a YouTube thumbnail. "
                    f"Topic: {title}. Hook: {hook}. Description: {description}. Keywords: {key_str}. "
                    f"Mood: bold, modern, subtle depth, soft lighting, safe-zone friendly. "
                    f"CRITICAL: NO TEXT, NO LETTERS, NO WORDS anywhere in the image."
                )
                img_path = _openai_background(bg_prompt, outdir)
                source = 'openai'
        except Exception as _e:
            print(f"[BG AI] Falling back to gradient: {_e}")

        if img_path is None:
            img_path = _gradient_background(outdir)
            source = 'gradient'

        url = f"http://localhost:5000/thumbnails/{img_path.name}" if '://' not in str(img_path) else str(img_path)
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
        key_str = ', '.join([str(k) for k in keywords][:10])

        outdir = Path('thumbnails')
        outdir.mkdir(exist_ok=True)

        def _openai_background(prompt: str, outdir: Path) -> Path:
            from openai import OpenAI
            import requests as _req
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
            resp = client.images.generate(
                model=model,
                prompt=prompt,
                size="1792x1024",
                quality="standard",
                n=1,
            )
            image_url = resp.data[0].url
            r = _req.get(image_url, timeout=30)
            r.raise_for_status()
            fname = f"meme_bg_{int(time.time())}.png"
            path = outdir / fname
            path.write_bytes(r.content)
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

        img_path = None
        source = None
        try:
            if os.getenv("OPENAI_API_KEY"):
                if prompt_override:
                    bg_prompt = prompt_override
                else:
                    bg_prompt = (
                        f"Design a cinematic, high-contrast abstract background for a YouTube thumbnail. "
                        f"Topic: {title}. Hook: {hook}. Description: {description}. Keywords: {key_str}. "
                        f"Mood: bold, modern, subtle depth, soft lighting, safe-zone friendly."
                    )
                if enforce_no_text:
                    bg_prompt += " CRITICAL: This is a BACKGROUND ONLY. NO TEXT/WORDS/LETTERS anywhere."
                img_path = _openai_background(bg_prompt, outdir)
                source = 'openai'
        except Exception as _e:
            print(f"[BG AI] Falling back to gradient (clean route): {_e}")

        if img_path is None:
            img_path = _gradient_background(outdir)
            source = 'gradient'

        url = f"http://localhost:5000/thumbnails/{img_path.name}"
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
            'yt_title': f"{title} — What You Need to Know",
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
        if topic.get('generate_ai_thumbnail'):
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
        print("=" * 70)
        print("[VIDEO] POST-PROCESS VIDEO ENDPOINT CALLED")
        print("=" * 70)

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

        video_path = outdir / f"uploaded_video_{int(time.time())}.mp4"
        video_file.save(video_path)
        print(f"[OK] Video saved: {video_path}")

        # Handle audio
        if audio_file:
            audio_path = outdir / f"uploaded_audio_{int(time.time())}.mp3"
            audio_file.save(audio_path)
            print(f"[OK] Audio saved: {audio_path}")
        else:
            # Extract audio from video using FFmpeg
            print("[EXTRACT] Extracting audio from video...")
            import subprocess
            import imageio_ffmpeg

            audio_path = outdir / f"extracted_audio_{int(time.time())}.mp3"
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

            cmd = [
                ffmpeg,
                '-i', str(video_path),
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
            if include_logo_early:
                logo_url = None
                # Allow UI to pass an explicit filename and/or position
                ui_logo_filename = (request.form.get('logo_filename') or '').strip()
                ui_logo_position = (request.form.get('logo_position') or '').strip()
                logo_position = ui_logo_position if ui_logo_position else 'bottom-left'
                # 1) Try UI override, then active logo from web/logo_library.json
                logo_path = None
                if ui_logo_filename:
                    cand_mss = Path(__file__).parent.parent / 'logos' / ui_logo_filename
                    cand_web = Path(__file__).parent / 'logos' / ui_logo_filename
                    print(f"[LOGO-FIRST] UI override => MSS: {cand_mss.exists()} {cand_mss} | WEB: {cand_web.exists()} {cand_web}")
                    logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
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
                                    cand_web = Path(__file__).parent / 'logos' / fname
                                    print(f"[LOGO-FIRST] Candidates => MSS: {cand_mss.exists()} {cand_mss} | WEB: {cand_web.exists()} {cand_web}")
                                    logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
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
                                cand_web = Path(__file__).parent / 'logos' / fname
                                print(f"[LOGO-FIRST] Candidates => MSS: {cand_mss.exists()} {cand_mss} | WEB: {cand_web.exists()} {cand_web}")
                                logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
                    except Exception:
                        pass
                if logo_path and logo_path.exists():
                    print(f"[LOGO-FIRST] Applying logo before avatar: {logo_path}")
                    logo_opacity = request.form.get('logo_opacity', '0.6')
                    try:
                        logo_opacity_val = max(0.0, min(1.0, float(logo_opacity)))
                    except Exception:
                        logo_opacity_val = 0.6
                    if logo_path and logo_path.exists():
                            print(f"[LOGO-FIRST] Applying logo before avatar: {logo_path}")
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
                            filter_complex = (
                                f"[1:v]scale=-1:100,format=yuva420p,colorchannelmixer=aa={logo_opacity_val},"
                                f"fade=t=in:st=0:d=0.5:alpha=1[logo];[0:v][logo]overlay={pos}"
                            )
                            video_with_logo = outdir / f"video_with_logo_{int(time.time())}.mp4"
                            cmd = [
                                ffmpeg,
                                '-i', str(current_video),
                                '-i', str(logo_path),
                                '-filter_complex', filter_complex,
                                '-c:v', 'libx264',
                                '-c:a', 'copy',
                                '-y', str(video_with_logo)
                            ]
                            result = subprocess.run(cmd, capture_output=True, text=True)
                            if result.returncode == 0 and video_with_logo.exists():
                                current_video = video_with_logo
                                logo_already_applied = True
                                print(f"[LOGO-FIRST] Logo applied: {current_video}")
                            else:
                                print(f"[LOGO-FIRST] Logo overlay failed, continuing without early logo: {result.stderr[:300] if result.stderr else 'no stderr'}")
        except Exception as e:
            print(f"[LOGO-FIRST] Exception while applying early logo: {e}")

        # Upload audio to Drive (needed for D-ID). If static avatar requested, skip D-ID upload entirely.
        if include_avatar and (not avatar_static) and (not skip_did):
            print("[UPLOAD] Uploading audio to Google Drive for D-ID...")
            audio_drive = drive_upload_public(audio_path, "MSS_Audio")
            audio_url = audio_drive['download_url']
            print(f"[OK] Audio uploaded: {audio_url}")
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
                                    base_video_path=video_path,
                                    avatar_image_path=avatar_local_path,
                                    output_path=static_out,
                                    avatar_position=selected_avatar.get('position', 'bottom-right'),
                                    avatar_scale=selected_avatar.get('scale', 25) / 100.0,
                                    animate=False
                                )
                                if static_out.exists():
                                    avatar_video_path = static_out
                                    print(f"[OK] Static avatar overlay created: {avatar_video_path}")
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

            # Overlay avatar on video
            # eof_action=pass means if avatar ends, continue with main video (avatar will fade out)
            filter_complex = f"[1:v]scale=iw*{scale}:ih*{scale}[avatar];[0:v][avatar]overlay={pos}:eof_action=pass"

            cmd = [
                ffmpeg,
                '-i', str(video_path),
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
            print(f"[DEBUG] Main video: {video_path} (size: {video_path.stat().st_size} bytes)")
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

            if result.returncode != 0:
                print(f"[!] Avatar overlay FAILED")
                print(f"[!] Full error: {result.stderr}")
                video_with_avatar = video_path
            else:
                if video_with_avatar.exists():
                    print(f"[OK] Avatar overlay SUCCESS")
                    print(f"[OK] Output size: {video_with_avatar.stat().st_size} bytes")
                    print(f"[OK] Video with avatar: {video_with_avatar}")
                else:
                    print(f"[!] Avatar overlay claimed success but file not found!")
                    video_with_avatar = video_path
        else:
            video_with_avatar = current_video
            # Try a last-resort static overlay directly onto the base video
            try:
                if selected_avatar and avatar_local_path and avatar_local_path.exists():
                    print("[OVERLAY] Animated avatar failed; applying static avatar overlay to base video...")
                    from scripts.avatar_animator import add_avatar_to_video
                    static_out = outdir / f"video_with_avatar_{int(time.time())}.mp4"
                    add_avatar_to_video(
                        base_video_path=video_path,
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
                cand_web = Path(__file__).parent / 'logos' / ui_logo_filename
                print(f"[LOGO-LATE] UI override => MSS: {cand_mss.exists()} {cand_mss} | WEB: {cand_web.exists()} {cand_web}")
                logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
            # Active logo
            library_file = Path(__file__).parent / 'logo_library.json'
            if library_file.exists() and (not logo_path):
                try:
                    lib = json.loads(library_file.read_text(encoding='utf-8'))
                    active = next((l for l in lib.get('logos', []) if l.get('active')), None)
                    if active:
                        fname = active.get('filename') or (active.get('url','').split('/')[-1])
                        if fname:
                            cand_mss = Path(__file__).parent.parent / 'logos' / fname
                            cand_web = Path(__file__).parent / 'logos' / fname
                            print(f"[LOGO-LATE] Candidates => MSS: {cand_mss.exists()} {cand_mss} | WEB: {cand_web.exists()} {cand_web}")
                            logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
                except Exception:
                    pass
            # Position / fallback URL
            ts_path = Path(__file__).parent.parent / 'thumbnail_settings.json'
            if ts_path.exists():
                try:
                    ts = json.loads(ts_path.read_text(encoding='utf-8'))
                    logo_position = ts.get('logoPosition', logo_position)
                    if not logo_path and ts.get('logoUrl'):
                        fname = ts.get('logoUrl').split('/')[-1]
                        cand_mss = Path(__file__).parent.parent / 'logos' / fname
                        cand_web = Path(__file__).parent / 'logos' / fname
                        print(f"[LOGO-LATE] Candidates => MSS: {cand_mss.exists()} {cand_mss} | WEB: {cand_web.exists()} {cand_web}")
                        logo_path = cand_mss if cand_mss.exists() else (cand_web if cand_web.exists() else None)
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
                # Allow UI to control opacity; default to 0.6 (60% opaque)
                logo_opacity = request.form.get('logo_opacity', '0.6')
                try:
                    logo_opacity_val = max(0.0, min(1.0, float(logo_opacity)))
                except Exception:
                    logo_opacity_val = 0.6
                filter_complex = (
                    f"[1:v]scale=-1:100,format=yuva420p,colorchannelmixer=aa={logo_opacity_val},"
                    f"fade=t=in:st=0:d=0.5:alpha=1[logo];[0:v][logo]overlay={pos}"
                )
                cmd = [
                    ffmpeg,
                    '-i', str(current_video),
                    '-i', str(logo_path),
                    '-filter_complex', filter_complex,
                    '-c:v', 'libx264',
                    '-c:a', 'copy',  # Copy audio without re-encoding
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
            return jsonify({
                'success': True,
                'message': 'Video post-processed successfully (no intro/outro)',
                'files': {
                    'final_video': video_with_avatar.name,
                    'avatar_video': avatar_video_path.name if avatar_video_path else None
                }
            })

        # Get video dimensions from the main video
        probe_cmd = [
            ffmpeg,
            '-i', str(video_with_avatar),
            '-hide_banner'
        ]
        probe_result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # Parse dimensions (look for "Stream #0:0" line with resolution)
        import re
        match = re.search(r'(\d{3,})x(\d{3,})', probe_result.stdout)
        if match:
            width, height = int(match.group(1)), int(match.group(2))
        else:
            # Default to common portrait size
            width, height = 1080, 1920

        print(f"[INFO] Video dimensions: {width}x{height}")

        # Load active intro/outro from library
        # Intro/outro library is in parent directory (MSS/intro_outro_library.json)
        intro_outro_library_file = Path(__file__).parent.parent / "intro_outro_library.json"
        active_intro = None
        active_outro = None

        print(f"[DEBUG] Looking for intro/outro library at: {intro_outro_library_file}")
        print(f"[DEBUG] Intro/outro library exists: {intro_outro_library_file.exists()}")

        if intro_outro_library_file.exists():
            try:
                library = json.loads(intro_outro_library_file.read_text(encoding="utf-8"))
                active_intro = next((x for x in library.get('intros', []) if x.get('active')), None)
                active_outro = next((x for x in library.get('outros', []) if x.get('active')), None)

                if active_intro:
                    print(f"[INTRO] Found active intro: {active_intro.get('name')}")
                if active_outro:
                    print(f"[OUTRO] Found active outro: {active_outro.get('name')}")
            except Exception as e:
                print(f"[WARN] Could not load intro/outro library: {e}")

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
            # Get current dimensions
            probe_cmd = [
                ffmpeg,
                '-i', str(input_path),
                '-hide_banner'
            ]
            probe_result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            match = re.search(r'(\d{3,})x(\d{3,})', probe_result.stdout)

            if match:
                current_width, current_height = int(match.group(1)), int(match.group(2))

                if current_width != target_width or current_height != target_height:
                    print(f"[RESIZE] Resizing {input_path.name} from {current_width}x{current_height} to {target_width}x{target_height}")
                    resize_cmd = [
                        ffmpeg,
                        '-i', str(input_path),
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
                print(f"[WARN] Could not determine dimensions for {input_path.name}, using as-is")
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

        # Concatenate using filter_complex concat with aresample and setpts to avoid NaN audio and ts issues
        print("[CONCAT] Concatenating intro + video + outro (filter_complex)...")

        final_video = outdir / f"final_with_intro_outro_{int(time.time())}.mp4"

        filter_complex = (
            "[0:v]setpts=PTS-STARTPTS[v0];"
            "[0:a]aresample=async=1:min_hard_compensation=0.010:first_pts=0,asetpts=N/SR/TB[a0];"
            "[1:v]setpts=PTS-STARTPTS[v1];"
            "[1:a]aresample=async=1:min_hard_compensation=0.010:first_pts=0,asetpts=N/SR/TB[a1];"
            "[2:v]setpts=PTS-STARTPTS[v2];"
            "[2:a]aresample=async=1:min_hard_compensation=0.010:first_pts=0,asetpts=N/SR/TB[a2];"
            "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]"
        )

        concat_cmd = [
            ffmpeg,
            '-i', str(intro_path_resized),
            '-i', str(current_video),
            '-i', str(outro_path_resized),
            '-filter_complex', filter_complex,
            '-map', '[v]',
            '-map', '[a]',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-y', str(final_video)
        ]

        print(f"[DEBUG] Concat command: {' '.join(concat_cmd)}")
        concat_result = subprocess.run(concat_cmd, capture_output=True, text=True)

        if concat_result.returncode != 0:
            print(f"[!] CONCAT FAILED with filter_complex")
            print(f"[!] Error: {concat_result.stderr[:500]}")

            # Fallback: normalize each clip, then concat using demuxer
            print("[FALLBACK] Normalizing clips and concatenating via demuxerâ€¦")
            def normalize_clip(src_path: Path, out_path: Path):
                print(f"[NORM] Normalizing clip: {src_path} -> {out_path}")
                norm_cmd = [
                    ffmpeg,
                    '-i', str(src_path),
                    '-vf', 'fps=30,format=yuv420p,setsar=1/1',
                    '-af', 'aformat=sample_fmts=s16:channel_layouts=stereo,aresample=async=1:min_hard_compensation=0.100:first_pts=0,asetpts=N/SR/TB,apad',
                    '-ar', '44100',
                    '-ac', '2',
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-movflags', '+faststart',
                    '-y', str(out_path)
                ]
                res = subprocess.run(norm_cmd, capture_output=True, text=True)
                if res.returncode != 0:
                    print(f"[WARN] Normalize pass1 failed: {res.stderr[:300]}")
                    norm2_cmd = [
                        ffmpeg,
                        '-i', str(src_path),
                        '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                        '-vf', 'fps=30,format=yuv420p,setsar=1/1',
                        '-map', '0:v:0',
                        '-map', '1:a:0',
                        '-c:v', 'libx264',
                        '-c:a', 'aac',
                        '-shortest',
                        '-movflags', '+faststart',
                        '-y', str(out_path)
                    ]
                    res2 = subprocess.run(norm2_cmd, capture_output=True, text=True)
                    if res2.returncode != 0:
                        print(f"[!] Normalize pass2 failed: {res2.stderr[:300]}")
                        raise Exception(f"Normalize failed: {src_path}")

            # Normalize each source to stable MP4 (H.264/AAC)
            n_intro = outdir / f"n_intro_{int(time.time())}.mp4"
            n_main = outdir / f"n_main_{int(time.time())}.mp4"
            n_outro = outdir / f"n_outro_{int(time.time())}.mp4"

            normalize_clip(intro_path_resized, n_intro)
            normalize_clip(current_video, n_main)
            normalize_clip(outro_path_resized, n_outro)

            # Remux normalized MP4s to TS and concat via concat: protocol
            print("[FALLBACK] Remuxing to TS and concatenating via concat protocol…")

            ts_intro = outdir / f"ts_intro_{int(time.time())}.ts"
            ts_main = outdir / f"ts_main_{int(time.time())}.ts"
            ts_outro = outdir / f"ts_outro_{int(time.time())}.ts"

            def remux_to_ts(src: Path, dst: Path):
                cmd = [
                    ffmpeg,
                    '-i', str(src),
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
                ffmpeg,
                '-i', concat_input,
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

        # Clean up temporary files
        # No temp concat list to clean up with filter_complex

        return jsonify({
            'success': True,
            'message': 'Video post-processed successfully',
            'files': {
                'final_video': final_video.name,
                'avatar_video': avatar_video_path.name if avatar_video_path else None
            }
        })

    except Exception as e:
        print(f"Error post-processing video: {e}")
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


@app.route('/intro_outro/<path:filename>', methods=['GET'])
def serve_intro_outro_file(filename):
    """Serve files from the intro_outro directory"""
    try:
        intro_outro_dir = Path("intro_outro").absolute()
        return send_from_directory(intro_outro_dir, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/logos/<path:filename>', methods=['GET'])
def serve_logo_file(filename):
    """Serve files from the logos directory"""
    try:
        logos_dir = Path("logos").absolute()
        return send_from_directory(logos_dir, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/thumbnails/<path:filename>', methods=['GET'])
def serve_thumbnail_file(filename):
    """Serve files from the thumbnails directory"""
    try:
        thumbnails_dir = Path("thumbnails").absolute()
        return send_from_directory(thumbnails_dir, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/get-intro-outro-library', methods=['GET'])
def get_intro_outro_library():
    """Get all saved intros and outros"""
    try:
        # Intro/outro library is in parent directory (MSS/intro_outro_library.json)
        library_file = Path(__file__).parent.parent / "intro_outro_library.json"

        if not library_file.exists():
            # Create default library with current intro/outro
            default_library = {
                "intros": [{
                    "id": "default",
                    "name": "Default Brand Intro",
                    "duration": 3.0,
                    "html": """<div style='width:100%;height:100%;background:linear-gradient(135deg, #0B0F19 0%, #1a2332 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;'>
                <div style='font-family:Inter,Arial,sans-serif;font-size:96px;font-weight:900;color:#FFD700;text-shadow:0 6px 20px rgba(255,215,0,.5);margin-bottom:20px;'>MANY SOURCES SAY</div>
                <div style='font-family:Inter,Arial,sans-serif;font-size:32px;font-weight:400;color:#94a3b8;font-style:italic;'>Because one source is NEVER enough</div>
            </div>""",
                    "active": True
                }],
                "outros": [{
                    "id": "default",
                    "name": "Default Brand Outro",
                    "duration": 3.0,
                    "html": """<div style='width:100%;height:100%;background:linear-gradient(135deg, #0B0F19 0%, #1a2332 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;'>
                <div style='font-family:Inter,Arial,sans-serif;font-size:72px;font-weight:900;color:#FFD700;text-shadow:0 6px 20px rgba(255,215,0,.5);margin-bottom:30px;'>THANKS FOR WATCHING!</div>
                <div style='font-family:Inter,Arial,sans-serif;font-size:48px;font-weight:700;color:#E8EBFF;margin-bottom:15px;'>MANY SOURCES SAY</div>
                <div style='font-family:Inter,Arial,sans-serif;font-size:28px;font-weight:400;color:#94a3b8;'>Subscribe for more insights</div>
            </div>""",
                    "active": True
                }]
            }
            library_file.write_text(json.dumps(default_library, indent=2), encoding="utf-8")

        library = json.loads(library_file.read_text(encoding="utf-8"))

        return jsonify({
            'success': True,
            'intros': library.get('intros', []),
            'outros': library.get('outros', [])
        })

    except Exception as e:
        print(f"Error loading intro/outro library: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save-intro-outro', methods=['POST'])
def save_intro_outro():
    """Save a new or updated intro/outro"""
    try:
        data = request.get_json()
        item_type = data.get('type')  # 'intro' or 'outro'
        item_id = data.get('id')
        name = data.get('name')
        duration = data.get('duration', 3.0)
        html = data.get('html')
        audio = data.get('audio', '')  # Audio text for TTS

        if not item_type or not name or not html:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Intro/outro library is in parent directory (MSS/intro_outro_library.json)
        library_file = Path(__file__).parent.parent / "intro_outro_library.json"
        library = json.loads(library_file.read_text(encoding="utf-8")) if library_file.exists() else {"intros": [], "outros": []}

        # Generate ID if new
        if not item_id:
            import time
            item_id = f"{item_type}_{int(time.time())}"

        new_item = {
            "id": item_id,
            "name": name,
            "duration": duration,
            "html": html,
            "audio": audio,
            "active": False
        }

        # Add or update
        items_key = 'intros' if item_type == 'intro' else 'outros'
        existing_idx = next((i for i, x in enumerate(library[items_key]) if x['id'] == item_id), None)

        if existing_idx is not None:
            # Keep active status when updating
            new_item['active'] = library[items_key][existing_idx]['active']
            library[items_key][existing_idx] = new_item
        else:
            library[items_key].append(new_item)

        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        return jsonify({'success': True, 'message': 'Saved successfully'})

    except Exception as e:
        print(f"Error saving intro/outro: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/set-active-intro-outro', methods=['POST'])
def set_active_intro_outro():
    """Set which intro/outro is active"""
    try:
        data = request.get_json()
        item_type = data.get('type')
        item_id = data.get('id')

        # Intro/outro library is in parent directory (MSS/intro_outro_library.json)
        library_file = Path(__file__).parent.parent / "intro_outro_library.json"
        library = json.loads(library_file.read_text(encoding="utf-8"))

        items_key = 'intros' if item_type == 'intro' else 'outros'

        # Deactivate all, then activate the selected one
        for item in library[items_key]:
            item['active'] = (item['id'] == item_id)

        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        return jsonify({'success': True})

    except Exception as e:
        print(f"Error setting active intro/outro: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete-intro-outro', methods=['POST'])
def delete_intro_outro():
    """Delete an intro/outro"""
    try:
        data = request.get_json()
        item_type = data.get('type')
        item_id = data.get('id')

        # Intro/outro library is in parent directory (MSS/intro_outro_library.json)
        library_file = Path(__file__).parent.parent / "intro_outro_library.json"
        library = json.loads(library_file.read_text(encoding="utf-8"))

        items_key = 'intros' if item_type == 'intro' else 'outros'
        library[items_key] = [x for x in library[items_key] if x['id'] != item_id]

        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        return jsonify({'success': True})

    except Exception as e:
        print(f"Error deleting intro/outro: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save-thumbnail-settings', methods=['POST'])
def save_thumbnail_settings():
    """Save thumbnail design settings"""
    try:
        settings = request.get_json()

        settings_file = Path("thumbnail_settings.json")
        settings_file.write_text(json.dumps(settings, indent=2), encoding="utf-8")

        return jsonify({'success': True, 'message': 'Thumbnail settings saved'})

    except Exception as e:
        print(f"Error saving thumbnail settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get-thumbnail-settings', methods=['GET'])
def get_thumbnail_settings():
    """Get saved thumbnail design settings"""
    try:
        settings_file = Path("thumbnail_settings.json")

        if settings_file.exists():
            settings = json.loads(settings_file.read_text(encoding="utf-8"))
            return jsonify({'success': True, 'settings': settings})
        else:
            return jsonify({'success': True, 'settings': None})

    except Exception as e:
        print(f"Error loading thumbnail settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/preview-tts', methods=['POST'])
def preview_tts():
    """Generate TTS audio preview for intro/outro"""
    try:
        data = request.get_json()
        text = data.get('text', '')

        if not text:
            return jsonify({'success': False, 'error': 'No text provided'}), 400

        # Import the TTS function from make_video
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
        from make_video import google_tts_to_drive

        # Generate TTS and upload to Drive
        audio_url = google_tts_to_drive(text, filename_prefix="preview_tts")

        return jsonify({'success': True, 'audio_url': audio_url})

    except Exception as e:
        print(f"Error generating TTS preview: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== AVATAR ENDPOINTS ====================

@app.route('/upload-avatar-file', methods=['POST'])
def upload_avatar_file():
    """Upload avatar image/video file locally and return URL"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Create avatars directory
        avatars_dir = Path("avatars")
        avatars_dir.mkdir(exist_ok=True)

        # Generate unique filename
        import mimetypes
        ext = Path(file.filename).suffix or '.png'
        unique_filename = f"avatar_{int(time.time())}{ext}"
        save_path = avatars_dir / unique_filename

        # Save file
        file.save(save_path)
        print(f"[OK] Avatar saved locally: {save_path}")

        # Check if it's an image file - if so, try to remove background
        mimetype, _ = mimetypes.guess_type(str(save_path))
        if mimetype and mimetype.startswith('image/'):
            try:
                from rembg import remove
                from PIL import Image

                print(f"Removing background from image: {file.filename}")
                input_img = Image.open(save_path)
                output_img = remove(input_img)

                # Save as PNG to preserve transparency
                png_path = save_path.with_suffix('.png')
                output_img.save(png_path)

                # Remove original if different extension
                if png_path != save_path:
                    save_path.unlink()
                    save_path = png_path
                    unique_filename = save_path.name

                print(f"[OK] Background removed successfully")
            except Exception as bg_error:
                print(f"[WARN] Background removal failed (continuing with original): {bg_error}")

        # Return full URL so it works from the frontend
        local_url = f"http://localhost:5000/avatars/{unique_filename}"
        print(f"[OK] Avatar URL: {local_url}")

        return jsonify({'success': True, 'url': local_url})

    except Exception as e:
        print(f"Error uploading avatar file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload-intro-outro-file', methods=['POST'])
def upload_intro_outro_file():
    """Upload intro/outro video file locally and return URL"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Create intro_outro directory
        intro_outro_dir = Path("intro_outro")
        intro_outro_dir.mkdir(exist_ok=True)

        # Generate unique filename
        ext = Path(file.filename).suffix or '.mp4'
        unique_filename = f"intro_outro_{int(time.time())}{ext}"
        save_path = intro_outro_dir / unique_filename

        # Save file
        file.save(save_path)
        print(f"[OK] Intro/Outro saved locally: {save_path}")

        # Return full URL so it works from the frontend
        local_url = f"http://localhost:5000/intro_outro/{unique_filename}"
        print(f"[OK] Intro/Outro URL: {local_url}")

        return jsonify({'success': True, 'url': local_url})

    except Exception as e:
        print(f"Error uploading intro/outro file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload-logo', methods=['POST'])
def upload_logo():
    """Upload MSS logo file locally and return URL"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Create logos directory
        logos_dir = Path("logos")
        logos_dir.mkdir(exist_ok=True)

        # Generate unique filename
        ext = Path(file.filename).suffix or '.png'
        unique_filename = f"mss_logo_{int(time.time())}{ext}"
        save_path = logos_dir / unique_filename

        # Save file
        file.save(save_path)
        print(f"[OK] Logo saved locally: {save_path}")

        # Return full URL so it works from the frontend
        local_url = f"http://localhost:5000/logos/{unique_filename}"
        print(f"[OK] Logo URL: {local_url}")

        return jsonify({'success': True, 'url': local_url})

    except Exception as e:
        print(f"Error uploading logo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload-logo-to-library', methods=['POST'])
def upload_logo_to_library():
    """Upload logo file to library"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Create logos directory
        logos_dir = Path("logos")
        logos_dir.mkdir(exist_ok=True)

        # Generate unique filename
        ext = Path(file.filename).suffix or '.png'
        unique_filename = f"logo_{int(time.time())}{ext}"
        save_path = logos_dir / unique_filename

        # Save file
        file.save(save_path)
        print(f"[OK] Logo saved locally: {save_path}")

        # Return full URL
        local_url = f"http://localhost:5000/logos/{unique_filename}"

        # Load library
        library_file = Path("logo_library.json")
        if library_file.exists():
            library = json.loads(library_file.read_text(encoding="utf-8"))
        else:
            library = {'logos': []}

        # Get name from request or use filename
        name = request.form.get('name', file.filename)

        # Add to library
        logo_entry = {
            'id': str(int(time.time() * 1000)),
            'name': name,
            'url': local_url,
            'filename': unique_filename,
            'active': False,
            'uploadedAt': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        library['logos'].append(logo_entry)
        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        print(f"[OK] Logo added to library: {name}")

        return jsonify({'success': True, 'url': local_url, 'logo': logo_entry})

    except Exception as e:
        print(f"Error uploading logo to library: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get-logo-library', methods=['GET'])
def get_logo_library():
    """Get all uploaded logos"""
    try:
        library_file = Path("logo_library.json")

        if not library_file.exists():
            return jsonify({'success': True, 'logos': []})

        # Read robustly; if corrupt, back up and return empty list
        try:
            raw = library_file.read_text(encoding="utf-8")
            library = json.loads(raw or "{}")
            logos = library.get('logos', []) if isinstance(library, dict) else []
            return jsonify({'success': True, 'logos': logos})
        except Exception as e:
            # Backup corrupt file so UI can continue
            try:
                backup = library_file.with_suffix('.json.bak')
                library_file.replace(backup)
            except Exception:
                pass
            print(f"[WARN] Corrupt logo_library.json; backed up and returning empty list: {e}")
            return jsonify({'success': True, 'logos': []})

    except Exception as e:
        print(f"Error loading logo library: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/set-active-logo', methods=['POST'])
def set_active_logo():
    """Set a logo as active (deactivates all others)"""
    try:
        data = request.get_json()
        logo_id = data.get('id')

        if not logo_id:
            return jsonify({'success': False, 'error': 'No logo ID provided'}), 400

        library_file = Path("logo_library.json")

        if not library_file.exists():
            return jsonify({'success': False, 'error': 'Logo library not found'}), 404

        library = json.loads(library_file.read_text(encoding="utf-8"))

        # Deactivate all logos
        for logo in library.get('logos', []):
            logo['active'] = False

        # Activate the selected logo
        found = False
        active_logo_url = None
        for logo in library.get('logos', []):
            if logo['id'] == logo_id:
                logo['active'] = True
                active_logo_url = logo['url']
                found = True
                print(f"[OK] Activated logo: {logo['name']}")
                break

        if not found:
            return jsonify({'success': False, 'error': 'Logo not found'}), 404

        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        return jsonify({'success': True, 'logoUrl': active_logo_url})

    except Exception as e:
        print(f"Error setting active logo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete-logo', methods=['POST'])
def delete_logo():
    """Delete a logo from library and file system"""
    try:
        data = request.get_json()
        logo_id = data.get('id')

        if not logo_id:
            return jsonify({'success': False, 'error': 'No logo ID provided'}), 400

        library_file = Path("logo_library.json")

        if not library_file.exists():
            return jsonify({'success': False, 'error': 'Logo library not found'}), 404

        library = json.loads(library_file.read_text(encoding="utf-8"))

        # Find and remove logo
        logo_to_delete = None
        for logo in library.get('logos', []):
            if logo['id'] == logo_id:
                logo_to_delete = logo
                break

        if not logo_to_delete:
            return jsonify({'success': False, 'error': 'Logo not found'}), 404

        # Delete file if it exists
        if logo_to_delete.get('filename'):
            file_path = Path("logos") / logo_to_delete['filename']
            if file_path.exists():
                file_path.unlink()
                print(f"[OK] Deleted logo file: {file_path}")

        # Remove from library
        library['logos'] = [l for l in library.get('logos', []) if l['id'] != logo_id]
        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        print(f"[OK] Deleted logo from library: {logo_to_delete['name']}")

        return jsonify({'success': True})

    except Exception as e:
        print(f"Error deleting logo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/generate-ai-thumbnail', methods=['POST'])
def generate_ai_thumbnail():
    """Generate 3 thumbnail variations using AI (DALL-E) with custom prompt"""
    try:
        data = request.get_json()
        video_title = data.get('title', '')
        ai_prompt = data.get('prompt', '')

        if not video_title:
            return jsonify({'success': False, 'error': 'No video title provided'}), 400

        if not ai_prompt:
            return jsonify({'success': False, 'error': 'No AI prompt provided'}), 400

        # Replace {{title}} placeholder in prompt
        base_prompt = ai_prompt.replace('{{title}}', video_title)

        print(f"[AI THUMBNAIL] Generating 3 thumbnails for: {video_title}")
        print(f"[AI THUMBNAIL] Base prompt: {base_prompt[:200]}...")

        from openai import OpenAI
        import requests

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Create thumbnails directory
        thumbnails_dir = Path("thumbnails")
        thumbnails_dir.mkdir(exist_ok=True)

        # Generate 3 variations with slightly different style prompts
        # IMPORTANT: Request NO TEXT in the image - text will be added via PIL
        variations = [
            {"suffix": " Style: Bold and dramatic with high contrast. NO TEXT OR WORDS in the image.", "label": "Bold"},
            {"suffix": " Style: Clean and minimal with modern aesthetics. NO TEXT OR WORDS in the image.", "label": "Minimal"},
            {"suffix": " Style: Vibrant and energetic with gradient effects. NO TEXT OR WORDS in the image.", "label": "Vibrant"}
        ]

        thumbnails = []

        for i, variation in enumerate(variations, 1):
            print(f"[AI THUMBNAIL] Generating variation {i}/3: {variation['label']}")

            # Add variation to prompt
            final_prompt = base_prompt + variation['suffix']

            # Generate image with DALL-E
            response = client.images.generate(
                model="dall-e-3",
                prompt=final_prompt,
                size="1792x1024",  # Closest to 16:9
                quality="standard",
                n=1,
            )

            image_url = response.data[0].url
            print(f"[AI THUMBNAIL] Variation {i} image URL: {image_url}")

            # Download the image
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()

            # Generate unique filename
            timestamp = int(time.time() * 1000)
            unique_filename = f"thumbnail_{timestamp}_{i}.png"
            save_path = thumbnails_dir / unique_filename

            # Save file
            save_path.write_bytes(img_response.content)
            print(f"[AI THUMBNAIL] Variation {i} saved to: {save_path}")

            # Add text overlay with PIL
            print(f"[AI THUMBNAIL] Adding text overlay: {video_title}")
            add_thumbnail_text(str(save_path), video_title)

            # Create thumbnail entry (not added to library yet)
            local_url = f"http://localhost:5000/thumbnails/{unique_filename}"
            thumbnail_entry = {
                'id': str(timestamp + i),
                'name': f"{video_title} - Variation {i}",
                'url': local_url,
                'filename': unique_filename,
                'variation': variation['label'],
                'active': False
            }

            thumbnails.append(thumbnail_entry)

            # Small delay to avoid rate limits
            if i < 3:
                import time as time_module
                time_module.sleep(2)

        print(f"[AI THUMBNAIL] Generated {len(thumbnails)} variations")

        return jsonify({'success': True, 'thumbnails': thumbnails})

    except Exception as e:
        print(f"[AI THUMBNAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/generate-thumbnail-with-canva', methods=['POST'])
def generate_thumbnail_with_canva():
    """Generate thumbnail using DALL-E for background + Canva for text overlay"""
    try:
        data = request.get_json()
        video_title = data.get('title', '')
        ai_prompt = data.get('prompt', '')
        variation_type = data.get('variation', 'Bold')  # Bold, Minimal, or Vibrant

        if not video_title:
            return jsonify({'success': False, 'error': 'No video title provided'}), 400

        if not ai_prompt:
            return jsonify({'success': False, 'error': 'No AI prompt provided'}), 400

        # Step 1: Generate background image with DALL-E (NO TEXT)
        print(f"[CANVA THUMBNAIL] Step 1: Generating background for: {video_title}")

        base_prompt = ai_prompt.replace('{{title}}', video_title)
        # Force no text in the DALL-E image
        background_prompt = base_prompt + f" IMPORTANT: This is a BACKGROUND IMAGE ONLY. NO TEXT, NO WORDS, NO LETTERS anywhere in the image. Pure visual background suitable for adding text overlay later."

        from openai import OpenAI
        import requests

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Generate background with DALL-E
        response = client.images.generate(
            model="dall-e-3",
            prompt=background_prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )

        background_url = response.data[0].url
        print(f"[CANVA THUMBNAIL] Background generated: {background_url}")

        # Download background image
        img_response = requests.get(background_url, timeout=30)
        img_response.raise_for_status()

        # Save background temporarily
        thumbnails_dir = Path("thumbnails")
        thumbnails_dir.mkdir(exist_ok=True)

        background_filename = f"bg_{int(time.time())}.png"
        background_path = thumbnails_dir / background_filename
        background_path.write_bytes(img_response.content)

        # Step 2: Use Canva API to create thumbnail with text
        print(f"[CANVA THUMBNAIL] Step 2: Creating Canva design with text overlay")

        canva_api_key = os.getenv("CANVA_API_KEY")

        if not canva_api_key:
            # If no Canva API, just return the background with instructions
            print(f"[CANVA THUMBNAIL] No CANVA_API_KEY found - returning background only")
            print(f"[CANVA THUMBNAIL] To enable text overlay, add CANVA_API_KEY to .env")

            local_url = f"http://localhost:5000/thumbnails/{background_filename}"

            return jsonify({
                'success': True,
                'background_only': True,
                'url': local_url,
                'message': 'Background generated. Add CANVA_API_KEY to .env for text overlay automation.',
                'instructions': {
                    'step1': 'Go to https://www.canva.com/developers/',
                    'step2': 'Create an app and get your API key',
                    'step3': 'Add CANVA_API_KEY=your_key to .env file',
                    'step4': 'Restart the server'
                }
            })

        # TODO: Implement Canva API integration
        # This requires:
        # 1. Upload background image to Canva
        # 2. Create design from template
        # 3. Replace background
        # 4. Update text layers with video_title
        # 5. Export final thumbnail

        # For now, return background with manual Canva instructions
        local_url = f"http://localhost:5000/thumbnails/{background_filename}"

        return jsonify({
            'success': True,
            'background_url': local_url,
            'canva_template_url': 'https://www.canva.com/design/create?template=youtube-thumbnail',
            'instructions': {
                'step1': f'Download background: {local_url}',
                'step2': 'Open Canva template',
                'step3': 'Replace background with downloaded image',
                'step4': f'Add text: "{video_title}"',
                'step5': 'Export as PNG (1280x720)'
            }
        })

    except Exception as e:
        print(f"[CANVA THUMBNAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save-selected-thumbnail', methods=['POST'])
def save_selected_thumbnail():
    """Save user-selected thumbnail to library"""
    try:
        thumbnail = request.get_json()

        if not thumbnail or not thumbnail.get('url'):
            return jsonify({'success': False, 'error': 'No thumbnail data provided'}), 400

        # Load library
        library_file = Path("thumbnail_library.json")
        if library_file.exists():
            library = json.loads(library_file.read_text(encoding="utf-8"))
        else:
            library = {'thumbnails': []}

        # Add uploadedAt timestamp
        thumbnail['uploadedAt'] = time.strftime('%Y-%m-%d %H:%M:%S')

        # Add to library
        library['thumbnails'].append(thumbnail)
        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        print(f"[THUMBNAIL] Saved to library: {thumbnail['name']}")

        return jsonify({'success': True, 'thumbnail': thumbnail})

    except Exception as e:
        print(f"[THUMBNAIL] Error saving: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload-thumbnail', methods=['POST'])
def upload_thumbnail():
    """Upload thumbnail file locally and save to library"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Create thumbnails directory
        thumbnails_dir = Path("thumbnails")
        thumbnails_dir.mkdir(exist_ok=True)

        # Generate unique filename
        ext = Path(file.filename).suffix or '.png'
        unique_filename = f"thumbnail_{int(time.time())}{ext}"
        save_path = thumbnails_dir / unique_filename

        # Save file
        file.save(save_path)
        print(f"[OK] Thumbnail saved locally: {save_path}")

        # Return full URL
        local_url = f"http://localhost:5000/thumbnails/{unique_filename}"

        # Load library
        library_file = Path("thumbnail_library.json")
        if library_file.exists():
            library = json.loads(library_file.read_text(encoding="utf-8"))
        else:
            library = {'thumbnails': []}

        # Get name from request or use filename
        name = request.form.get('name', file.filename)

        # Add to library
        thumbnail_entry = {
            'id': str(int(time.time() * 1000)),
            'name': name,
            'url': local_url,
            'filename': unique_filename,
            'active': False,
            'uploadedAt': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        library['thumbnails'].append(thumbnail_entry)
        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        print(f"[OK] Thumbnail added to library: {name}")

        return jsonify({'success': True, 'url': local_url, 'thumbnail': thumbnail_entry})

    except Exception as e:
        print(f"Error uploading thumbnail: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get-thumbnail-library', methods=['GET'])
def get_thumbnail_library():
    """Get all uploaded thumbnails"""
    try:
        library_file = Path("thumbnail_library.json")

        if library_file.exists():
            library = json.loads(library_file.read_text(encoding="utf-8"))
            return jsonify({'success': True, 'thumbnails': library.get('thumbnails', [])})
        else:
            return jsonify({'success': True, 'thumbnails': []})

    except Exception as e:
        print(f"Error loading thumbnail library: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/set-active-thumbnail', methods=['POST'])
def set_active_thumbnail():
    """Set a thumbnail as active (deactivates all others)"""
    try:
        data = request.get_json()
        thumbnail_id = data.get('id')

        if not thumbnail_id:
            return jsonify({'success': False, 'error': 'No thumbnail ID provided'}), 400

        library_file = Path("thumbnail_library.json")

        if not library_file.exists():
            return jsonify({'success': False, 'error': 'Thumbnail library not found'}), 404

        library = json.loads(library_file.read_text(encoding="utf-8"))

        # Deactivate all thumbnails
        for thumbnail in library.get('thumbnails', []):
            thumbnail['active'] = False

        # Activate the selected thumbnail
        found = False
        for thumbnail in library.get('thumbnails', []):
            if thumbnail['id'] == thumbnail_id:
                thumbnail['active'] = True
                found = True
                print(f"[OK] Activated thumbnail: {thumbnail['name']}")
                break

        if not found:
            return jsonify({'success': False, 'error': 'Thumbnail not found'}), 404

        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        return jsonify({'success': True})

    except Exception as e:
        print(f"Error setting active thumbnail: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete-thumbnail', methods=['POST'])
def delete_thumbnail():
    """Delete a thumbnail from library and file system"""
    try:
        data = request.get_json()
        thumbnail_id = data.get('id')

        if not thumbnail_id:
            return jsonify({'success': False, 'error': 'No thumbnail ID provided'}), 400

        library_file = Path("thumbnail_library.json")

        if not library_file.exists():
            return jsonify({'success': False, 'error': 'Thumbnail library not found'}), 404

        library = json.loads(library_file.read_text(encoding="utf-8"))

        # Find and remove thumbnail
        thumbnail_to_delete = None
        for thumbnail in library.get('thumbnails', []):
            if thumbnail['id'] == thumbnail_id:
                thumbnail_to_delete = thumbnail
                break

        if not thumbnail_to_delete:
            return jsonify({'success': False, 'error': 'Thumbnail not found'}), 404

        # Delete file if it exists
        if thumbnail_to_delete.get('filename'):
            file_path = Path("thumbnails") / thumbnail_to_delete['filename']
            if file_path.exists():
                file_path.unlink()
                print(f"[OK] Deleted thumbnail file: {file_path}")

        # Remove from library
        library['thumbnails'] = [t for t in library.get('thumbnails', []) if t['id'] != thumbnail_id]
        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        print(f"[OK] Deleted thumbnail from library: {thumbnail_to_delete['name']}")

        return jsonify({'success': True})

    except Exception as e:
        print(f"Error deleting thumbnail: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/get-avatar-library', methods=['GET'])
def get_avatar_library():
    """Get all avatars from library"""
    try:
        # Avatar library is in parent directory (MSS/avatar_library.json)
        library_file = Path(__file__).parent.parent / "avatar_library.json"

        if library_file.exists():
            library = json.loads(library_file.read_text(encoding="utf-8"))
        else:
            library = {"avatars": []}

        return jsonify({'success': True, 'avatars': library.get('avatars', [])})

    except Exception as e:
        print(f"Error loading avatar library: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/save-avatar', methods=['POST'])
def save_avatar():
    """Save a new or updated avatar"""
    try:
        data = request.get_json()
        avatar_id = data.get('id')
        name = data.get('name')
        avatar_type = data.get('type')  # 'image' or 'video'
        image_url = data.get('image_url', '')
        video_url = data.get('video_url', '')
        position = data.get('position', 'bottom-right')
        scale = data.get('scale', 25)
        opacity = data.get('opacity', 100)
        voice = data.get('voice', 'en-US-Neural2-F')

        if not name or not avatar_type:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Avatar library is in parent directory (MSS/avatar_library.json)
        library_file = Path(__file__).parent.parent / "avatar_library.json"
        library = json.loads(library_file.read_text(encoding="utf-8")) if library_file.exists() else {"avatars": []}

        # Generate ID if new
        if not avatar_id:
            import time
            avatar_id = f"avatar_{int(time.time())}"

        new_avatar = {
            "id": avatar_id,
            "name": name,
            "type": avatar_type,
            "image_url": image_url,
            "video_url": video_url,
            "position": position,
            "scale": scale,
            "opacity": opacity,
            "voice": voice,
            "active": False
        }

        # Add or update
        existing_idx = next((i for i, x in enumerate(library['avatars']) if x['id'] == avatar_id), None)

        if existing_idx is not None:
            # Keep active status when updating
            new_avatar['active'] = library['avatars'][existing_idx]['active']
            library['avatars'][existing_idx] = new_avatar
        else:
            library['avatars'].append(new_avatar)

        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        return jsonify({'success': True, 'message': 'Avatar saved successfully'})

    except Exception as e:
        print(f"Error saving avatar: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/set-active-avatar', methods=['POST'])
def set_active_avatar():
    """Set which avatar is active"""
    try:
        data = request.get_json()
        avatar_id = data.get('id')

        # Avatar library is in parent directory (MSS/avatar_library.json)
        library_file = Path(__file__).parent.parent / "avatar_library.json"
        library = json.loads(library_file.read_text(encoding="utf-8"))

        # Deactivate all, then activate the selected one
        for avatar in library['avatars']:
            avatar['active'] = (avatar['id'] == avatar_id)

        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        return jsonify({'success': True})

    except Exception as e:
        print(f"Error setting active avatar: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/delete-avatar', methods=['POST'])
def delete_avatar():
    """Delete an avatar"""
    try:
        data = request.get_json()
        avatar_id = data.get('id')

        # Avatar library is in parent directory (MSS/avatar_library.json)
        library_file = Path(__file__).parent.parent / "avatar_library.json"
        library = json.loads(library_file.read_text(encoding="utf-8"))

        library['avatars'] = [x for x in library['avatars'] if x['id'] != avatar_id]

        library_file.write_text(json.dumps(library, indent=2), encoding="utf-8")

        return jsonify({'success': True})

    except Exception as e:
        print(f"Error deleting intro/outro: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/regenerate-dalle-thumbnail', methods=['POST'])
def regenerate_dalle_thumbnail():
    """Regenerate just the DALL-E thumbnail"""
    try:
        data = request.get_json()
        title = data.get('title')
        description = data.get('description')

        if not title:
            return jsonify({'success': False, 'error': 'No title provided'}), 400

        print(f"\n[REGEN] Regenerating DALL-E thumbnail for: {title}")

        outdir = Path("out")
        ensure_dir(outdir)

        # Generate new DALL-E thumbnail
        thumb_path = generate_dalle_thumbnail(title, outdir)

        return jsonify({
            'success': True,
            'thumbnail': thumb_path.name,
            'message': 'DALL-E thumbnail regenerated successfully'
        })

    except Exception as e:
        print(f"Error regenerating DALL-E thumbnail: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/archive-video', methods=['POST'])
def archive_video():
    """Archive video and all related files to out/{date}_{topic_name} folder"""
    try:
        data = request.get_json()
        topic_name = data.get('topic_name', 'video')
        thumbnail = data.get('thumbnail')

        if not thumbnail:
            return jsonify({'success': False, 'error': 'No thumbnail selected'}), 400

        # Get current script data
        outdir = Path("out")
        script_file = outdir / "script.json"

        if not script_file.exists():
            return jsonify({'success': False, 'error': 'No script found'}), 404

        script_data = json.loads(script_file.read_text(encoding="utf-8"))

        # Create archive folder name: YYYY-MM-DD_{topic_name}
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Sanitize topic name for folder
        import re
        safe_topic = re.sub(r'[^\w\s-]', '', topic_name).strip()
        safe_topic = re.sub(r'[-\s]+', '_', safe_topic)[:50]  # Limit length

        archive_folder = outdir / f"{date_str}_{safe_topic}"
        archive_folder.mkdir(exist_ok=True)

        print(f"[ARCHIVE] Archiving video to: {archive_folder}")

        # Copy files to archive
        import shutil
        archived_files = []

        # Copy video files
        for f in outdir.glob("*.mp4"):
            dest = archive_folder / f.name
            shutil.copy2(f, dest)
            archived_files.append(f.name)
            print(f"  [OK] Copied: {f.name}")

        # Copy selected thumbnail
        thumb_src = outdir / thumbnail
        if thumb_src.exists():
            thumb_dest = archive_folder / "thumbnail_selected.jpg"
            shutil.copy2(thumb_src, thumb_dest)
            archived_files.append("thumbnail_selected.jpg")
            print(f"  [OK] Copied selected thumbnail: {thumbnail}")

        # Copy all thumbnails for reference
        for f in outdir.glob("thumb_*.jpg"):
            dest = archive_folder / f.name
            shutil.copy2(f, dest)
            archived_files.append(f.name)

        # Copy script.json
        dest_script = archive_folder / "script.json"
        shutil.copy2(script_file, dest_script)
        archived_files.append("script.json")

        # Copy audio files if they exist
        for f in outdir.glob("*.mp3"):
            dest = archive_folder / f.name
            shutil.copy2(f, dest)
            archived_files.append(f.name)

        # Create metadata file with publishing info
        metadata = {
            "archived_date": datetime.now().isoformat(),
            "topic_name": topic_name,
            "selected_thumbnail": thumbnail,
            "script": script_data,
            "files": archived_files
        }

        metadata_file = archive_folder / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        print(f"[OK] Archive complete: {archive_folder.name}")

        return jsonify({
            'success': True,
            'archive_folder': archive_folder.name,
            'archived_files': archived_files,
            'message': f'Video archived successfully to {archive_folder.name}'
        })

    except Exception as e:
        print(f"Error archiving video: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/upload-all-to-drive', methods=['POST'])
def upload_all_to_drive():
    """Upload all video files and thumbnails to Google Drive (async)"""
    try:
        data = request.get_json()
        files_data = data.get('files', {})

        shorts_file = files_data.get('shorts')
        wide_file = files_data.get('wide')
        thumbnails = files_data.get('thumbnails', [])
        selected_thumbnail = files_data.get('selected_thumbnail')

        # Start upload in background thread
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)

        def upload_all_files():
            """Background upload function"""
            try:
                print(f"[UPLOAD] Starting Google Drive upload in background...")

                outdir = Path("out")
                uploaded_files = []
                uploaded_count = 0

                # Upload shorts video
                if shorts_file:
                    shorts_path = outdir / shorts_file
                    if shorts_path.exists():
                        print(f"  Uploading: {shorts_file}")
                        result = drive_upload_public(shorts_path, "MSS_Videos")
                        uploaded_files.append({'name': shorts_file, 'url': result['download_url']})
                        uploaded_count += 1

                # Upload wide video
                if wide_file:
                    wide_path = outdir / wide_file
                    if wide_path.exists():
                        print(f"  Uploading: {wide_file}")
                        result = drive_upload_public(wide_path, "MSS_Videos")
                        uploaded_files.append({'name': wide_file, 'url': result['download_url']})
                        uploaded_count += 1

                # Upload thumbnails
                for thumb in thumbnails:
                    if thumb:
                        thumb_path = outdir / thumb
                        if thumb_path.exists():
                            print(f"  Uploading: {thumb}")
                            result = drive_upload_public(thumb_path, "MSS_Thumbnails")
                            uploaded_files.append({'name': thumb, 'url': result['download_url']})
                            uploaded_count += 1

                # Mark selected thumbnail
                if selected_thumbnail and selected_thumbnail not in thumbnails:
                    selected_path = outdir / selected_thumbnail
                    if selected_path.exists():
                        print(f"  Uploading selected thumbnail: {selected_thumbnail}")
                        result = drive_upload_public(selected_path, "MSS_Thumbnails")
                        uploaded_files.append({'name': f"{selected_thumbnail} (SELECTED)", 'url': result['download_url']})
                        uploaded_count += 1

                print(f"[OK] Uploaded {uploaded_count} files to Google Drive")
                print('\a')  # Ring bell when done

            except Exception as e:
                print(f"[ERROR] Background upload error: {e}")
                import traceback
                traceback.print_exc()

        # Start background upload
        executor.submit(upload_all_files)

        # Return immediately
        return jsonify({
            'success': True,
            'message': 'Upload started in background. Check console for progress.',
            'background': True
        })

    except Exception as e:
        print(f"Error starting upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/public_audio/<path:filename>', methods=['GET'])
def serve_public_audio(filename):
    """Serve audio files for Shotstack (publicly accessible)"""
    try:
        audio_dir = Path(__file__).parent.parent / "public_audio"
        return send_from_directory(audio_dir, filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@app.route('/test-shotstack', methods=['GET'])
def test_shotstack():
    """Test Shotstack API connection"""
    try:
        # Create a minimal test payload
        test_payload = {
            "timeline": {
                "soundtrack": {
                    "src": "https://shotstack-assets.s3-ap-southeast-2.amazonaws.com/music/disco.mp3"
                },
                "tracks": [
                    {
                        "clips": [
                            {
                                "asset": {
                                    "type": "video",
                                    "src": "https://shotstack-assets.s3-ap-southeast-2.amazonaws.com/footage/beach-overhead.mp4"
                                },
                                "start": 0,
                                "length": 5
                            }
                        ]
                    }
                ]
            },
            "output": {
                "format": "mp4",
                "resolution": "sd"
            }
        }

        result = shotstack_render(test_payload)

        return jsonify({
            'success': True,
            'message': 'Shotstack API is working',
            'response': result
        })

    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


def _read_version() -> str:
    try:
        root = Path(__file__).parent.parent
        ver_path = root / 'version.json'
        if ver_path.exists():
            data = json.loads(ver_path.read_text(encoding='utf-8'))
            # prefer unified app version if present
            for key in ('app', 'website', 'version'):
                v = (data.get(key) or '').strip()
                if v:
                    return v
        # fallback to env or default
        return os.getenv('MSS_VERSION', '2.8.0')
    except Exception:
        return os.getenv('MSS_VERSION', '2.8.0')


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'MSS API Server',
        'version': _read_version()
    })


def openai_draft_from_topic_custom(topic, header_text='', footer_text='', full_prompt=''):
    """Enhanced version with custom header/footer or full prompt override"""
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    system = "You are an expert YouTube scriptwriter. Create engaging 90-150 second scripts with strong hooks. Return JSON only."

    # Use full_prompt if provided (edited from UI), otherwise build from parts
    if full_prompt:
        print("[PROMPT] Using edited full prompt from UI")
        user_prompt = full_prompt
    else:
        # Build user prompt with custom header/footer
        base_user = f"""Create a concise script. Use the SEO metadata but do not fluff.
Return JSON with keys: narration (90-150s), overlays (6-10 lines), yt_title, yt_description, yt_tags.

Topic: {topic.get('title')}
Angle: {topic.get('angle')}
Keywords: {', '.join(topic.get('keywords', []))}
Outline: {topic.get('outline')}
Preferred Title: {topic.get('yt_title')}"""

        user_prompt = ""
        if header_text:
            user_prompt += header_text + "\n\n"
        user_prompt += base_user
        if footer_text:
            user_prompt += "\n\n" + footer_text

    completion = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_SCRIPT", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
        response_format={"type": "json_object"},
    )

    data = json.loads(completion.choices[0].message.content)

    # Map to expected format
    return {
        "narration": data.get("narration", ""),
        "overlays": data.get("overlays", []),
        "title": data.get("yt_title", topic.get("yt_title", topic.get("title"))),
        "description": data.get("yt_description", ""),
        "keywords": data.get("yt_tags", []),
    }


def generate_dalle_thumbnail(title, out_dir):
    """Generate thumbnail using DALL-E in Bold Contrast News Cut style"""
    from openai import OpenAI
    import requests

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Craft prompt for Bold Contrast News Cut style with YELLOW text
    prompt = f"""Create a bold, high-contrast news-style thumbnail for YouTube:

Title text: "{title}"

Style requirements:
- Bold, dramatic lighting with high contrast
- News broadcast aesthetic with dark background
- Strong shadows and highlights
- Dark blue or black background for maximum contrast
- Clean, modern look
- Text is EXTREMELY LARGE (fills 70% of the image), BOLD, and BRIGHT YELLOW (#FFD700 gold)
- The yellow text must be MASSIVE and the main focus
- Cinematic letterbox bars (top and bottom black bars)
- Professional news studio or dramatic abstract background
- NO people's faces
- Focus on abstract shapes, dramatic lighting, and the HUGE YELLOW title text
- 16:9 aspect ratio optimized for YouTube
- Text color: BRIGHT YELLOW or GOLD - no other color for text

CRITICAL: The text "{title}" should be the dominant visual element taking up most of the image, in a bold sans-serif font, BRIGHT YELLOW color, with dramatic lighting effects making it glow."""

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",  # Closest to 16:9
            quality="standard",
            n=1,
        )

        image_url = response.data[0].url

        # Download the image
        img_response = requests.get(image_url, timeout=30)
        img_response.raise_for_status()

        # Save to file
        thumb_path = out_dir / "thumb_ai_dalle.jpg"
        thumb_path.write_bytes(img_response.content)

        print(f"[OK] AI thumbnail generated: {thumb_path}")
        return thumb_path

    except Exception as e:
        print(f"DALL-E thumbnail generation failed: {e}")
        raise


@app.route('/generate-script', methods=['POST'])
def generate_script():
    """
    Generate a video script using OpenAI/Claude API
    """
    try:
        data = request.get_json() or {}
        prompt = data.get('prompt', '')
        title = data.get('title', '')
        hook = data.get('hook', '')
        description = data.get('description', '')
        length = data.get('length', 'medium')
        style = data.get('style', 'informative')

        if not prompt:
            return jsonify({'success': False, 'error': 'No prompt provided'}), 400

        # Initialize OpenAI client
        from openai import OpenAI
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return jsonify({'success': False, 'error': 'OPENAI_API_KEY not configured'}), 500

        client = OpenAI(api_key=api_key)

        print(f"[Script Gen] Generating script for: {title}")
        print(f"[Script Gen] Length: {length}, Style: {style}")

        # Generate script using GPT-4
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",  # or gpt-3.5-turbo for faster/cheaper
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional YouTube script writer with expertise in creating engaging, viewer-retaining content."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )

        script = response.choices[0].message.content

        print(f"[Script Gen] Successfully generated {len(script.split())} word script")

        return jsonify({
            'success': True,
            'script': script,
            'metadata': {
                'title': title,
                'hook': hook,
                'length': length,
                'style': style,
                'word_count': len(script.split())
            }
        })

    except Exception as e:
        print(f"[Script Gen] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("MSS API Server Starting...")
    print("=" * 60)
    print("\nServer will run at: http://localhost:5000")
    print("Open web UI at: http://localhost:8003")
    print("\nTo start web UI in another terminal:")
    print("   cd web/topic-picker-standalone")
    print("   python -m http.server 8003")
    print("\n" + "=" * 60 + "\n")

    # Disable reloader so it runs cleanly under background jobs or supervisors
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
