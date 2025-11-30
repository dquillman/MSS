"""
Trend Alerts and AI Content Calendar Module for MSS
Provides YouTube trend monitoring and intelligent content scheduling
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os
from google.cloud import firestore
from web import firebase_db

# YouTube trending topics data source (can be replaced with real API)
# For now, using mock data - integrate with YouTube Data API v3 later
MOCK_TRENDING_TOPICS = [
    {
        "topic": "AI Tools 2025",
        "views": "2.5M",
        "growth": "+125%",
        "niche": "technology",
        "difficulty": "medium",
        "keywords": ["AI", "automation", "ChatGPT", "productivity", "artificial intelligence"],
        "subtopics": ["Best AI Tools for Content Creation", "AI vs Human Workers", "Free AI Tools You Need"]
    },
    {
        "topic": "Side Hustles",
        "views": "1.8M",
        "growth": "+98%",
        "niche": "business",
        "difficulty": "low",
        "keywords": ["passive income", "make money online", "side business", "entrepreneur", "freelance"],
        "subtopics": ["Best Side Hustles for 2025", "How to Start with $0", "Side Hustles That Pay $1000/month"]
    },
    {
        "topic": "Travel Tips Europe",
        "views": "1.2M",
        "growth": "+76%",
        "niche": "travel",
        "difficulty": "medium",
        "keywords": ["Europe travel", "budget travel", "hidden gems", "backpacking", "travel guide"],
        "subtopics": ["Cheapest European Cities", "Europe Travel Mistakes", "Best Time to Visit Europe"]
    },
    {
        "topic": "Fitness Transformation",
        "views": "950K",
        "growth": "+65%",
        "niche": "health",
        "difficulty": "high",
        "keywords": ["weight loss", "gym routine", "fitness journey", "body transformation", "workout plan"],
        "subtopics": ["90-Day Transformation Challenge", "From Beginner to Athlete", "Home Workout Transformations"]
    },
    {
        "topic": "Cryptocurrency Updates",
        "views": "890K",
        "growth": "+54%",
        "niche": "finance",
        "difficulty": "high",
        "keywords": ["crypto", "Bitcoin", "blockchain", "investing", "cryptocurrency news"],
        "subtopics": ["Bitcoin Price Predictions 2025", "Best Crypto to Buy Now", "Crypto Regulation Changes"]
    },
    {
        "topic": "DIY Home Projects",
        "views": "780K",
        "growth": "+43%",
        "niche": "lifestyle",
        "difficulty": "low",
        "keywords": ["DIY", "home improvement", "crafts", "woodworking", "home decor"],
        "subtopics": ["Budget-Friendly Home Upgrades", "DIY Furniture Projects", "Easy Weekend DIY Projects"]
    },
    {
        "topic": "Gaming News",
        "views": "650K",
        "growth": "+38%",
        "niche": "gaming",
        "difficulty": "medium",
        "keywords": ["gaming", "video games", "esports", "game reviews", "new releases"],
        "subtopics": ["Upcoming Game Releases 2025", "Gaming Industry Trends", "Best Games of the Year"]
    },
    {
        "topic": "Productivity Hacks",
        "views": "580K",
        "growth": "+32%",
        "niche": "self-improvement",
        "difficulty": "low",
        "keywords": ["productivity", "time management", "efficiency", "work-life balance", "habits"],
        "subtopics": ["Morning Routines of Successful People", "Top Productivity Apps", "How to Focus Better"]
    },
]

class TrendCalendarManager:
    def __init__(self, db_path: str = None):
        # db_path is ignored for Firestore
        self.db = firebase_db.get_db()
        print(f"[TRENDS] Initialized with Firestore")

    def get_trending_topics(self, user_email: str, niche: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get trending topics from YouTube Trending API"""
        try:
            # Try to fetch real trending videos from YouTube
            trends = self._fetch_youtube_trending(user_email, niche)

            if trends:
                print(f"[TRENDS] Fetched {len(trends)} real trending topics from YouTube")
                return trends
            else:
                print("[TRENDS] YouTube API returned no results, using fallback mock data")
        except Exception as e:
            print(f"[TRENDS] Error fetching from YouTube API: {e}, using fallback mock data")

        # Fallback to mock data if YouTube API fails
        trends = MOCK_TRENDING_TOPICS.copy()

        # Filter by niche if specified
        if niche:
            trends = [t for t in trends if t['niche'] == niche.lower()]

        # Get user preferences
        doc = self.db.collection('user_preferences').document(user_email).get()
        preferred_niches = []
        
        if doc.exists:
            data = doc.to_dict()
            niches_str = data.get('preferred_niches')
            if niches_str:
                preferred_niches = [n.strip().lower() for n in niches_str.split(',')]

        if preferred_niches:
            # Prioritize preferred niches
            preferred = [t for t in trends if t['niche'] in preferred_niches]
            others = [t for t in trends if t['niche'] not in preferred_niches]
            trends = preferred + others

        # Sort by growth rate
        def extract_growth_percentage(trend):
            growth_str = trend.get('growth', '+0%')
            import re
            match = re.search(r'([+-]?\d+)', growth_str)
            return int(match.group(1)) if match else 0

        trends.sort(key=extract_growth_percentage, reverse=True)

        return trends

    def _fetch_youtube_trending(self, user_email: str, niche: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch trending videos from YouTube Data API v3 and generate topic themes"""
        try:
            # Import YouTube API
            from googleapiclient.discovery import build
            from google.oauth2.credentials import Credentials
            import os
            from openai import OpenAI

            # Get API key or credentials
            api_key = os.getenv('YOUTUBE_API_KEY')

            if not api_key:
                # Try to get user's YouTube credentials
                doc_id = f"{user_email}_youtube"
                doc = self.db.collection('platform_connections').document(doc_id).get()
                
                creds_data = None
                if doc.exists:
                    data = doc.to_dict()
                    if data.get('status') == 'active':
                        creds_data = data.get('credentials')

                if not creds_data:
                    print("[TRENDS] No YouTube API key or credentials found")
                    return []

                # Use user's OAuth credentials
                credentials = Credentials(
                    token=creds_data.get('token'),
                    refresh_token=creds_data.get('refresh_token'),
                    token_uri=creds_data.get('token_uri'),
                    client_id=creds_data.get('client_id'),
                    client_secret=creds_data.get('client_secret')
                )
                youtube = build('youtube', 'v3', credentials=credentials)
            else:
                # Use API key
                youtube = build('youtube', 'v3', developerKey=api_key)

            # Target categories we WANT - AI, science, technology, world issues, health, government
            # YouTube category IDs: https://developers.google.com/youtube/v3/docs/videoCategories/list
            target_categories = [
                '28',  # Science & Technology (includes AI, tech innovation, research)
                '22',  # People & Blogs (often has world issues, political commentary, AI discussions)
                '26',  # Howto & Style (includes health, fitness, wellness)
            ]

            # Fetch trending videos from ALL categories (no filter), then filter by target
            all_trends = []

            # Fetch trending from each target category
            for category_id in target_categories:
                try:
                    request = youtube.videos().list(
                        part='snippet,statistics',
                        chart='mostPopular',
                        regionCode='US',
                        maxResults=20,
                        videoCategoryId=category_id
                    )
                    response = request.execute()

                    for video in response.get('items', []):
                        all_trends.append(video)

                except Exception as e:
                    print(f"[TRENDS] Error fetching category {category_id}: {e}")
                    continue

            response = {'items': all_trends}

            # Collect video data for AI analysis
            video_data = []
            for video in response.get('items', []):
                snippet = video['snippet']

                # Only include English videos
                default_language = snippet.get('defaultLanguage', '')
                default_audio_language = snippet.get('defaultAudioLanguage', '')
                title = snippet.get('title', '')

                # Skip non-English content
                if default_language and default_language.lower() not in ['en', 'en-us', 'en-gb']:
                    continue
                if default_audio_language and default_audio_language.lower() not in ['en', 'en-us', 'en-gb']:
                    continue

                # Simple heuristic: skip if title contains mostly non-ASCII characters
                if title:
                    ascii_chars = sum(1 for c in title if ord(c) < 128)
                    if len(title) > 0 and ascii_chars / len(title) < 0.7:
                        continue

                # Filter out late night talk shows
                channel_title = snippet.get('channelTitle', '').lower()
                title_lower = title.lower()

                late_night_shows = [
                    'tonight show', 'late show', 'late night', 'jimmy fallon', 'stephen colbert',
                    'jimmy kimmel', 'james corden', 'seth meyers', 'conan', 'daily show',
                    'last week tonight', 'john oliver', 'saturday night live', 'snl'
                ]

                # Skip if title or channel matches late night shows
                if any(show in title_lower or show in channel_title for show in late_night_shows):
                    continue

                stats = video['statistics']
                views = int(stats.get('viewCount', 0))

                # Map category ID to niche name
                category_id = snippet.get('categoryId', '0')
                category_to_niche = {
                    '25': 'news-politics',
                    '28': 'technology',
                    '27': 'education',
                    '22': 'world-issues',
                    '26': 'health',
                }
                niche_name = category_to_niche.get(category_id, 'general')

                # Collect video info for AI analysis
                video_data.append({
                    'title': title,
                    'description': snippet.get('description', '')[:200],  # First 200 chars
                    'views': views,
                    'category': niche_name
                })

            # If no videos collected, return empty
            if len(video_data) == 0:
                print(f"[TRENDS] No videos passed category filter")
                return []

            # Use AI to generate broader topic themes from trending videos
            print(f"[TRENDS] Analyzing {len(video_data)} videos to generate topic themes...")
            trends = self._generate_topic_themes(video_data)

            if trends and len(trends) > 0:
                print(f"[TRENDS] Successfully generated {len(trends)} trending topics")
                return trends

            # If AI generation failed, return empty
            print(f"[TRENDS] AI topic generation failed")
            return []

        except Exception as e:
            print(f"[TRENDS] Error in _fetch_youtube_trending: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _generate_topic_themes(self, video_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use AI to analyze trending videos and generate broader topic themes"""
        try:
            from openai import OpenAI
            from dotenv import load_dotenv
            load_dotenv()

            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                print("[TRENDS] OPENAI_API_KEY not found")
                return []

            client = OpenAI(api_key=api_key)

            # Prepare video summaries for AI
            video_summaries = []
            for v in video_data[:30]:  # Limit to 30 videos
                video_summaries.append(f"Title: {v['title']}\nCategory: {v['category']}\nViews: {v['views']:,}")

            prompt = f"""Analyze these trending YouTube videos and generate 8-12 broader TOPIC THEMES (not individual video topics).

Trending Videos:
{chr(10).join(video_summaries)}

Generate creative, engaging topic themes that:
1. Are broader than individual videos (e.g., "AI in Healthcare 2025" not specific video titles)
2. Focus on AI, technology, science, health, or world issues
3. Are suitable for creating educational/informative content
4. Include realistic view counts and growth estimates

Return ONLY valid JSON (no markdown, no code blocks) in this EXACT format:
[{{"topic":"Topic Name","views":"2.5M","growth":"+125%","niche":"technology","difficulty":"medium","keywords":["keyword1","keyword2","keyword3","keyword4","keyword5"],"subtopics":["Subtopic 1","Subtopic 2","Subtopic 3"]}}]"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )

            result_text = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if result_text.startswith('```'):
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]
                result_text = result_text.strip()

            trends = json.loads(result_text)
            return trends[:12]  # Limit to 12 topics

        except Exception as e:
            print(f"[TRENDS] Error generating topic themes: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _extract_keywords(self, title: str, description: str) -> List[str]:
        """Extract keywords from title and description"""
        import re

        # Combine title and description
        text = f"{title} {description}".lower()

        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
                     'this', 'that', 'these', 'those', 'how', 'what', 'when', 'where', 'why'}

        # Extract words (alphanumeric sequences)
        words = re.findall(r'\b[a-z0-9]+\b', text)

        # Filter and count
        from collections import Counter
        word_counts = Counter([w for w in words if w not in stop_words and len(w) > 3])

        # Return top keywords
        return [word for word, count in word_counts.most_common(15)]

    def _generate_subtopics(self, title: str, keywords: List[str]) -> List[str]:
        """Generate relevant subtopics based on title and keywords"""
        # Simple subtopic generation - in production, use AI
        subtopics = []

        # Common question patterns
        if keywords:
            subtopics.append(f"How to {keywords[0] if keywords else 'get started'}")
            if len(keywords) > 1:
                subtopics.append(f"{keywords[1].title()} vs {keywords[0].title()}")
            if len(keywords) > 2:
                subtopics.append(f"Best {keywords[2]} for beginners")

        # Add title-based subtopic
        if len(title) < 50:
            subtopics.insert(0, f"{title}: Complete Guide")

        return subtopics[:3]

    def save_trend_alert(self, user_email: str, trend: Dict[str, Any]) -> str:
        """Save a trend alert for a user"""
        data = {
            'user_email': user_email,
            'topic': trend['topic'],
            'views': trend.get('views', ''),
            'growth': trend.get('growth', ''),
            'niche': trend.get('niche', ''),
            'difficulty': trend.get('difficulty', ''),
            'detected_at': firestore.SERVER_TIMESTAMP,
            'dismissed': False
        }
        
        _, doc_ref = self.db.collection('trend_alerts').add(data)
        return doc_ref.id

    def get_user_alerts(self, user_email: str, include_dismissed: bool = False) -> List[Dict[str, Any]]:
        """Get all trend alerts for a user"""
        query = (self.db.collection('trend_alerts')
                 .where('user_email', '==', user_email))
                 
        if not include_dismissed:
            query = query.where('dismissed', '==', False)
            
        query = query.order_by('detected_at', direction=firestore.Query.DESCENDING).limit(20)
        
        docs = query.stream()
        alerts = []
        for doc in docs:
            a = doc.to_dict()
            a['id'] = doc.id
            alerts.append(a)
            
        return alerts

    def dismiss_alert(self, alert_id: str, user_email: str) -> bool:
        """Dismiss a trend alert"""
        try:
            doc_ref = self.db.collection('trend_alerts').document(alert_id)
            doc = doc_ref.get()
            
            if doc.exists and doc.to_dict().get('user_email') == user_email:
                doc_ref.update({'dismissed': True})
                return True
            return False
        except Exception as e:
            print(f"[TRENDS] Error dismissing alert: {e}")
            return False

    def generate_content_calendar(self, user_email: str, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Generate AI-powered content calendar suggestions"""
        # Get user preferences
        doc = self.db.collection('user_preferences').document(user_email).get()
        
        if doc.exists:
            data = doc.to_dict()
            frequency = data.get('posting_frequency', 3)
            days_str = data.get('best_posting_days', 'Monday,Wednesday,Friday')
            time_str = data.get('best_posting_time', '10:00')
        else:
            frequency, days_str, time_str = 3, 'Monday,Wednesday,Friday', '10:00'

        # Parse preferred posting days
        preferred_days = [d.strip() for d in days_str.split(',')]
        day_map = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
            'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
        }
        preferred_day_nums = [day_map[d] for d in preferred_days if d in day_map]

        # Generate suggestions
        suggestions = []
        today = datetime.now()
        trending = self.get_trending_topics(user_email)

        # Generate posts for next N days based on frequency
        posts_per_week = frequency
        current_date = today
        topic_index = 0

        for week in range(days_ahead // 7 + 1):
            posts_this_week = 0

            for day_offset in range(7):
                check_date = current_date + timedelta(days=week * 7 + day_offset)

                if (check_date - today).days >= days_ahead:
                    break

                # Check if this day is a preferred posting day
                if check_date.weekday() in preferred_day_nums and posts_this_week < posts_per_week:
                    if topic_index < len(trending):
                        topic = trending[topic_index]
                        suggestions.append({
                            'date': check_date.strftime('%Y-%m-%d'),
                            'time': time_str,
                            'title': f"Video about {topic['topic']}",
                            'topic': topic['topic'],
                            'niche': topic['niche'],
                            'reason': f"Trending with {topic['views']} views ({topic['growth']} growth)",
                            'difficulty': topic['difficulty'],
                            'ai_suggested': True
                        })
                        topic_index += 1
                        posts_this_week += 1

        return suggestions

    def save_calendar_entry(self, user_email: str, entry: Dict[str, Any]) -> str:
        """Save a content calendar entry"""
        data = {
            'user_email': user_email,
            'title': entry.get('title', ''),
            'description': entry.get('description', ''),
            'scheduled_date': entry.get('date', ''),
            'scheduled_time': entry.get('time', '10:00'),
            'topic': entry.get('topic', ''),
            'niche': entry.get('niche', ''),
            'status': entry.get('status', 'scheduled'),
            'ai_suggested': entry.get('ai_suggested', False),
            'created_at': firestore.SERVER_TIMESTAMP
        }
        
        _, doc_ref = self.db.collection('content_calendar').add(data)
        return doc_ref.id

    def get_calendar_entries(self, user_email: str, start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get calendar entries for a user"""
        query = (self.db.collection('content_calendar')
                 .where('user_email', '==', user_email))

        if start_date:
            query = query.where('scheduled_date', '>=', start_date)

        if end_date:
            query = query.where('scheduled_date', '<=', end_date)

        # Note: Firestore requires composite index for multiple fields + ordering
        # For now, we'll sort in memory if needed, or rely on simple queries
        # query = query.order_by('scheduled_date').order_by('scheduled_time')
        
        docs = query.stream()
        entries = []
        for doc in docs:
            e = doc.to_dict()
            e['id'] = doc.id
            entries.append(e)
            
        # Sort in memory
        entries.sort(key=lambda x: (x.get('scheduled_date', ''), x.get('scheduled_time', '')))
        
        return entries

    def update_calendar_entry(self, entry_id: str, user_email: str, updates: Dict[str, Any]) -> bool:
        """Update a calendar entry"""
        try:
            doc_ref = self.db.collection('content_calendar').document(entry_id)
            doc = doc_ref.get()
            
            if not doc.exists or doc.to_dict().get('user_email') != user_email:
                return False
                
            allowed_fields = ['title', 'description', 'scheduled_date', 'scheduled_time', 'status']
            clean_updates = {k: v for k, v in updates.items() if k in allowed_fields}
            
            if not clean_updates:
                return False
                
            doc_ref.update(clean_updates)
            return True
        except Exception as e:
            print(f"[TRENDS] Error updating entry: {e}")
            return False

    def delete_calendar_entry(self, entry_id: str, user_email: str) -> bool:
        """Delete a calendar entry"""
        try:
            doc_ref = self.db.collection('content_calendar').document(entry_id)
            doc = doc_ref.get()
            
            if not doc.exists or doc.to_dict().get('user_email') != user_email:
                return False
                
            doc_ref.delete()
            return True
        except Exception as e:
            if doc.exists:
                return doc.to_dict()
            else:
                # Return defaults
                return {
                    'user_email': user_email,
                    'preferred_niches': '',
                    'posting_frequency': 3,
                    'best_posting_days': 'Monday,Wednesday,Friday',
                    'best_posting_time': '10:00'
                }
        except Exception as e:
            print(f"[TRENDS] Error getting preferences: {e}")
            return {
                'user_email': user_email,
                'preferred_niches': '',
                'posting_frequency': 3,
                'best_posting_days': 'Monday,Wednesday,Friday',
                'best_posting_time': '10:00'
            }
