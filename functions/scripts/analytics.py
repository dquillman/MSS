"""
YouTube Analytics Module
Track video performance and optimize based on data
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_video_analytics(video_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch analytics for a YouTube video
    Returns metrics: views, likes, comments, watch_time, ctr, avg_view_duration
    """
    try:
        from googleapiclient.discovery import build
        from scripts.make_video import get_google_service
    except ImportError:
        print("YouTube API client not available")
        return None

    try:
        # Use YouTube Data API v3
        scopes = ["https://www.googleapis.com/auth/youtube.readonly",
                  "https://www.googleapis.com/auth/yt-analytics.readonly"]
        creds = get_google_service(scopes, token_file='token.youtube_analytics.pickle')

        youtube = build("youtube", "v3", credentials=creds)
        youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)

        # Get basic video stats
        video_response = youtube.videos().list(
            part="statistics,snippet,contentDetails",
            id=video_id
        ).execute()

        if not video_response.get("items"):
            return None

        video = video_response["items"][0]
        stats = video.get("statistics", {})
        snippet = video.get("snippet", {})
        content = video.get("contentDetails", {})

        # Get analytics (requires channel ownership)
        try:
            # Get last 30 days of analytics
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=30)

            analytics_response = youtube_analytics.reports().query(
                ids="channel==MINE",
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained",
                dimensions="video",
                filters=f"video=={video_id}",
            ).execute()

            analytics = {}
            if analytics_response.get("rows"):
                row = analytics_response["rows"][0]
                headers = [h["name"] for h in analytics_response.get("columnHeaders", [])]
                analytics = dict(zip(headers, row))
        except Exception as e:
            print(f"Analytics API error (may not have access): {e}")
            analytics = {}

        # Combine data
        metrics = {
            "video_id": video_id,
            "title": snippet.get("title"),
            "published_at": snippet.get("publishedAt"),
            "duration": content.get("duration"),
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "watch_time_minutes": analytics.get("estimatedMinutesWatched", 0),
            "avg_view_duration_seconds": analytics.get("averageViewDuration", 0),
            "avg_view_percentage": analytics.get("averageViewPercentage", 0),
            "shares": analytics.get("shares", 0),
            "subscribers_gained": analytics.get("subscribersGained", 0),
            "engagement_rate": 0.0,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        # Calculate engagement rate
        if metrics["views"] > 0:
            metrics["engagement_rate"] = (metrics["likes"] + metrics["comments"] + metrics["shares"]) / metrics["views"] * 100

        return metrics

    except Exception as e:
        print(f"Failed to fetch analytics for {video_id}: {e}")
        return None


def save_analytics(video_id: str, metrics: Dict[str, Any]) -> None:
    """Save analytics to local JSON file"""
    analytics_dir = Path("out/analytics")
    analytics_dir.mkdir(parents=True, exist_ok=True)

    log_file = analytics_dir / f"{video_id}_history.json"

    # Load existing history
    history = []
    if log_file.exists():
        try:
            history = json.loads(log_file.read_text(encoding="utf-8"))
        except:
            history = []

    # Append new entry
    history.append(metrics)

    # Save
    log_file.write_text(json.dumps(history, indent=2), encoding="utf-8")


def analyze_performance(video_id: str) -> Dict[str, Any]:
    """
    Analyze video performance and provide recommendations
    """
    metrics = get_video_analytics(video_id)
    if not metrics:
        return {"status": "error", "message": "Could not fetch analytics"}

    # Save metrics
    save_analytics(video_id, metrics)

    # Performance benchmarks (adjust based on your channel)
    benchmarks = {
        "avg_view_percentage": 50,  # 50% retention is good
        "engagement_rate": 5.0,      # 5% engagement is solid
        "ctr": 4.0,                  # 4% CTR is above average
    }

    analysis = {
        "video_id": video_id,
        "metrics": metrics,
        "score": 0,
        "recommendations": [],
        "strengths": [],
        "weaknesses": [],
    }

    # Analyze retention
    if metrics.get("avg_view_percentage", 0) >= benchmarks["avg_view_percentage"]:
        analysis["strengths"].append("Strong viewer retention")
        analysis["score"] += 30
    else:
        analysis["weaknesses"].append("Low retention - consider stronger hooks")
        analysis["recommendations"].append("Improve opening 3 seconds to hook viewers")

    # Analyze engagement
    if metrics.get("engagement_rate", 0) >= benchmarks["engagement_rate"]:
        analysis["strengths"].append("High audience engagement")
        analysis["score"] += 30
    else:
        analysis["weaknesses"].append("Low engagement rate")
        analysis["recommendations"].append("Add stronger calls-to-action for likes/comments")

    # Analyze views
    if metrics.get("views", 0) > 1000:
        analysis["strengths"].append("Good view count")
        analysis["score"] += 40
    elif metrics.get("views", 0) > 100:
        analysis["score"] += 20
    else:
        analysis["weaknesses"].append("Low view count")
        analysis["recommendations"].append("Optimize title/thumbnail for better CTR")

    # Overall grade
    if analysis["score"] >= 80:
        analysis["grade"] = "A - Excellent"
    elif analysis["score"] >= 60:
        analysis["grade"] = "B - Good"
    elif analysis["score"] >= 40:
        analysis["grade"] = "C - Average"
    else:
        analysis["grade"] = "D - Needs Improvement"

    return analysis


def get_top_performing_videos(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get top performing videos from channel
    Useful for identifying what content works best
    """
    try:
        from googleapiclient.discovery import build
        from scripts.make_video import get_google_service

        scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
        creds = get_google_service(scopes, token_file='token.youtube_analytics.pickle')
        youtube = build("youtube", "v3", credentials=creds)

        # Get channel uploads
        channels_response = youtube.channels().list(
            part="contentDetails",
            mine=True
        ).execute()

        if not channels_response.get("items"):
            return []

        uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        # Get recent uploads
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50
        ).execute()

        video_ids = [item["snippet"]["resourceId"]["videoId"] for item in playlist_response.get("items", [])]

        if not video_ids:
            return []

        # Get statistics for all videos
        videos_response = youtube.videos().list(
            part="statistics,snippet",
            id=",".join(video_ids)
        ).execute()

        videos = []
        for video in videos_response.get("items", []):
            stats = video.get("statistics", {})
            snippet = video.get("snippet", {})

            videos.append({
                "video_id": video["id"],
                "title": snippet.get("title"),
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "published_at": snippet.get("publishedAt"),
            })

        # Sort by views
        videos.sort(key=lambda x: x["views"], reverse=True)

        return videos[:limit]

    except Exception as e:
        print(f"Failed to fetch top videos: {e}")
        return []


def generate_performance_report() -> str:
    """
    Generate a markdown performance report for all tracked videos
    """
    analytics_dir = Path("out/analytics")
    if not analytics_dir.exists():
        return "No analytics data available yet."

    report = ["# YouTube Performance Report\n"]
    report.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n")

    # Load all analytics files
    all_metrics = []
    for file in analytics_dir.glob("*_history.json"):
        try:
            history = json.loads(file.read_text(encoding="utf-8"))
            if history:
                all_metrics.append(history[-1])  # Latest entry
        except:
            continue

    if not all_metrics:
        return "No analytics data available yet."

    # Sort by views
    all_metrics.sort(key=lambda x: x.get("views", 0), reverse=True)

    report.append(f"## Summary\n")
    report.append(f"- Total videos tracked: {len(all_metrics)}\n")
    report.append(f"- Total views: {sum(m.get('views', 0) for m in all_metrics):,}\n")
    report.append(f"- Total likes: {sum(m.get('likes', 0) for m in all_metrics):,}\n")
    report.append(f"- Avg engagement rate: {sum(m.get('engagement_rate', 0) for m in all_metrics) / len(all_metrics):.2f}%\n\n")

    report.append("## Top Performing Videos\n\n")
    for i, metrics in enumerate(all_metrics[:10], 1):
        report.append(f"### {i}. {metrics.get('title', 'Unknown')}\n")
        report.append(f"- Video ID: `{metrics.get('video_id')}`\n")
        report.append(f"- Views: {metrics.get('views', 0):,}\n")
        report.append(f"- Likes: {metrics.get('likes', 0):,}\n")
        report.append(f"- Engagement Rate: {metrics.get('engagement_rate', 0):.2f}%\n")
        report.append(f"- Avg View %: {metrics.get('avg_view_percentage', 0):.1f}%\n\n")

    return "".join(report)


if __name__ == "__main__":
    # CLI for testing
    import sys

    if len(sys.argv) < 2:
        print("Usage: python analytics.py <video_id>")
        sys.exit(1)

    video_id = sys.argv[1]
    analysis = analyze_performance(video_id)

    print(json.dumps(analysis, indent=2))
