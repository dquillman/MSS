import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

import requests
import random
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from mutagen.mp3 import MP3
from tenacity import retry, stop_after_attempt, wait_exponential

# Import enhanced utilities
from scripts.video_utils import (
    retry_api_call,
    get_stock_footage_for_keywords,
    enhance_narration_with_ssml,
    generate_thumbnail_variants,
    generate_chapter_markers,
    get_enhanced_script_prompt,
    run_in_parallel,
)
from scripts.ffmpeg_render import render_video_with_ffmpeg


# ---------- Helpers ----------

def read_env():
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def fetch_url_text(url: str) -> str:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    # Remove scripts/styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


@retry_api_call()
def openai_generate(script_prompt: str, brand: str = "Many Sources Say") -> Dict[str, Any]:
    """Return JSON with narration, overlays, title, description, keywords, visual_cues."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    client = OpenAI(api_key=api_key)
    system = "You are an expert YouTube scriptwriter. Create engaging 90-150 second scripts with strong hooks. Return JSON only."
    user = get_enhanced_script_prompt(script_prompt, brand)

    # Try JSON mode if available
    completion = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_SCRIPT", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.6,
        response_format={"type": "json_object"},
    )
    content = completion.choices[0].message.content
    data = json.loads(content)

    # Basic shape checks with defaults
    required_keys = ["narration", "overlays", "title", "description", "keywords"]
    for k in required_keys:
        if k not in data:
            raise RuntimeError(f"OpenAI response missing '{k}'")

    # Add optional fields with defaults
    if "visual_cues" not in data:
        data["visual_cues"] = data.get("keywords", [])[:5]
    if "hook" not in data:
        data["hook"] = data["narration"][:200]
    if "engagement_cta" not in data:
        data["engagement_cta"] = "Subscribe for more insights!"

    # Append engagement CTA to narration if not already included
    narration = data["narration"]
    cta = data.get("engagement_cta", "")
    if cta and cta not in narration:
        data["narration"] = f"{narration} {cta}"

    return data


def openai_generate_topics(brand: str = "Many Sources Say", seed: str = "", include_meta_content: bool = True) -> List[Dict[str, Any]]:
    """Return a list of 5 topic ideas with SEO metadata and viral optimization.
    Each item: {title, angle, keywords[], yt_title, yt_description, yt_tags[], outline, hook_options[]}
    """
    from openai import OpenAI
    from datetime import datetime, timezone
    from scripts.video_utils import get_enhanced_topic_prompt, get_youtube_trending_topics

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required")

    # Get current date
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Get trending topics if API key available
    trending_topics = None
    if os.getenv("YOUTUBE_API_KEY"):
        try:
            trending_data = get_youtube_trending_topics(region="US", max_results=5)
            trending_topics = [t.get("title", "") for t in trending_data[:5]]
        except Exception as e:
            print(f"Note: Could not fetch trending topics: {e}")

    client = OpenAI(api_key=api_key)
    system = (
        "You are a senior YouTube strategist and viral content expert."
        f" Today's date is {today}."
        " Generate 5 high-performing video topics optimized for maximum views and engagement."
        " Use proven viral patterns and SEO optimization. Return JSON only."
    )

    # Add seed topic constraint if provided (strong enforcement)
    seed_instruction = (
        f" CRITICAL: All five topics MUST be directly and explicitly about '{seed}'. "
        f"Reject any topic that is not obviously about '{seed}'."
    ) if seed else ""

    # Add a nonce to reduce repetition across calls
    nonce = f"{int(time.time())}-{random.randint(1000,9999)}"

    # Use enhanced topic prompt
    user = get_enhanced_topic_prompt(brand, trending_topics, include_meta_content)
    user += (
        f"\n\n{seed_instruction}"
        f"\nIMPORTANT: Today is {today}. Create topics relevant to 2025 and current events, NOT outdated topics from 2023 or earlier."
        f"\nNonce: {nonce}. Generate fresh, non-repetitive topics across runs."
    )

    temperature = float(os.getenv("OPENAI_SEO_TEMPERATURE", "0.85"))
    completion = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_SEO", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = completion.choices[0].message.content
    payload = json.loads(content)
    topics = payload.get("topics") or payload.get("items") or []
    if not isinstance(topics, list) or not topics:
        raise RuntimeError("OpenAI topics response missing 'topics' array")
    # normalize
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
            "visual_cues": t.get("visual_cues", []),
            "hook_options": t.get("hook_options", []),
        })
    return norm


def openai_draft_from_topic(topic: Dict[str, Any]) -> Dict[str, Any]:
    """Use the chosen topic to produce narration + overlays + metadata with viral patterns."""
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    system = "You are an expert YouTube scriptwriter who creates viral, engaging content. Return JSON only."
    user = (
        "Create a compelling 90-150 second script optimized for maximum views and engagement.\n\n"
        "CRITICAL REQUIREMENTS:\n"
        "1. HOOK (first 3-5 seconds): Use viral patterns:\n"
        "   - 'I analyzed [number] [things] and discovered [shocking finding]...'\n"
        "   - 'Most [people] don't know this about [topic]...'\n"
        "   - 'After [research], I found [surprise]...'\n"
        "   The hook must create curiosity gap.\n\n"
        "2. STORY ARC: Problem → Insight → Revelation → Takeaway\n"
        "3. ENGAGEMENT: Include moments that make viewers want to keep watching:\n"
        "   - 'But here's where it gets interesting...'\n"
        "   - 'Wait until you hear this part...'\n"
        "   - 'The real secret is...'\n\n"
        "4. CALL TO ACTION: End with SPECIFIC engagement request:\n"
        "   - 'Drop a comment telling me [specific question]'\n"
        "   - 'Like this video if you want more secrets about [topic]'\n"
        "   - 'Subscribe if you want to see [next video idea]'\n\n"
        "5. Use short punchy sentences (3-7 words) for impact, longer ones for context.\n\n"
        "Return JSON with keys:\n"
        "- narration: 90-150 second script with natural speech patterns\n"
        "- overlays: 6-10 short text overlays (3-7 words each)\n"
        "- yt_title: Optimized title (use provided title or enhance it)\n"
        "- yt_description: SEO-rich description (first 2 sentences with keywords)\n"
        "- yt_tags: Search-optimized tags\n"
        "- engagement_cta: Specific call-to-action text\n\n"
        f"Topic: {topic.get('title')}\nAngle: {topic.get('angle')}\nKeywords: {', '.join(topic.get('keywords', []))}\n"
        f"Outline: {topic.get('outline')}\nPreferred Title: {topic.get('yt_title')}\n"
        f"Hook Options: {topic.get('hook_options', [])}\n"
        "Use one of the hook options or create a new one following the viral patterns above."
    )
    completion = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_SCRIPT", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.6,
        response_format={"type": "json_object"},
    )
    data = json.loads(completion.choices[0].message.content)
    for k in ["narration", "overlays", "yt_title", "yt_description", "yt_tags"]:
        if k not in data:
            raise RuntimeError(f"Draft-from-topic missing '{k}'")
    # Append engagement CTA to narration if not already included
    narration = data["narration"]
    cta = data.get("engagement_cta", "Subscribe for more insights!")
    if cta and cta not in narration:
        narration = f"{narration} {cta}"

    # Map keys to the shape used later
    mapped = {
        "narration": narration,
        "overlays": data["overlays"],
        "title": data.get("yt_title", topic.get("yt_title", topic.get("title"))),
        "description": data.get("yt_description", ""),
        "keywords": data.get("yt_tags", []),
        "engagement_cta": cta,
    }
    return mapped

@retry_api_call()
def get_active_avatar_voice() -> str:
    """Get the voice setting from the active avatar, or default"""
    library_file = Path("avatar_library.json")

    if not library_file.exists():
        return os.getenv("TTS_VOICE_NAME", "en-US-Neural2-C")

    try:
        library = json.loads(library_file.read_text(encoding="utf-8"))
        active_avatar = next((x for x in library.get('avatars', []) if x.get('active')), None)

        if active_avatar and active_avatar.get('voice'):
            return active_avatar['voice']
    except Exception as e:
        print(f"Warning: Could not load avatar voice: {e}")

    return os.getenv("TTS_VOICE_NAME", "en-US-Neural2-C")


def google_tts_to_drive(text: str, filename_prefix: str = "audio") -> str:
    """Generate TTS and upload to Google Drive, return public URL"""
    import tempfile
    temp_audio = Path(tempfile.gettempdir()) / f"{filename_prefix}_{int(time.time())}.mp3"
    google_tts(text, temp_audio, use_ssml=False)
    result = drive_upload_public(temp_audio, "MSS_Audio")
    temp_audio.unlink(missing_ok=True)
    return result['download_url']


def google_tts(text: str, out_path: Path, use_ssml: bool = True, voice_override: Optional[str] = None) -> None:
    """Generate TTS with optional SSML enhancement and configurable voice.

    Automatically derives the language_code from the selected voice (e.g.,
    voice 'en-GB-Neural2-A' -> language_code 'en-GB') to avoid API errors such as:
      "Requested language code 'en-US' doesn't match the voice 'en-GB-...'".
    """
    try:
        from google.cloud import texttospeech
    except Exception as e:
        raise RuntimeError("google-cloud-texttospeech is required. pip install google-cloud-texttospeech") from e

    client = texttospeech.TextToSpeechClient()

    # Apply SSML if enabled
    if use_ssml and os.getenv("ENABLE_SSML", "true").lower() in {"true", "1", "yes"}:
        ssml_text = enhance_narration_with_ssml(text)
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)
    else:
        synthesis_input = texttospeech.SynthesisInput(text=text)

    # Use voice override if provided, otherwise get from active avatar, otherwise use env/default
    if voice_override:
        voice_name = voice_override
    else:
        voice_name = get_active_avatar_voice()

    # Infer language code from voice (e.g., 'en-GB-Neural2-A' -> 'en-GB')
    # Fallback to env TTS_LANGUAGE_CODE or 'en-US'.
    import re
    env_lang = os.getenv("TTS_LANGUAGE_CODE", "en-US")
    lang_from_voice = None
    if voice_name:
        m = re.match(r"^([a-zA-Z]{2}-[a-zA-Z]{2})", voice_name)
        if m:
            # Normalize case: language lower, region upper
            parts = m.group(1).split('-')
            lang_from_voice = f"{parts[0].lower()}-{parts[1].upper()}"
    language_code = lang_from_voice or env_lang

    speaking_rate = float(os.getenv("TTS_SPEAKING_RATE", "1.03"))

    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name or os.getenv("TTS_VOICE_NAME", "en-US-Neural2-C"),
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speaking_rate,
        pitch=0.0,
        effects_profile_id=["medium-bluetooth-speaker-class-device"],  # Optimized for mobile
    )
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )
    out_path.write_bytes(response.audio_content)


def get_google_service(scopes: List[str], token_file: str):
    try:
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import pickle
    except Exception as e:
        raise RuntimeError("Google API client libs missing. pip install google-api-python-client google-auth-oauthlib") from e

    creds = None
    token_path = Path(token_file)
    if token_path.exists():
        with token_path.open("rb") as f:
            creds = pickle.load(f)
    if not creds or not getattr(creds, 'valid', False):
        if creds and getattr(creds, 'expired', False) and getattr(creds, 'refresh_token', None):
            creds.refresh(Request())
        else:
            secrets_path = Path(__file__).parent.parent / "client_secrets.json"
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), scopes)
            creds = flow.run_local_server(port=0)
        with token_path.open("wb") as f:
            pickle.dump(creds, f)
    # The caller will build the service
    return creds


def drive_build_service(creds):
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=creds)


def drive_find_or_create_path(service, path: str) -> str:
    # path like "/autopilot/audio/"
    parts = [p for p in path.strip().split("/") if p]
    parent = 'root'
    for name in parts:
        q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent}' in parents and trashed=false"
        res = service.files().list(q=q, fields="files(id,name)").execute()
        files = res.get('files', [])
        if files:
            parent = files[0]['id']
        else:
            file_metadata = { 'name': name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [parent] }
            folder = service.files().create(body=file_metadata, fields='id').execute()
            parent = folder['id']
    return parent


def drive_upload_public(file_path: Path, folder_path: str = "MSS_Audio") -> Dict[str, str]:
    """
    Upload a file to Google Drive using OAuth (personal account).
    First run will open browser for authorization.
    Returns public download URL.
    """
    from googleapiclient.http import MediaFileUpload

    scopes = ['https://www.googleapis.com/auth/drive.file']
    creds = get_google_service(scopes, "token.drive.pickle")
    service = drive_build_service(creds)

    # Find or create folder
    query = f"name='{folder_path}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])

    if folders:
        folder_id = folders[0]['id']
    else:
        folder_metadata = {
            'name': folder_path,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder['id']

    # Upload file with auto-detected mimetype
    import mimetypes
    mimetype, _ = mimetypes.guess_type(str(file_path))
    if not mimetype:
        # Fallback based on extension
        ext = file_path.suffix.lower()
        if ext == '.mp3':
            mimetype = 'audio/mpeg'
        elif ext == '.mp4':
            mimetype = 'video/mp4'
        elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            mimetype = f'image/{ext[1:]}'
        else:
            mimetype = 'application/octet-stream'

    media = MediaFileUpload(str(file_path), mimetype=mimetype, resumable=False)
    file_metadata = { 'name': file_path.name, 'parents': [folder_id] }
    created = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    fid = created['id']

    # Make public
    service.permissions().create(fileId=fid, body={ 'type': 'anyone', 'role': 'reader' }).execute()

    # Use uc?export=download for direct file access (required by D-ID API)
    url = f"https://drive.google.com/uc?export=download&id={fid}"

    view_url = f"https://drive.google.com/file/d/{fid}/view"
    return { 'file_id': fid, 'download_url': url, 'view_url': view_url }


def upload_to_drive_and_share(file_path: Path, custom_name: Optional[str] = None, folder: str = "MSS_Avatars") -> str:
    """
    Upload any file to Google Drive and return public download URL.
    Wrapper around drive_upload_public for avatar uploads.
    """
    # Rename file if custom name provided
    if custom_name:
        temp_path = file_path.parent / custom_name
        import shutil
        shutil.copy(file_path, temp_path)
        file_path = temp_path

    result = drive_upload_public(file_path, folder_path=folder)

    # Clean up temp file if we renamed
    if custom_name and file_path.name == custom_name:
        file_path.unlink()

    return result['download_url']


def get_mp3_duration_seconds(file_path: Path) -> float:
    """Robust MP3 duration calculation with mutagen -> ffprobe fallback."""
    try:
        audio = MP3(file_path)
        return float(audio.info.length)
    except Exception as e:
        print(f"[WARN] Mutagen failed to read MP3 ({file_path}): {e}")
        # Fallback to ffprobe via imageio_ffmpeg
        try:
            import subprocess
            import json as _json
            import imageio_ffmpeg
            ffprobe = imageio_ffmpeg.get_ffmpeg_exe().replace("ffmpeg", "ffprobe")
            cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(file_path)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                info = _json.loads(res.stdout or "{}")
                dur = float(info.get("format", {}).get("duration", 0.0))
                if dur > 0:
                    return dur
        except Exception as ee:
            print(f"[WARN] ffprobe fallback failed: {ee}")
        # last resort fallback to keep pipeline running
        return 60.0


def create_intro_outro_clips(intro_duration: float = 3.0, outro_duration: float = 3.0, total_content_secs: float = 0) -> Dict[str, Any]:
    """Create intro and outro clip definitions from library, including optional TTS audio"""
    # Load from library
    library_file = Path("intro_outro_library.json")

    # Default HTML if library doesn't exist
    default_intro_html = """<div style='width:100%;height:100%;background:linear-gradient(135deg, #0B0F19 0%, #1a2332 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;'>
                <div style='font-family:Inter,Arial,sans-serif;font-size:96px;font-weight:900;color:#FFD700;text-shadow:0 6px 20px rgba(255,215,0,.5);margin-bottom:20px;'>MANY SOURCES SAY</div>
                <div style='font-family:Inter,Arial,sans-serif;font-size:32px;font-weight:400;color:#94a3b8;font-style:italic;'>Because one source is NEVER enough</div>
            </div>"""

    default_outro_html = """<div style='width:100%;height:100%;background:linear-gradient(135deg, #0B0F19 0%, #1a2332 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;'>
                <div style='font-family:Inter,Arial,sans-serif;font-size:72px;font-weight:900;color:#FFD700;text-shadow:0 6px 20px rgba(255,215,0,.5);margin-bottom:30px;'>THANKS FOR WATCHING!</div>
                <div style='font-family:Inter,Arial,sans-serif;font-size:48px;font-weight:700;color:#E8EBFF;margin-bottom:15px;'>MANY SOURCES SAY</div>
                <div style='font-family:Inter,Arial,sans-serif;font-size:28px;font-weight:400;color:#94a3b8;'>Subscribe for more insights</div>
            </div>"""

    intro_html = default_intro_html
    outro_html = default_outro_html
    intro_audio_text = ""
    outro_audio_text = ""

    if library_file.exists():
        try:
            library = json.loads(library_file.read_text(encoding="utf-8"))

            # Find active intro
            active_intro = next((x for x in library.get('intros', []) if x.get('active')), None)
            if active_intro:
                intro_html = active_intro['html']
                intro_duration = active_intro.get('duration', 3.0)
                intro_audio_text = active_intro.get('audio', '')

            # Find active outro
            active_outro = next((x for x in library.get('outros', []) if x.get('active')), None)
            if active_outro:
                outro_html = active_outro['html']
                outro_duration = active_outro.get('duration', 3.0)
                outro_audio_text = active_outro.get('audio', '')
        except Exception as e:
            print(f"Warning: Could not load intro/outro library: {e}")

    # Generate TTS audio for intro if text is provided
    intro_audio_url = None
    if intro_audio_text:
        try:
            print(f"Generating intro TTS audio: {intro_audio_text[:50]}...")
            intro_audio_url = google_tts_to_drive(intro_audio_text, filename_prefix="intro_audio")
            print(f"âœ“ Intro audio uploaded: {intro_audio_url}")
        except Exception as e:
            print(f"Warning: Failed to generate intro audio: {e}")

    # Generate TTS audio for outro if text is provided
    outro_audio_url = None
    if outro_audio_text:
        try:
            print(f"Generating outro TTS audio: {outro_audio_text[:50]}...")
            outro_audio_url = google_tts_to_drive(outro_audio_text, filename_prefix="outro_audio")
            print(f"âœ“ Outro audio uploaded: {outro_audio_url}")
        except Exception as e:
            print(f"Warning: Failed to generate outro audio: {e}")

    intro_clip = {
        "asset": {
            "type": "html",
            "html": intro_html
        },
        "start": 0,
        "length": intro_duration,
        "transition": {"out": "fade"}
    }

    outro_start = intro_duration + total_content_secs
    outro_clip = {
        "asset": {
            "type": "html",
            "html": outro_html
        },
        "start": outro_start,
        "length": outro_duration,
        "transition": {"in": "fade"}
    }

    return {
        "intro": intro_clip,
        "outro": outro_clip,
        "intro_duration": intro_duration,
        "outro_duration": outro_duration,
        "intro_audio_url": intro_audio_url,
        "outro_audio_url": outro_audio_url
    }


def create_avatar_clip(total_duration: float, start_time: float = 0, audio_url: Optional[str] = None, voice_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Load avatar from library and create clip definition
    If D-ID is enabled and audio_url is provided, generates talking avatar video
    Auto-selects avatar based on voice gender if voice_name provided
    """
    library_file = Path("avatar_library.json")

    if not library_file.exists():
        return None

    try:
        library = json.loads(library_file.read_text(encoding="utf-8"))

        # Auto-select avatar based on voice gender if voice provided
        if voice_name:
            # Determine voice gender from voice name patterns
            voice_gender = 'female'
            # Male voice indicators: J, B, Q, L, D, A in voice names
            # Examples: Neural2-J, Studio-Q, News-L, Neural2-D, Neural2-A
            male_indicators = ['J', 'B', 'Q', 'L', 'D', 'A']
            voice_upper = voice_name.upper()

            for indicator in male_indicators:
                if f'-{indicator}' in voice_upper or voice_upper.endswith(f'-{indicator}'):
                    voice_gender = 'male'
                    break

            print(f"[AVATAR] Auto-selecting avatar: Voice={voice_name}, Gender={voice_gender}")

            # Find matching avatar by gender
            active_avatar = next((x for x in library.get('avatars', []) if x.get('gender') == voice_gender), None)

            # Fallback to any active avatar
            if not active_avatar:
                active_avatar = next((x for x in library.get('avatars', []) if x.get('active')), None)
                print(f"[AVATAR] No {voice_gender} avatar found, using active avatar")
        else:
            # Use active avatar
            active_avatar = next((x for x in library.get('avatars', []) if x.get('active')), None)

        if not active_avatar:
            return None

        # Position mapping for Shotstack (camelCase required)
        position_map = {
            'bottom-right': 'bottomRight',
            'bottom-left': 'bottomLeft',
            'top-right': 'topRight',
            'top-left': 'topLeft',
            'center': 'center'
        }

        shotstack_position = position_map.get(active_avatar.get('position', 'bottom-right'), 'bottomRight')
        scale = active_avatar.get('scale', 25)
        opacity = active_avatar.get('opacity', 100) / 100.0

        if active_avatar['type'] == 'image':
            # Check if D-ID is enabled and we have audio URL
            did_enabled = os.getenv("DID_API_KEY") and os.getenv("DID_API_KEY") != "your_d_id_api_key_here"

            if did_enabled and audio_url:
                # Generate talking avatar with D-ID
                # Extract local avatar path from URL
                avatar_filename = active_avatar['image_url'].split('/')[-1]
                avatar_local_path = Path("avatars") / avatar_filename

                if not avatar_local_path.exists():
                    print(f"[!] Avatar file not found locally: {avatar_local_path}")
                    print(f"   Skipping D-ID talking avatar generation")
                else:
                    did_video_path = Path("out") / f"did_avatar_{int(time.time())}.mp4"
                    did_video = generate_did_talking_avatar(
                        str(avatar_local_path),
                        audio_url,  # This can be a URL - function will download it
                        did_video_path
                    )

                if did_video and avatar_local_path.exists():
                    # Upload D-ID video to Google Drive for public access
                    print(f"[UPLOAD] Uploading D-ID avatar to Google Drive...")
                    drive_result = drive_upload_public(did_video_path, "MSS_Avatars")

                    # Use the D-ID generated talking video
                    return {
                        "asset": {
                            "type": "video",
                            "src": drive_result['download_url'],
                            "volume": 0.0
                        },
                        "start": start_time,
                        "length": total_duration,
                        "fit": "none",
                        "scale": scale / 100.0,
                        "opacity": opacity,
                        "position": shotstack_position
                    }

            # Upload static avatar image to Google Drive for public access
            # Extract filename from URL
            avatar_filename = active_avatar['image_url'].split('/')[-1]
            avatar_local_path = Path("avatars") / avatar_filename

            if avatar_local_path.exists():
                print(f"[UPLOAD] Uploading avatar to Google Drive for Shotstack access...")
                drive_result = drive_upload_public(avatar_local_path, "MSS_Avatars")
                avatar_public_url = drive_result['download_url']
            else:
                # Fallback to original URL if local file doesn't exist
                avatar_public_url = active_avatar['image_url']

            # Use static image with public URL
            return {
                "asset": {
                    "type": "image",
                    "src": avatar_public_url
                },
                "start": start_time,
                "length": total_duration,
                "fit": "none",
                "scale": scale / 100.0,
                "opacity": opacity,
                "position": shotstack_position
            }
        elif active_avatar['type'] == 'video':
            # Video avatar - ensure it's publicly accessible
            video_url = active_avatar['video_url']

            # If it's a localhost URL, we need to upload to Drive
            if 'localhost' in video_url:
                # Extract filename and upload
                video_filename = video_url.split('/')[-1]
                video_local_path = Path("avatars") / video_filename

                if video_local_path.exists():
                    print(f"[UPLOAD] Uploading video avatar to Google Drive for Shotstack access...")
                    drive_result = drive_upload_public(video_local_path, "MSS_Avatars")
                    video_url = drive_result['download_url']

            return {
                "asset": {
                    "type": "video",
                    "src": video_url,
                    "volume": 0.0
                },
                "start": start_time,
                "length": total_duration,
                "fit": "none",
                "scale": scale / 100.0,
                "opacity": opacity,
                "position": shotstack_position
            }

    except Exception as e:
        print(f"Warning: Could not load avatar: {e}")
        return None


def generate_did_talking_avatar(avatar_image_path: str, audio_path: str, output_path: Path) -> Optional[str]:
    """
    Generate a talking avatar video using D-ID API

    Args:
        avatar_image_path: Path to the avatar image file (or URL if it ends with proper extension)
        audio_path: Path to the audio file (or URL if it ends with proper extension)
        output_path: Path where to save the generated video

    Returns:
        Path to the generated video file, or None if failed

    Note:
        Uses pad_audio=0.5 to add 0.5s padding to prevent avatar from stopping before audio ends.
        The fluent and stitch options ensure smooth, continuous animation throughout.
    """
    did_api_key = os.getenv("DID_API_KEY")

    if not did_api_key or did_api_key == "your_d_id_api_key_here":
        print("[!] D-ID API key not configured. Add DID_API_KEY to .env file")
        print("   Get your key at: https://studio.d-id.com")
        return None

    try:
        print(f"[DID] Generating D-ID talking avatar...")

        headers = {
            "Authorization": f"Basic {did_api_key}",
        }

        # Convert paths to local files if needed
        if avatar_image_path.startswith('http'):
            # Download image temporarily
            import tempfile
            resp = requests.get(avatar_image_path)
            resp.raise_for_status()
            temp_img = Path(tempfile.gettempdir()) / "did_temp_avatar.png"
            temp_img.write_bytes(resp.content)
            avatar_image_path = str(temp_img)

        if audio_path.startswith('http'):
            # Download audio temporarily
            import tempfile
            resp = requests.get(audio_path)
            resp.raise_for_status()
            temp_audio = Path(tempfile.gettempdir()) / "did_temp_audio.mp3"
            temp_audio.write_bytes(resp.content)
            audio_path = str(temp_audio)

        # Step 1: Upload image to D-ID images endpoint
        print(f"  [UPLOAD] Uploading avatar image to D-ID...")
        images_url = "https://api.d-id.com/images"

        with open(avatar_image_path, 'rb') as img_file:
            files = {'image': ('avatar.png', img_file, 'image/png')}
            image_response = requests.post(images_url, headers=headers, files=files)

        if image_response.status_code != 201:
            print(f"[X] D-ID image upload error: {image_response.status_code} - {image_response.text}")
            image_response.raise_for_status()

        image_data = image_response.json()
        image_url = image_data.get('url')
        print(f"  [OK] Image uploaded: {image_url}")

        # Step 2: Upload audio to D-ID audios endpoint
        print(f"  [UPLOAD] Uploading audio to D-ID...")
        audios_url = "https://api.d-id.com/audios"

        with open(audio_path, 'rb') as audio_file:
            files = {'audio': ('audio.mp3', audio_file, 'audio/mpeg')}
            audio_response = requests.post(audios_url, headers=headers, files=files)

        if audio_response.status_code != 201:
            print(f"[X] D-ID audio upload error: {audio_response.status_code} - {audio_response.text}")
            audio_response.raise_for_status()

        audio_data = audio_response.json()
        audio_url = audio_data.get('url')
        print(f"  [OK] Audio uploaded: {audio_url}")

        # Step 3: Create talk with uploaded image and audio URLs
        print(f"  [CREATE] Creating D-ID talk...")
        create_url = "https://api.d-id.com/talks"
        headers["Content-Type"] = "application/json"

        payload = {
            "source_url": image_url,
            "script": {
                "type": "audio",
                "audio_url": audio_url
            },
            "config": {
                "fluent": True,
                "pad_audio": 0.5,  # Add 0.5s padding to ensure animation extends through audio end
                "stitch": True,
                "driver_expressions": {
                    "expressions": [
                        {"start_frame": 0, "expression": "neutral", "intensity": 0.9}
                    ]
                }
            }
        }

        response = requests.post(create_url, json=payload, headers=headers)

        if response.status_code != 201:
            print(f"[X] D-ID talk creation error: {response.status_code} - {response.text}")

        response.raise_for_status()

        talk_data = response.json()
        talk_id = talk_data.get("id")

        if not talk_id:
            print(f"[X] D-ID API error: No talk ID returned")
            return None

        print(f"  [WAIT] D-ID processing (ID: {talk_id})...")

        # Step 2: Poll for completion
        get_url = f"https://api.d-id.com/talks/{talk_id}"
        max_attempts = 60  # 5 minutes max (5 second intervals)

        for attempt in range(max_attempts):
            time.sleep(5)

            status_response = requests.get(get_url, headers=headers)
            status_response.raise_for_status()
            status_data = status_response.json()

            status = status_data.get("status")

            if status == "done":
                video_url = status_data.get("result_url")
                if not video_url:
                    print(f"[X] D-ID completed but no video URL")
                    return None

                # Download the video
                print(f"  [DOWNLOAD] Downloading talking avatar video...")
                video_response = requests.get(video_url, stream=True)
                video_response.raise_for_status()

                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, 'wb') as f:
                    for chunk in video_response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"  [OK] D-ID avatar saved: {output_path}")
                return str(output_path)

            elif status == "error":
                error_msg = status_data.get("error", {}).get("description", "Unknown error")
                print(f"[X] D-ID error: {error_msg}")
                return None

            elif status in ["created", "started"]:
                print(f"  [WAIT] D-ID status: {status} (attempt {attempt + 1}/{max_attempts})")

            else:
                print(f"  [!] Unknown D-ID status: {status}")

        print(f"[X] D-ID timeout after {max_attempts * 5} seconds")
        return None

    except Exception as e:
        print(f"[X] D-ID API error: {e}")
        import traceback
        traceback.print_exc()
        return None


def build_shotstack_payload(audio_url: str, overlays: List[str], total_secs: float, title: str, stock_videos: Optional[List[str]] = None) -> Dict[str, Any]:
    """Build Shotstack payload with optional stock video B-roll and intro/outro"""
    # Create intro/outro
    intro_outro = create_intro_outro_clips(intro_duration=3.0, outro_duration=3.0, total_content_secs=total_secs)
    intro_duration = intro_outro["intro_duration"]
    outro_duration = intro_outro["outro_duration"]

    # Distribute overlays evenly across duration, text stays 20s each
    n = max(1, len(overlays))
    slot = total_secs / n  # Divide entire duration by number of overlays
    text_clips = []
    t = intro_duration  # Start right after intro (3s)
    text_duration = 20.0  # 20 seconds per overlay

    for i, line in enumerate(overlays):
        # Main text overlay - news headline style
        text_clips.append({
            "asset": {
                "type": "html",
                "html": "<div style='font-family:Inter,Arial,sans-serif;font-size:68px;font-weight:800;line-height:1.2;color:#FFFFFF;text-shadow:0 6px 20px rgba(0,0,0,0.9), 0 2px 4px rgba(0,0,0,0.8);display:flex;align-items:center;justify-content:center;padding:0 60px;text-align:center;width:100%;height:100%;word-wrap:break-word;overflow-wrap:break-word;background:linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.3) 100%);'>" + line[:150].replace("\"", "&quot;") + "</div>",
            },
            "start": round(t, 2),
            "length": round(text_duration, 2),
            "transition": {"in": "slideUp", "out": "slideDown"},
        })

        t += slot

    # Create ONE continuous news banner for the entire video (including intro/outro)
    total_with_intro_outro = intro_duration + total_secs + outro_duration
    news_banner_clips = []  # TEMPORARILY DISABLED TO DEBUG AVATAR

    # Create separate intro/outro track (keeps backgrounds separate from text overlays)
    intro_outro_clips = [
        intro_outro["intro"],
        intro_outro["outro"]
    ]

    # Background track - use stock videos if available, otherwise gradient
    # Extend duration to include intro and outro
    bg_clips = []
    dim_clips = []  # Separate track for dimming overlay

    if stock_videos and len(stock_videos) > 0:
        # Distribute stock videos across content duration (not intro/outro)
        video_duration = total_secs / len(stock_videos)
        t = intro_duration  # Start after intro
        for video_url in stock_videos:
            bg_clips.append({
                "asset": {
                    "type": "video",
                    "src": video_url,
                    "volume": 0.0,  # Mute stock video
                },
                "start": round(t, 2),
                "length": round(video_duration, 2),
                "fit": "cover",
                "scale": 1.0,
                "transition": {"in": "fade", "out": "fade"},
                "effect": "zoomIn",  # Add subtle motion
            })
            t += video_duration

        # Add dim overlay on separate track (so text is readable) - only over content, not intro/outro
        dim_clips.append({
            "asset": {
                "type": "html",
                "html": "<div style='width:100%;height:100%;background:rgba(0,0,0,0.4);'></div>"
            },
            "start": intro_duration,
            "length": round(total_secs, 2),
        })
    else:
        # Fallback to gradient background for content area
        bg_clips.append({
            "asset": {
                "type": "html",
                "html": "<div style='width:100%;height:100%;background: radial-gradient(80% 80% at 50% 50%, #182032 0%, #0B0F19 100%);'></div>"
            },
            "start": intro_duration,
            "length": round(total_secs, 2),
            "fit": "cover",
            "transition": {"in": "fade", "out": "fade"}
        })

    # Audio track - starts after intro
    audio_clips = [{
        "asset": {
            "type": "audio",
            "src": audio_url
        },
        "start": intro_duration + 3.0,  # Intro + 3 second delay
        "length": round(total_secs - 3.0, 2)
    }]

    # Add intro audio if available
    if intro_outro.get("intro_audio_url"):
        audio_clips.insert(0, {
            "asset": {
                "type": "audio",
                "src": intro_outro["intro_audio_url"]
            },
            "start": 0,
            "length": intro_duration
        })

    # Add outro audio if available
    if intro_outro.get("outro_audio_url"):
        outro_start = intro_duration + total_secs
        audio_clips.append({
            "asset": {
                "type": "audio",
                "src": intro_outro["outro_audio_url"]
            },
            "start": outro_start,
            "length": outro_duration
        })

    # Create avatar clip if available (for entire video duration including intro/outro)
    total_with_intro_outro = intro_duration + total_secs + outro_duration
    voice_name = get_active_avatar_voice()
    avatar_clip = create_avatar_clip(total_with_intro_outro, start_time=0, audio_url=audio_url, voice_name=voice_name)

    # DEBUG
    print(f"\n[VIDEO] VIDEO STRUCTURE (9:16):")
    print(f"   Intro: 0 to {intro_duration}s")
    print(f"   Content: {intro_duration} to {intro_duration + total_secs}s")
    print(f"   Outro: {intro_duration + total_secs} to {total_with_intro_outro}s")
    print(f"   BG clips: {len(bg_clips)} clips")
    if avatar_clip:
        print(f"   Avatar: {avatar_clip.get('start')}s for {avatar_clip.get('length')}s")
    print()

    # Build tracks: intro/outro backgrounds -> content background -> dim -> text -> news banner -> avatar -> audio
    # Avatar MUST be on the LAST visual track (highest number) to render on top
    tracks = [
        {"clips": intro_outro_clips},  # Track 0: intro/outro with backgrounds
        {"clips": bg_clips},           # Track 1: content background (videos or gradient)
    ]
    if dim_clips:
        tracks.append({"clips": dim_clips})  # Track 2: dim overlay (only if using stock videos)
    tracks.append({"clips": text_clips})     # Track 3 or 2: text overlays
    if news_banner_clips:
        tracks.append({"clips": news_banner_clips})  # Track 4 or 3: news banner lower-third
    if avatar_clip:
        tracks.append({"clips": [avatar_clip]})  # Track 5 or 4 or 3: avatar overlay (MUST BE LAST VISUAL!)
    tracks.append({"clips": audio_clips})    # Track 6 or 5 or 4 or 3: audio

    payload = {
        "timeline": {
            "background": "#000000",
            "tracks": tracks,
        },
        "output": {
            "format": "mp4",
            "resolution": "1080",
            "aspectRatio": "9:16",
            "fps": 30,
            "repeat": False
        }
    }
    return payload


def build_shotstack_payload_wide(audio_url: str, overlays: List[str], total_secs: float, title: str, stock_videos: Optional[List[str]] = None) -> Dict[str, Any]:
    """Build wide format Shotstack payload with optional stock video B-roll and intro/outro"""
    # Create intro/outro
    intro_outro = create_intro_outro_clips(intro_duration=3.0, outro_duration=3.0, total_content_secs=total_secs)
    intro_duration = intro_outro["intro_duration"]
    outro_duration = intro_outro["outro_duration"]

    text_clips = []
    n = max(1, len(overlays))
    slot = total_secs / n  # Divide entire duration by number of overlays
    t = intro_duration  # Start right after intro (3s)
    text_duration = 20.0  # 20 seconds per overlay

    for i, line in enumerate(overlays):
        # Main text overlay - news headline style (WIDE)
        text_clips.append({
            "asset": {
                "type": "html",
                "html": "<div style='font-family:Inter,Arial,sans-serif;font-size:84px;font-weight:800;line-height:1.2;color:#FFFFFF;text-shadow:0 6px 20px rgba(0,0,0,0.9), 0 2px 4px rgba(0,0,0,0.8);display:flex;align-items:center;justify-content:center;padding:0 180px;text-align:center;max-width:90%;margin:0 auto;word-wrap:break-word;overflow-wrap:break-word;background:linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,0.3) 100%);'>" + line[:180].replace("\"", "&quot;") + "</div>",
            },
            "start": round(t, 2),
            "length": round(text_duration, 2),
            "transition": {"in": "slideLeft", "out": "slideRight"},
        })

        t += slot

    # Create ONE continuous news banner for the entire video (including intro/outro)
    total_with_intro_outro = intro_duration + total_secs + outro_duration
    news_banner_clips = []  # TEMPORARILY DISABLED TO DEBUG AVATAR

    # Create separate intro/outro track (keeps backgrounds separate from text overlays)
    intro_outro_clips = [
        intro_outro["intro"],
        intro_outro["outro"]
    ]

    # Background track - use stock videos if available
    bg_clips = []
    dim_clips = []  # Separate track for dimming overlay

    if stock_videos and len(stock_videos) > 0:
        video_duration = total_secs / len(stock_videos)
        t = intro_duration  # Start after intro
        for video_url in stock_videos:
            bg_clips.append({
                "asset": {
                    "type": "video",
                    "src": video_url,
                    "volume": 0.0,
                },
                "start": round(t, 2),
                "length": round(video_duration, 2),
                "fit": "cover",
                "scale": 1.0,
                "transition": {"in": "fade", "out": "fade"},
                "effect": "zoomIn",
            })
            t += video_duration

        # Add dim overlay on separate track (so text is readable)
        dim_clips.append({
            "asset": {
                "type": "html",
                "html": "<div style='width:100%;height:100%;background:rgba(0,0,0,0.4);'></div>"
            },
            "start": intro_duration,
            "length": round(total_secs, 2),
        })
    else:
        bg_clips.append({
            "asset": {"type": "html", "html": "<div style='width:100%;height:100%;background: radial-gradient(80% 80% at 50% 50%, #182032 0%, #0B0F19 100%);'></div>"},
            "start": intro_duration,
            "length": round(total_secs, 2),
            "fit": "cover",
            "transition": {"in": "fade", "out": "fade"}
        })

    # Audio track - starts after intro
    audio_clips = [{
        "asset": {
            "type": "audio",
            "src": audio_url
        },
        "start": intro_duration + 3.0,  # Intro + 3 second delay
        "length": round(total_secs - 3.0, 2)
    }]

    # Add intro audio if available
    if intro_outro.get("intro_audio_url"):
        audio_clips.insert(0, {
            "asset": {
                "type": "audio",
                "src": intro_outro["intro_audio_url"]
            },
            "start": 0,
            "length": intro_duration
        })

    # Add outro audio if available
    if intro_outro.get("outro_audio_url"):
        outro_start = intro_duration + total_secs
        audio_clips.append({
            "asset": {
                "type": "audio",
                "src": intro_outro["outro_audio_url"]
            },
            "start": outro_start,
            "length": outro_duration
        })

    # Create avatar clip if available (for entire video duration including intro/outro)
    total_with_intro_outro = intro_duration + total_secs + outro_duration
    voice_name = get_active_avatar_voice()
    avatar_clip = create_avatar_clip(total_with_intro_outro, start_time=0, audio_url=audio_url, voice_name=voice_name)

    # Build tracks: intro/outro backgrounds -> content background -> dim -> text -> news banner -> avatar -> audio
    # Avatar MUST be on the LAST visual track (highest number) to render on top
    tracks = [
        {"clips": intro_outro_clips},  # Track 0: intro/outro with backgrounds
        {"clips": bg_clips},           # Track 1: content background (videos or gradient)
    ]
    if dim_clips:
        tracks.append({"clips": dim_clips})  # Track 2: dim overlay (only if using stock videos)
    tracks.append({"clips": text_clips})     # Track 3 or 2: text overlays
    if news_banner_clips:
        tracks.append({"clips": news_banner_clips})  # Track 4 or 3: news banner lower-third
    if avatar_clip:
        tracks.append({"clips": [avatar_clip]})  # Track 5 or 4 or 3: avatar overlay (MUST BE LAST VISUAL!)
    tracks.append({"clips": audio_clips})    # Track 6 or 5 or 4 or 3: audio

    return {
        "timeline": {
            "background": "#0B0F19",
            "tracks": tracks
        },
        "output": {
            "format": "mp4",
            "resolution": "1080",
            "aspectRatio": "16:9",
            "fps": 30,
            "repeat": False
        }
    }


def shotstack_render_and_download(payload: Dict[str, Any], out_path: Path) -> Dict[str, Any]:
    submit = shotstack_render(payload)
    render_id = submit.get("response", {}).get("id") or submit.get("id")
    final = shotstack_poll(render_id)
    url = final.get("response", {}).get("url") or final.get("url")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with out_path.open("wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
    return {"render_id": render_id, "url": url}


def shotstack_thumbnail(title: str, out_path: Path, width: int = 1280, height: int = 720) -> Dict[str, Any]:
    html = (
        "<div style='width:%dpx;height:%dpx;background: radial-gradient(65%% 65%% at 50%% 40%%, #182032 0%%, #0B0F19 100%%);position:relative;display:flex;align-items:center;justify-content:center;'>"
        % (width, height)
        + "<div style=\"font:800 74px Inter,Arial;color:#E8EBFF;max-width:%dpx;text-align:center;line-height:1.08;text-shadow:0 3px 12px rgba(0,0,0,.45)\">%s</div>" % (int(width*0.78), title[:120].replace("\"", "&quot;"))
        + "</div>"
    )
    payload = {
        "timeline": {"tracks": [{"clips": [{"asset": {"type": "html", "html": html}, "start": 0, "length": 2}]}]},
        "output": {"format": "jpg", "resolution": f"{width}x{height}", "fps": 1, "repeat": False},
    }
    submit = shotstack_render(payload)
    rid = submit.get("response", {}).get("id") or submit.get("id")
    final = shotstack_poll(rid)
    url = final.get("response", {}).get("url") or final.get("url")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with out_path.open("wb") as f:
            for chunk in r.iter_content(8192):
                if chunk:
                    f.write(chunk)
    return {"render_id": rid, "url": url}


def shotstack_render(payload: Dict[str, Any]) -> Dict[str, Any]:
    env = os.getenv("SHOTSTACK_ENV", "stage").lower()
    base = "https://api.shotstack.io/stage" if env != "production" else "https://api.shotstack.io/v1"
    key = os.getenv("SHOTSTACK_API_KEY")
    if not key:
        raise RuntimeError("SHOTSTACK_API_KEY is required")
    headers = {"x-api-key": key, "content-type": "application/json"}
    r = requests.post(f"{base}/render", headers=headers, json=payload, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"Shotstack render failed: {r.status_code} {r.text}")
    return r.json()


def render_video(
    audio_path: str,
    overlays: List[str],
    total_secs: float,
    title: str,
    output_path: str,
    stock_videos: Optional[List[str]] = None,
    aspect_ratio: str = "9:16"
) -> Dict[str, Any]:
    """
    Render video using either FFmpeg (local) or Shotstack (cloud) based on VIDEO_RENDERER env var

    Returns:
        For FFmpeg: {"status": "done", "url": file_path}
        For Shotstack: {"render_id": ..., ...}
    """
    renderer = os.getenv("VIDEO_RENDERER", "shotstack").lower()

    if renderer == "ffmpeg":
        print(f"[RENDER] Rendering with FFmpeg (local, no watermark)...")

        # Get intro/outro
        intro_outro = create_intro_outro_clips(intro_duration=3.0, outro_duration=3.0, total_content_secs=total_secs)

        # Read toggles from env (set by API)
        include_avatar_env = os.getenv("INCLUDE_AVATAR", "true").lower() in {"true", "1", "yes"}
        include_logo_env = os.getenv("INCLUDE_LOGO", "true").lower() in {"true", "1", "yes"}

        # Get avatar data
        voice_name = get_active_avatar_voice()
        library_file = Path("avatar_library.json")
        avatar_data = None

        if include_avatar_env and library_file.exists():
            try:
                library = json.loads(library_file.read_text(encoding="utf-8"))
                # Auto-select by gender
                if voice_name:
                    voice_gender = 'female'
                    male_voices = ['J', 'B', 'Q', 'L']
                    for indicator in male_voices:
                        if f'-{indicator}' in voice_name or voice_name.endswith(indicator):
                            voice_gender = 'male'
                            break
                    avatar = next((x for x in library.get('avatars', []) if x.get('gender') == voice_gender), None)
                    if not avatar:
                        avatar = next((x for x in library.get('avatars', []) if x.get('active')), None)
                else:
                    avatar = next((x for x in library.get('avatars', []) if x.get('active')), None)

                if avatar:
                    avatar_data = {
                        'image_url': avatar['image_url'],
                        'position': avatar.get('position', 'bottom-right'),
                        'scale': avatar.get('scale', 25),
                        'opacity': avatar.get('opacity', 100)
                    }
            except Exception as e:
                print(f"Warning: Could not load avatar: {e}")

        # Render with FFmpeg
        resolution = "1080x1920" if aspect_ratio == "9:16" else "1920x1080"
        video_path = render_video_with_ffmpeg(
            audio_path=audio_path,
            overlays=overlays,
            output_path=output_path,
            intro_outro=intro_outro,
            avatar_data=avatar_data,
            stock_videos=stock_videos,
            aspect_ratio=aspect_ratio,
            resolution=resolution
        )

        # Optional logo overlay at the end
        if include_logo_env:
            try:
                thumb_settings_path = Path('thumbnail_settings.json')
                if thumb_settings_path.exists():
                    thumb_settings = json.loads(thumb_settings_path.read_text(encoding='utf-8'))
                    logo_url = thumb_settings.get('logoUrl')
                    logo_position = thumb_settings.get('logoPosition', 'bottom-left')
                    if logo_url:
                        from pathlib import Path as _P
                        import subprocess
                        import imageio_ffmpeg
                        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
                        logo_filename = logo_url.split('/')[-1]
                        logo_path = _P('logos') / logo_filename
                        if logo_path.exists():
                            pos_map = {
                                'bottom-right': 'W-w-20:H-h-20',
                                'bottom-left': '20:H-h-20',
                                'top-right': 'W-w-20:20',
                                'top-left': '20:20',
                                'center': '(W-w)/2:(H-h)/2'
                            }
                            pos = pos_map.get(logo_position, '20:H-h-20')
                            filter_complex = f"[1:v]scale=-1:110,scale=iw*1.25:ih,format=rgba,geq=a='if(gt(a,0),255,0)'[logo];[0:v][logo]overlay={pos}"
                            out_with_logo = Path(output_path).with_name(Path(output_path).stem + '_logo.mp4')
                            cmd = [
                                ffmpeg_bin,
                                '-i', str(Path(video_path)),
                                '-i', str(logo_path),
                                '-filter_complex', filter_complex,
                                '-c:v', 'libx264',
                                '-c:a', 'copy',
                                '-y', str(out_with_logo)
                            ]
                            res = subprocess.run(cmd, capture_output=True, text=True)
                            if res.returncode == 0 and out_with_logo.exists():
                                video_path = str(out_with_logo)
            except Exception as e:
                print(f"[WARN] Logo overlay skipped: {e}")

        return {"status": "done", "url": video_path}

    else:  # shotstack
        print(f"[RENDER] Rendering with Shotstack (cloud, may have watermark)...")
        # Build payload as before
        if aspect_ratio == "9:16":
            payload = build_shotstack_payload(audio_path, overlays, total_secs, title, stock_videos)
        else:
            payload = build_shotstack_payload_wide(audio_path, overlays, total_secs, title, stock_videos)

        return shotstack_render(payload)


def shotstack_poll(render_id: str, timeout_s: int = 900, interval_s: int = 10) -> Dict[str, Any]:
    env = os.getenv("SHOTSTACK_ENV", "stage").lower()
    base = "https://api.shotstack.io/stage" if env != "production" else "https://api.shotstack.io/v1"
    key = os.getenv("SHOTSTACK_API_KEY")
    headers = {"x-api-key": key}
    started = time.time()
    while True:
        r = requests.get(f"{base}/render/{render_id}", headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        status = data.get("response", {}).get("status") or data.get("status")
        if status in {"done", "failed"}:
            return data
        if time.time() - started > timeout_s:
            raise TimeoutError("Timed out waiting for Shotstack render")
        time.sleep(interval_s)


def youtube_upload(file_path: Path, title: str, description: str, tags: List[str], privacy: str = "unlisted", publish_at_iso: Optional[str] = None, thumbnail_path: Optional[Path] = None, chapter_markers: str = "") -> Optional[str]:
    # Standard YouTube upload via OAuth Installed App flow
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import google.auth.exceptions
        import pickle
    except Exception as e:
        print("YouTube upload deps missing, skipping upload.", file=sys.stderr)
        return None

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    creds = None
    token_path = Path("token.pickle")
    if token_path.exists():
        with token_path.open("rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secrets_path = Path(__file__).parent.parent / "client_secrets.json"
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
            creds = flow.run_local_server(port=0)
        with token_path.open("wb") as f:
            pickle.dump(creds, f)

    service = build("youtube", "v3", credentials=creds)

    # Enhance description with chapter markers
    full_description = description
    if chapter_markers:
        full_description = f"{description}\n\nâ±ï¸ CHAPTERS:\n{chapter_markers}"

    body = {
        "snippet": {
            "title": title[:100],
            "description": full_description[:5000],
            "tags": tags[:500],
            "categoryId": "27",  # Education as a default
        },
        "status": {"privacyStatus": privacy},
    }
    if publish_at_iso and privacy in {"private", "unlisted"}:
        body["status"]["publishAt"] = publish_at_iso
    media = MediaFileUpload(str(file_path), chunksize=-1, resumable=True, mimetype="video/mp4")
    request = service.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
    video_id = response.get("id")
    if thumbnail_path and video_id:
        try:
            service.thumbnails().set(videoId=video_id, media_body=str(thumbnail_path)).execute()
        except Exception:
            pass
    return f"https://youtu.be/{video_id}" if video_id else None


def sheets_append_log(row: List[str]) -> None:
    try:
        from googleapiclient.discovery import build
        creds = get_google_service(['https://www.googleapis.com/auth/spreadsheets'], token_file='token.sheets.pickle')
        service = build('sheets', 'v4', credentials=creds)
        sheet_id = os.getenv('GSHEET_ID')
        if not sheet_id:
            return
        body = {"values": [row]}
        service.spreadsheets().values().append(spreadsheetId=sheet_id, range='Log!A:Z', valueInputOption='RAW', insertDataOption='INSERT_ROWS', body=body).execute()
    except Exception:
        pass


# ---------- CLI ----------

def main():
    read_env()
    parser = argparse.ArgumentParser(description="Blog-to-Video CLI (OpenAI + ElevenLabs + Shotstack + YouTube)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="Source URL to fetch and summarize")
    src.add_argument("--text", help="Direct source text input")
    parser.add_argument("--brand", default="Many Sources Say", help="Brand or channel name for context")
    parser.add_argument("--outdir", default="out", help="Output directory")
    parser.add_argument("--no-upload", action="store_true", help="Skip YouTube upload")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    ensure_dir(outdir)

    # 1) Fetch/prepare source
    if args.url:
        print(f"Fetching: {args.url}")
        source_text = fetch_url_text(args.url)
    else:
        source_text = args.text

    # 2) LLM: narration + overlays + metadata
    print("Generating narration and overlays with OpenAI...")
    llm = openai_generate(source_text, args.brand)
    narration = llm["narration"]
    overlays = llm["overlays"]
    title = llm["title"]
    description = llm["description"]
    keywords = llm["keywords"]
    visual_cues = llm.get("visual_cues", keywords[:5])

    # Save draft artifacts
    (outdir / "script.json").write_text(json.dumps(llm, indent=2), encoding="utf-8")

    # 3) Get stock footage (if enabled)
    stock_videos = []
    if os.getenv("ENABLE_STOCK_FOOTAGE", "false").lower() in {"true", "1", "yes"}:
        # Use topic keywords first (more specific), then visual cues as fallback
        topic_keywords = topic_data.get("keywords", []) if isinstance(topic_data, dict) else []
        search_keywords = topic_keywords[:3] if topic_keywords else visual_cues[:3]
        print(f"Fetching stock footage for: {', '.join(search_keywords)}...")
        stock_videos = get_stock_footage_for_keywords(search_keywords, max_clips=3)
        print(f"Found {len(stock_videos)} stock video clips")

    # 4) TTS with SSML
    print("Generating voiceover with Google Cloud TTS...")
    audio_path = outdir / "voiceover.mp3"
    google_tts(narration, audio_path, use_ssml=True)
    duration = get_mp3_duration_seconds(audio_path)
    print(f"Audio duration: {duration:.1f}s")

    # 5) Upload audio to Google Drive (public)
    print("Uploading audio to Google Drive (public)...")
    audio_up = drive_upload_public(audio_path, os.getenv("DRIVE_AUDIO_FOLDER", "/autopilot/audio/"))
    audio_url = audio_up['download_url']
    print(f"Audio URL: {audio_url}")

    # 6) Shotstack render with stock footage
    print("Submitting render to Shotstack...")
    payload = build_shotstack_payload(audio_url, overlays, duration, title, stock_videos)
    (outdir / "shotstack_payload.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    submit = shotstack_render(payload)
    render_id = submit.get("response", {}).get("id") or submit.get("id")
    if not render_id:
        raise RuntimeError(f"Unexpected Shotstack response: {submit}")
    print(f"Render ID: {render_id}")

    print("Polling render status...")
    final = shotstack_poll(render_id)
    (outdir / "shotstack_final.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    assets = final.get("response", {}).get("assets") or {}
    video_url = assets.get("url") or final.get("url")
    if not video_url:
        raise RuntimeError("No video URL in Shotstack response")
    print(f"Video URL: {video_url}")

    # Download MP4
    print("Downloading MP4...")
    mp4_path = outdir / "video.mp4"
    with requests.get(video_url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with mp4_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    # 7) Upload MP4 to Google Drive (public)
    print("Uploading MP4 to Google Drive (public)...")
    video_up = drive_upload_public(mp4_path, os.getenv("DRIVE_RENDERS_FOLDER", "/autopilot/renders/"))

    # 8) Generate chapter markers
    chapter_markers = generate_chapter_markers(overlays, duration)

    # 9) Generate thumbnail variants
    print("Generating thumbnail variants...")
    thumb_variants = generate_thumbnail_variants(title, outdir, count=int(os.getenv("THUMBNAIL_VARIANTS", "3")))
    print(f"Created {len(thumb_variants)} thumbnail variants")

    # 10) Upload to YouTube (optional)
    video_link = None
    if not args.no_upload:
        privacy = os.getenv("YOUTUBE_PRIVACY_STATUS", "unlisted")
        print("Uploading to YouTube...")
        try:
            # Use first thumbnail variant
            thumb_path = thumb_variants[0] if thumb_variants else None
            video_link = youtube_upload(mp4_path, title, description, keywords, privacy,
                                       thumbnail_path=thumb_path, chapter_markers=chapter_markers)
        except Exception as e:
            print(f"YouTube upload failed: {e}", file=sys.stderr)

    # 8) Summarize
    summary = {
        "source_url": args.url,
        "title": title,
        "description": description,
        "keywords": keywords,
        "audio_url": audio_url,
        "audio_drive_file_id": audio_up['file_id'],
        "shotstack_render_id": render_id,
        "shotstack_video_url": video_url,
        "video_drive_file_id": video_up['file_id'],
        "video_drive_view_url": video_up['view_url'],
        "youtube_url": video_link,
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nDone. Summary written to", outdir / "summary.json")


if __name__ == "__main__":
    main()

