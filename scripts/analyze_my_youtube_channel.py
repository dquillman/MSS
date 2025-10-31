"""
Analyze your YouTube channel and provide actionable recommendations
for getting more viewers based on viral video strategies
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from scripts.analytics import get_top_performing_videos, analyze_performance
from scripts.video_utils import get_enhanced_topic_prompt


def get_channel_insights() -> Dict[str, Any]:
    """
    Get comprehensive insights about your YouTube channel
    Returns recommendations based on viral video patterns
    """
    print("🔍 Analyzing your YouTube channel...")
    
    # Get top performing videos
    print("📊 Fetching your top videos...")
    top_videos = get_top_performing_videos(limit=20)
    
    if not top_videos:
        return {
            "status": "error",
            "message": "Could not fetch videos. Make sure you're authenticated with YouTube API.",
            "recommendations": [
                "1. Check your YouTube API authentication: `python setup_youtube_credentials.py`",
                "2. Verify your YouTube channel has uploaded videos",
                "3. Ensure you have YouTube Data API v3 enabled in Google Cloud Console"
            ]
        }
    
    print(f"✅ Found {len(top_videos)} videos")
    
    # Analyze performance
    insights = {
        "total_videos": len(top_videos),
        "total_views": sum(v.get("views", 0) for v in top_videos),
        "avg_views": sum(v.get("views", 0) for v in top_videos) / len(top_videos) if top_videos else 0,
        "top_videos": top_videos[:5],  # Top 5 performers
        "recommendations": [],
        "weaknesses": [],
        "strengths": [],
        "action_plan": []
    }
    
    # Analyze patterns in top performers
    if top_videos:
        top_5 = top_videos[:5]
        
        # Check if videos have meta-content (automation/AI)
        meta_content_terms = ["AI", "automate", "automatic", "system", "MSS", "create 100", "generate"]
        meta_videos = [v for v in top_videos if any(term in v.get("title", "").upper() for term in meta_content_terms)]
        
        if meta_videos:
            insights["strengths"].append(f"✅ {len(meta_videos)} meta-content videos found - leveraging your unique value!")
        else:
            insights["weaknesses"].append("❌ No meta-content videos found - missing opportunity for self-referential content")
            insights["recommendations"].append("Create meta-content about your automation system (e.g., 'How I Create 100 Videos with AI')")
        
        # Check titles for viral patterns
        viral_patterns = ["how", "why", "secret", "truth", "exposed", "revealed", "analyzed", "don't know"]
        viral_titles = [v for v in top_5 if any(pattern in v.get("title", "").lower() for pattern in viral_patterns)]
        
        if viral_titles:
            insights["strengths"].append(f"✅ {len(viral_titles)}/{len(top_5)} top videos use viral title patterns")
        else:
            insights["weaknesses"].append("❌ Top videos don't use viral title patterns")
            insights["recommendations"].append("Add power words to titles: 'How', 'Why', 'Secret', 'Truth', 'The Truth About'")
        
        # Check engagement rates
        high_engagement = [v for v in top_5 if v.get("engagement_rate", 0) > 3.0]
        if high_engagement:
            insights["strengths"].append(f"✅ {len(high_engagement)} videos have strong engagement (>3%)")
        else:
            insights["weaknesses"].append("❌ Low engagement on top videos - viewers not interacting")
            insights["recommendations"].append("Add stronger calls-to-action and engagement hooks in scripts")
        
        # Analyze view counts
        views = [v.get("views", 0) for v in top_videos]
        if views:
            insights["avg_views"] = sum(views) / len(views)
            if insights["avg_views"] < 100:
                insights["weaknesses"].append("❌ Low average views - need better discovery")
                insights["recommendations"].append("Optimize for search and suggested videos with better SEO")
    
    return generate_action_plan(insights)


def generate_action_plan(insights: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate specific action plan based on insights
    """
    plan = insights.copy()
    plan["priority_actions"] = []
    
    # Priority 1: Meta-content (biggest opportunity)
    if "No meta-content videos" in str(insights.get("weaknesses", [])):
        plan["priority_actions"].append({
            "priority": "🔥 CRITICAL",
            "action": "Create 5 meta-content videos about your MSS automation system",
            "examples": [
                "How I Create 100 YouTube Videos Per Week Using AI",
                "Why AI-Generated Videos Get More Views Than Traditional Content",
                "Behind the Scenes: My Automated YouTube Channel",
                "YouTube Automation Secrets That Actually Work",
                "I Analyzed 1000 Viral Videos - Here's the Pattern I Found"
            ],
            "why": "Meta-content leverages your unique value prop and creates self-referential proof"
        })
    
    # Priority 2: Title optimization
    if insights["avg_views"] < 1000:
        plan["priority_actions"].append({
            "priority": "⚡ HIGH",
            "action": "Revise all existing video titles with viral patterns",
            "examples": [
                "OLD: 'Climate Change' → NEW: 'The Truth About Climate Change Policies (What Nobody Tells You)'",
                "OLD: 'AI Technology' → NEW: 'I Analyzed 100 AI Videos - Here's the Secret Pattern'",
                "OLD: 'Crypto' → NEW: 'Why Crypto Broke Every Rule in 2025 (The Hidden Truth)'"
            ],
            "why": "Viral patterns increase CTR by 40-200%"
        })
    
    # Priority 3: Thumbnail testing
    plan["priority_actions"].append({
        "priority": "📊 MEDIUM",
        "action": "A/B test thumbnails on top 3 videos",
        "how": [
            "1. Generate 3 thumbnail variants for each video",
            "2. Change thumbnail on YouTube every 48 hours",
            "3. Track which gets highest CTR",
            "4. Use winning style for future videos"
        ],
        "why": "Thumbnails are 80% of click-through rate"
    })
    
    # Priority 4: Upload consistency
    if insights["total_videos"] < 10:
        plan["priority_actions"].append({
            "priority": "📅 HIGH",
            "action": f"Increase upload frequency - you have {insights['total_videos']} videos",
            "recommendation": "Upload 3-5 videos per week consistently",
            "why": "Consistency signals quality to YouTube algorithm"
        })
    
    # Priority 5: Engagement loops
    plan["priority_actions"].append({
        "priority": "💬 MEDIUM",
        "action": "Add specific engagement CTAs to all new videos",
        "examples": [
            "Drop a comment if you think AI will replace creators",
            "Like if you want more automation secrets",
            "Subscribe for tomorrow's video about [related topic]"
        ],
        "why": "Engagement drives recommendation algorithm"
    })
    
    return plan


def print_insights_report(insights: Dict[str, Any]):
    """
    Print a formatted insights report
    """
    print("\n" + "="*80)
    print("🎬 YOUR YOUTUBE CHANNEL ANALYSIS")
    print("="*80)
    
    print(f"\n📊 OVERVIEW:")
    print(f"   Total Videos: {insights.get('total_videos', 0)}")
    print(f"   Total Views: {insights.get('total_views', 0):,}")
    print(f"   Avg Views per Video: {insights.get('avg_views', 0):.0f}")
    
    if insights.get("strengths"):
        print(f"\n✅ STRENGTHS:")
        for strength in insights["strengths"]:
            print(f"   {strength}")
    
    if insights.get("weaknesses"):
        print(f"\n❌ AREAS FOR IMPROVEMENT:")
        for weakness in insights["weaknesses"]:
            print(f"   {weakness}")
    
    if insights.get("top_videos"):
        print(f"\n🏆 TOP 5 VIDEOS:")
        for i, video in enumerate(insights["top_videos"][:5], 1):
            print(f"   {i}. {video.get('title', 'Unknown')[:60]}")
            print(f"      Views: {video.get('views', 0):,}")
            engagement = video.get('engagement_rate', 0)
            if engagement > 0:
                print(f"      Engagement: {engagement:.1f}%")
    
    if insights.get("priority_actions"):
        print(f"\n🎯 ACTION PLAN:")
        for i, action in enumerate(insights["priority_actions"], 1):
            print(f"\n   {i}. {action['priority']}: {action['action']}")
            if action.get("why"):
                print(f"      Why: {action['why']}")
            if action.get("examples"):
                print(f"      Examples:")
                for ex in action["examples"]:
                    print(f"        • {ex}")
            if action.get("how"):
                print(f"      How:")
                for step in action["how"]:
                    print(f"        {step}")
    
    print("\n" + "="*80)
    print("💡 Remember: Your MSS system already implements most viral patterns!")
    print("   Focus on: Creating meta-content + increasing upload frequency")
    print("="*80 + "\n")


def save_report(insights: Dict[str, Any], filename: str = "channel_insights.json"):
    """
    Save insights to file
    """
    out_dir = Path("out") / "analytics"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = out_dir / filename
    report_path.write_text(json.dumps(insights, indent=2))
    
    print(f"\n💾 Report saved to: {report_path}")
    return report_path


def main():
    """
    Main entry point
    """
    print("🚀 YouTube Channel Optimizer")
    print("   Analyzing your channel for growth opportunities...\n")
    
    # Get insights
    insights = get_channel_insights()
    
    if insights.get("status") == "error":
        print(f"❌ Error: {insights.get('message')}")
        if insights.get("recommendations"):
            print("\n💡 Recommendations:")
            for rec in insights["recommendations"]:
                print(f"   {rec}")
        return
    
    # Print report
    print_insights_report(insights)
    
    # Save report
    report_path = save_report(insights)
    
    # Generate actionable topics
    print("\n📝 GENERATING PERSONALIZED TOPIC SUGGESTIONS...")
    print("   Use these topics for your next videos:\n")
    
    from scripts.make_video import openai_generate_topics
    
    try:
        topics = openai_generate_topics(
            brand="Many Sources Say",
            seed="",  # No seed, let it generate meta-content naturally
            include_meta_content=True
        )
        
        print("\n🎬 TOP 5 RECOMMENDED VIDEOS:")
        for i, topic in enumerate(topics, 1):
            print(f"\n   {i}. {topic.get('yt_title', topic.get('title', 'Unknown'))}")
            print(f"      Angle: {topic.get('angle', 'N/A')[:80]}")
            print(f"      Keywords: {', '.join(topic.get('keywords', [])[:5])}")
    except Exception as e:
        print(f"   Could not generate topics: {e}")
    
    print("\n✅ Analysis complete! Use the insights above to optimize your channel.")
    print(f"   📄 Full report: {report_path}")


if __name__ == "__main__":
    main()

