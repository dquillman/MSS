"""
Enhanced utilities for MSS video creation
Includes: stock footage, retry logic, SSML, advanced thumbnails
"""
import os
import random
import time
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


# ---------- Retry Logic ----------

def retry_api_call(max_attempts: int = 3):
    """Decorator for retrying API calls with exponential backoff"""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.exceptions.RequestException, TimeoutError)),
        reraise=True
    )


# ---------- Stock Footage (Pexels) ----------

@retry_api_call()
def search_pexels_videos(query: str, per_page: int = 5) -> List[Dict[str, Any]]:
    """
    Search Pexels for stock video footage
    Returns list of video objects with download URLs
    """
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        return []

    headers = {"Authorization": api_key}
    url = "https://api.pexels.com/videos/search"
    params = {
        "query": query,
        "per_page": per_page,
        "orientation": "portrait",  # Better for shorts
        "size": "large"  # Get higher quality videos
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        videos = []

        for vid in data.get("videos", [])[:per_page]:
            # Find the best quality video file
            files = vid.get("video_files", [])
            if not files:
                continue

            # Filter to HD quality only (max 1920px to avoid 4K)
            # 4K videos create gigabyte files that browsers can't handle
            hd_files = [f for f in files if f.get("width", 0) <= 1920]

            if not hd_files:
                # Fallback to lowest quality if no HD available
                hd_files = files

            # Sort by width descending and pick best HD quality
            sorted_files = sorted(hd_files, key=lambda f: f.get("width", 0), reverse=True)
            best_file = sorted_files[0]

            videos.append({
                "id": vid.get("id"),
                "url": best_file.get("link"),
                "duration": vid.get("duration", 10),
                "width": best_file.get("width", 1080),
                "height": best_file.get("height", 1920),
            })

        return videos
    except Exception as e:
        print(f"Pexels API error: {e}")
        return []


def get_stock_footage_for_keywords(keywords: List[str], max_clips: int = 3) -> List[str]:
    """
    Get stock footage URLs for a list of keywords
    Returns list of video URLs
    """
    if not os.getenv("ENABLE_STOCK_FOOTAGE", "").lower() in {"true", "1", "yes"}:
        return []

    video_urls = []

    # Take top keywords
    for kw in keywords[:max_clips]:
        videos = search_pexels_videos(kw, per_page=2)
        if videos:
            video_urls.append(videos[0]["url"])

        # Rate limit
        time.sleep(0.5)

    return video_urls


# ---------- SSML Enhancement ----------

def enhance_narration_with_ssml(text: str) -> str:
    """
    Enhance narration text with SSML tags for natural delivery
    Adds pauses, emphasis, and prosody control
    """
    if not os.getenv("ENABLE_SSML", "").lower() in {"true", "1", "yes"}:
        return text

    # Add pauses after sentences
    text = text.replace(". ", ". <break time='500ms'/> ")
    text = text.replace("! ", "! <break time='500ms'/> ")
    text = text.replace("? ", "? <break time='500ms'/> ")

    # Add pauses after commas
    text = text.replace(", ", ", <break time='250ms'/> ")

    # Emphasize important words (simple heuristic)
    important_words = ["important", "critical", "key", "major", "significant", "breaking", "new"]
    for word in important_words:
        text = text.replace(f" {word} ", f" <emphasis level='strong'>{word}</emphasis> ")
        text = text.replace(f" {word.capitalize()} ", f" <emphasis level='strong'>{word.capitalize()}</emphasis> ")

    # Wrap in SSML speak tag
    ssml = f"<speak>{text}</speak>"

    return ssml


# ---------- Advanced Thumbnails ----------

def generate_thumbnail_variants(title: str, out_dir: Path, count: int = 3) -> List[Path]:
    """
    Generate multiple thumbnail variants with different styles
    Returns list of paths to generated thumbnails
    """
    from PIL import Image, ImageDraw, ImageFont

    variants = []

    # Color schemes
    schemes = [
        {"bg": [(24, 32, 50), (11, 15, 25)], "text": (232, 235, 255), "accent": (230, 57, 70)},  # Dark blue-red
        {"bg": [(76, 29, 149), (31, 41, 55)], "text": (255, 255, 255), "accent": (251, 191, 36)},  # Purple-yellow
        {"bg": [(17, 24, 39), (6, 78, 59)], "text": (209, 250, 229), "accent": (52, 211, 153)},  # Dark green
    ]

    for i in range(min(count, len(schemes))):
        scheme = schemes[i]
        width, height = 1280, 720

        # Create gradient background
        img = Image.new('RGB', (width, height), scheme["bg"][1])
        draw = ImageDraw.Draw(img)

        # Draw gradient (simple top-to-bottom)
        for y in range(height):
            ratio = y / height
            color = tuple(int(scheme["bg"][0][c] * (1-ratio) + scheme["bg"][1][c] * ratio) for c in range(3))
            draw.line([(0, y), (width, y)], fill=color)

        # Draw title text (split into lines if too long)
        try:
            # Try to use a nice font (DejaVu Sans is installed in Docker)
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 74)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except Exception as e:
            # Fallback: try to find any font, then default
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Wrap text
        words = title.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            # Rough width estimation
            if len(test_line) > 25:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
            else:
                current_line.append(word)

        if current_line:
            lines.append(" ".join(current_line))

        # Center text vertically
        line_height = 90
        total_height = len(lines) * line_height
        start_y = (height - total_height) // 2

        for idx, line in enumerate(lines):
            # Get text size
            bbox = draw.textbbox((0, 0), line, font=font_large)
            text_width = bbox[2] - bbox[0]
            text_x = (width - text_width) // 2
            text_y = start_y + idx * line_height

            # Draw shadow
            draw.text((text_x + 3, text_y + 3), line, fill=(0, 0, 0), font=font_large)
            # Draw text
            draw.text((text_x, text_y), line, fill=scheme["text"], font=font_large)

        # Add accent bar at bottom
        draw.rectangle([(0, height - 20), (width, height)], fill=scheme["accent"])

        # Save variant
        out_path = out_dir / f"thumb_variant_{i+1}.jpg"
        img.save(out_path, quality=95, optimize=True)
        variants.append(out_path)

    return variants


# ---------- YouTube Trending Topics ----------

@retry_api_call()
def get_youtube_trending_topics(region: str = "US", max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch trending videos from YouTube to identify hot topics
    Requires YouTube Data API key in YOUTUBE_API_KEY env var
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return []

    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,statistics",
        "chart": "mostPopular",
        "regionCode": region,
        "maxResults": max_results,
        "key": api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        topics = []
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})

            topics.append({
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "description": snippet.get("description", "")[:200],
                "views": int(stats.get("viewCount", 0)),
                "tags": snippet.get("tags", []),
                "category": snippet.get("categoryId", ""),
            })

        return topics
    except Exception as e:
        print(f"YouTube Trending API error: {e}")
        return []


# ---------- Chapter Markers ----------

def generate_chapter_markers(overlays: List[str], duration_secs: float) -> str:
    """
    Generate YouTube chapter markers (timestamps) from overlay text
    Returns formatted string for video description
    """
    if not overlays or duration_secs < 30:
        return ""

    chapters = ["0:00 Introduction\n"]

    # Distribute chapters evenly
    n_chapters = min(len(overlays), 8)  # Max 8 chapters
    interval = duration_secs / (n_chapters + 1)

    for i, overlay in enumerate(overlays[:n_chapters]):
        timestamp = int((i + 1) * interval)
        minutes = timestamp // 60
        seconds = timestamp % 60

        # Clean overlay text for chapter title
        chapter_title = overlay.strip()[:50]  # Max 50 chars
        chapters.append(f"{minutes}:{seconds:02d} {chapter_title}\n")

    return "".join(chapters)


# ---------- Enhanced OpenAI Prompts ----------

def get_enhanced_script_prompt(source_text: str, brand: str = "Many Sources Say") -> str:
    """
    Generate an enhanced prompt for OpenAI script generation
    Focuses on hook, story arc, and engagement with viral video patterns
    """
    return f"""You are an expert YouTube scriptwriter for {brand}. Create a compelling 90-150 second video script optimized for maximum views.

CRITICAL REQUIREMENTS:
1. HOOK (first 3-5 seconds): Must use one of these proven patterns:
   - "I analyzed [number] [things] and discovered [shocking finding]..."
   - "Most [people/creators] don't know this about [topic]..."
   - "After [experiment/research], I found [surprising result]..."
   - "This [number] [unit] secret changed everything..."
   - "[Bold claim] - Here's why nobody tells you this..."
   The hook MUST create curiosity gap - tease answer without revealing it immediately.

2. STORY ARC: Problem → Insight → Revelation → Takeaway
   - Start with a pain point or burning question
   - Build tension with surprising information
   - Reveal the key insight with specificity
   - End with actionable takeaway

3. PACING: Vary sentence length. Use short punchy sentences (3-7 words) for impact, longer ones for context.

4. EMOTION: Include moments of:
   - Surprise (shocking statistics or facts)
   - Curiosity (questions that tease answers)
   - Urgency (time-sensitive or valuable information)

5. RETENTION: End each major point with a reason to keep watching:
   - "But here's where it gets interesting..."
   - "Wait until you hear this part..."
   - "The real secret is..."

6. CALL TO ACTION: End with SPECIFIC engagement request (choose one):
   - "Drop a comment telling me [specific question related to topic]"
   - "Like this video if you want more secrets about [related topic]"
   - "Subscribe if you want to see [next video idea related to this topic]"
   - "Share this with one person who needs to see this"

7. SEO OPTIMIZATION:
   - Title (50-60 chars): Must include power words: "How", "Why", "Secret", "Truth", "Exposed", "Revealed", "The Truth About", "Why Nobody Tells You"
   - Use specific numbers when possible (e.g., "5 Secrets", "100M Views")
   - Description: First 2 sentences MUST contain primary keywords and value proposition

Return JSON with:
- narration: 90-150 second script with natural speech patterns
- overlays: 6-10 short text overlays (3-7 words each) highlighting key points
- hook: The first 5 seconds of narration (for A/B testing)
- title: Compelling YouTube title (50-60 chars, includes keywords and power words)
- description: SEO-rich description (first 2 sentences with keywords, then value prop)
- keywords: 10-15 search-optimized tags (mix broad + specific + long-tail)
- visual_cues: Array of 3-5 keywords for stock footage matching
- engagement_cta: Specific call-to-action text for end of video

Source content:
{source_text[:12000]}"""


def get_enhanced_topic_prompt(brand: str = "Many Sources Say", trending_topics: Optional[List[str]] = None, include_meta_content: bool = True) -> str:
    """
    Generate an enhanced prompt for topic ideation with trending awareness and meta-content options
    """
    trending_context = ""
    if trending_topics:
        trending_context = f"\n\nCurrent trending topics for inspiration: {', '.join(trending_topics[:5])}"

    meta_content_instruction = ""
    if include_meta_content:
        meta_content_instruction = f"""
SPECIAL INSTRUCTION: Include at least 1-2 "meta-content" topics about YouTube automation, AI video creation, or content strategy. Examples:
- "How I Create 100 YouTube Videos Per Week Using AI"
- "Why AI-Generated Videos Get More Views Than Traditional Content"
- "Behind the Scenes: My Automated YouTube Channel"
- "YouTube Automation Secrets That Actually Work"
- "I Analyzed 1000 Viral Videos - Here's the Pattern"
These topics leverage {brand}'s unique value proposition and create self-referential proof-of-concept content."""

    return f"""You are a senior YouTube strategist and viral content expert for {brand}.

Generate 5 HIGH-PERFORMING video topic ideas for today. Each must:
1. Tap into current interest, search demand, or timeless curiosity
2. Have clear search intent (what would someone Google?)
3. Promise specific value in under 60 seconds
4. Use power words: "Why", "How", "Secret", "Truth", "Exposed", "Revealed", "The Truth About", "Why Nobody Tells You"
5. Be achievable with narration + text overlays + stock footage
6. Create curiosity gap (tease answer without revealing immediately)

{trending_context}

{meta_content_instruction}

Return JSON array with 5 topics, each containing:
- title: Working title (internal use)
- angle: Unique perspective or hook (1 sentence that creates curiosity)
- keywords: 8-12 primary search keywords
- yt_title: Optimized YouTube title (50-60 chars, clickable but not clickbait)
   - Must include power words and numbers when possible
   - Patterns: "How [X] Actually Works", "Why [X] Is Wrong", "[X] Explained: The Secret", "I Analyzed [N] [Things] and Found [Surprise]"
- yt_description: SEO-rich description (100-150 words)
   - First 2 sentences: Must contain primary keywords and value proposition
   - Pattern: "In this video, I reveal [X] that [audience] needs to know..." or "After [research], I discovered [insight]..."
   - Include engagement hook: "Drop a comment if..." or "Subscribe for..."
- yt_tags: 15-20 diverse tags (mix broad + specific + long-tail keywords)
- outline: 5-7 bullet points of key talking points
- visual_cues: 4-6 keywords for stock footage matching (e.g., "technology", "cityscape", "nature")
- hook_options: 3 alternative opening hooks for A/B testing (must use viral patterns like "I analyzed...", "Most people don't know...", etc.)

Prioritize topics that:
- Answer a burning question
- Reveal surprising information or secrets
- Solve a common problem
- Explain a trending phenomenon
- Challenge a common belief
- Provide insider knowledge or behind-the-scenes insights
- Use specific numbers or statistics for credibility"""


# ---------- Performance Analytics Stub ----------

def track_video_performance(video_id: str, metrics: Dict[str, Any]) -> None:
    """
    Track video performance metrics
    TODO: Implement full analytics dashboard
    """
    # For now, just log to file
    log_dir = Path("out/analytics")
    log_dir.mkdir(parents=True, exist_ok=True)

    import json
    from datetime import datetime, timezone

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "video_id": video_id,
        **metrics
    }

    log_file = log_dir / f"{video_id}.json"
    log_file.write_text(json.dumps(log_entry, indent=2), encoding="utf-8")


# ---------- Parallel Execution Helper ----------

def run_in_parallel(tasks: List[Callable]) -> List[Any]:
    """
    Run multiple tasks in parallel using threading
    Returns list of results in same order as tasks
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = [None] * len(tasks)

    with ThreadPoolExecutor(max_workers=min(len(tasks), 4)) as executor:
        future_to_idx = {executor.submit(task): i for i, task in enumerate(tasks)}

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                print(f"Task {idx} failed: {e}")
                results[idx] = None

    return results
