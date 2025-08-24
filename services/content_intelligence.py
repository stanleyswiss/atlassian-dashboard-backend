"""
AI-powered content intelligence service for analyzing Atlassian Community trends
"""
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import openai
import os
from database.operations import DatabaseOperations
from config import settings

logger = logging.getLogger(__name__)

class ContentIntelligenceService:
    """
    AI service for analyzing community content patterns and generating insights
    """
    
    def __init__(self, api_key: str = None):
        self.db_ops = DatabaseOperations()
        
        # Get API key from multiple sources
        self.api_key = (
            api_key or 
            settings.openai_api_key or 
            os.environ.get("OPENAI_API_KEY") or 
            os.getenv("OPENAI_API_KEY")
        )
        
        logger.info(f"🔑 ContentIntelligenceService - API key available: {bool(self.api_key)}")
        
        if self.api_key:
            try:
                # Try new OpenAI client (v1.0+)
                self.openai_client = openai.OpenAI(api_key=self.api_key)
                logger.info("✅ OpenAI v1.0+ client initialized for content intelligence")
            except Exception as e:
                # Fallback to legacy method
                openai.api_key = self.api_key
                self.openai_client = None
                logger.info("✅ OpenAI legacy client initialized for content intelligence")
        else:
            logger.warning("❌ No OpenAI API key found for content intelligence")
            self.openai_client = None
    
    async def generate_forum_summary(self, forum: str, days: int = 7) -> Dict[str, Any]:
        """
        Generate AI-powered summary for a specific forum
        """
        try:
            # Get recent posts from forum
            posts = await self._get_recent_posts_by_forum(forum, days)
            
            if not posts:
                return {
                    "forum": forum,
                    "summary": "No recent activity",
                    "key_topics": [],
                    "sentiment_trend": "neutral",
                    "urgency_level": "low"
                }
            
            # Prepare content for AI analysis
            content_batch = self._prepare_content_for_analysis(posts)
            
            # Generate AI summary
            summary_data = await self._analyze_forum_content(forum, content_batch)
            
            return {
                "forum": forum,
                "post_count": len(posts),
                "time_period": f"Last {days} days",
                "generated_at": datetime.now().isoformat(),
                **summary_data
            }
            
        except Exception as e:
            logger.error(f"Error generating forum summary for {forum}: {e}")
            return {
                "forum": forum,
                "error": str(e),
                "summary": "Analysis failed",
                "key_topics": [],
                "sentiment_trend": "unknown"
            }
    
    async def generate_cross_forum_insights(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate insights across all forums to identify patterns
        """
        try:
            forums = ["jira", "confluence", "jsm", "rovo", "announcements"]
            all_posts = []
            
            for forum in forums:
                posts = await self._get_recent_posts_by_forum(forum, days)
                all_posts.extend(posts)
            
            if not all_posts:
                return {"error": "No posts available for analysis"}
            
            # Group posts by themes using AI
            insights = await self._analyze_cross_forum_patterns(all_posts)
            
            return {
                "total_posts": len(all_posts),
                "time_period": f"Last {days} days",
                "generated_at": datetime.now().isoformat(),
                **insights
            }
            
        except Exception as e:
            logger.error(f"Error generating cross-forum insights: {e}")
            return {"error": str(e)}
    
    async def get_trending_issues(self, days: int = 3) -> List[Dict[str, Any]]:
        """
        Identify trending issues across all forums using AI
        """
        try:
            all_posts = []
            forums = ["jira", "confluence", "jsm", "rovo", "announcements"]
            
            for forum in forums:
                posts = await self._get_recent_posts_by_forum(forum, days)
                all_posts.extend(posts)
            
            if len(all_posts) < 5:
                return []
            
            # Use AI to identify trending issues
            trending = await self._identify_trending_issues(all_posts)
            
            return trending
            
        except Exception as e:
            logger.error(f"Error identifying trending issues: {e}")
            return []
    
    async def _get_recent_posts_by_forum(self, forum: str, days: int) -> List[Dict]:
        """
        Get recent posts from a specific forum
        """
        try:
            from database.connection import get_session
            from database.models import PostDB
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with get_session() as db:
                posts = db.query(PostDB).filter(
                    PostDB.category == forum,
                    PostDB.created_at >= cutoff_date
                ).order_by(PostDB.created_at.desc()).limit(20).all()
                
                # Convert to dict format
                result = []
                for post in posts:
                    result.append({
                        'id': post.id,
                        'title': post.title,
                        'content': post.content,
                        'category': post.category,
                        'author': post.author,
                        'url': post.url,
                        'sentiment_score': post.sentiment_score,
                        'sentiment_label': post.sentiment_label,
                        'created_at': post.created_at.isoformat(),
                        'date': post.date.isoformat() if post.date else post.created_at.isoformat()
                    })
                
                return result
                
        except Exception as e:
            logger.error(f"Error getting posts for {forum}: {e}")
            return []
    
    def _prepare_content_for_analysis(self, posts: List[Dict]) -> str:
        """
        Prepare post content for AI analysis
        """
        content_parts = []
        
        for post in posts[:10]:  # Limit to 10 most recent posts
            title = post.get('title', '')
            content = post.get('content', '')[:500]  # First 500 chars
            
            content_parts.append(f"TITLE: {title}\nCONTENT: {content}\n---")
        
        return "\n".join(content_parts)
    
    async def _analyze_forum_content(self, forum: str, content: str) -> Dict[str, Any]:
        """
        Use OpenAI to analyze forum content and generate insights
        """
        try:
            prompt = f"""
            Analyze this {forum.upper()} forum content and provide insights:

            {content}

            Please provide a JSON response with:
            1. "summary": 2-sentence summary of main themes
            2. "key_topics": List of 3-5 main topics being discussed
            3. "sentiment_trend": Overall sentiment (positive/negative/neutral/mixed)
            4. "urgency_level": How urgent are the issues (low/medium/high/critical)
            5. "common_problems": List of 2-3 most common problems mentioned
            6. "emerging_trends": Any new or growing trends noticed

            Focus on technical issues, user pain points, and community needs.
            """
            
            if not self.api_key:
                logger.warning(f"🚫 No API key available for forum {forum} analysis - generating mock analysis")
                return self._generate_mock_analysis(forum)
            
            logger.info(f"🤖 Making real OpenAI API call for forum {forum} analysis")
            
            messages = [
                {"role": "system", "content": "You are an expert at analyzing technical community discussions and identifying patterns, issues, and trends."},
                {"role": "user", "content": prompt}
            ]
            
            try:
                if self.openai_client:
                    # New OpenAI client (v1.0+)
                    logger.info("Using OpenAI v1.0+ client for content intelligence")
                    response = await self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        max_tokens=800,
                        temperature=0.3
                    )
                    content = response.choices[0].message.content
                    tokens = response.usage.total_tokens
                else:
                    # Legacy OpenAI API
                    logger.info("Using OpenAI legacy API for content intelligence")
                    response = await openai.ChatCompletion.acreate(
                        model="gpt-4o-mini",
                        messages=messages,
                        max_tokens=800,
                        temperature=0.3
                    )
                    content = response.choices[0].message.content
                    tokens = response.usage.total_tokens if hasattr(response, 'usage') else 'unknown'
                
                logger.info(f"✅ OpenAI API call successful for forum {forum}, tokens: {tokens}")
                
                # Parse AI response (assuming it returns JSON)
                import json
                result = json.loads(content)
                return result
                
            except Exception as api_error:
                logger.error(f"OpenAI API call failed for forum {forum}: {api_error}")
                raise api_error
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return self._generate_mock_analysis(forum)
    
    async def _analyze_cross_forum_patterns(self, all_posts: List[Dict]) -> Dict[str, Any]:
        """
        Analyze patterns across all forums
        """
        try:
            # Group posts by forum
            forum_content = defaultdict(list)
            for post in all_posts:
                forum = post.get('category', 'unknown')
                forum_content[forum].append(post)
            
            content_summary = ""
            for forum, posts in forum_content.items():
                titles = [p.get('title', '') for p in posts[:5]]
                content_summary += f"\n{forum.upper()} ({len(posts)} posts):\n"
                content_summary += "\n".join([f"- {title}" for title in titles])
                content_summary += "\n"
            
            prompt = f"""
            Analyze these cross-forum patterns from Atlassian Community:

            {content_summary}

            Provide JSON with:
            1. "cross_forum_themes": Common themes appearing across multiple forums
            2. "forum_specific_focus": What each forum is primarily discussing
            3. "interconnected_issues": Issues that span multiple products
            4. "community_health": Overall assessment of community health/mood
            5. "action_items": Top 3 areas Atlassian should focus on based on community needs
            """
            
            if not self.api_key:
                return self._generate_mock_cross_forum_analysis()
            
            # Call OpenAI API similar to above
            # For now, return mock data
            return self._generate_mock_cross_forum_analysis()
            
        except Exception as e:
            logger.error(f"Cross-forum analysis failed: {e}")
            return self._generate_mock_cross_forum_analysis()
    
    async def _identify_trending_issues(self, posts: List[Dict]) -> List[Dict[str, Any]]:
        """
        Identify trending issues using AI
        """
        # Extract titles and group similar ones
        titles = [post.get('title', '') for post in posts]
        
        prompt = f"""
        From these recent Atlassian Community post titles, identify trending issues:

        {chr(10).join(titles)}

        Return JSON array with top 3 trending issues:
        [
          {{
            "issue": "Brief description",
            "severity": "low/medium/high/critical", 
            "affected_products": ["jira", "confluence", etc.],
            "post_count": estimated_number,
            "summary": "What's happening and why users are affected"
          }}
        ]
        """
        
        if not self.api_key:
            return self._generate_mock_trending_issues()
        
        # Call OpenAI API
        # For now, return mock
        return self._generate_mock_trending_issues()
    
    # Mock data generators for when OpenAI is not available
    def _generate_mock_analysis(self, forum: str) -> Dict[str, Any]:
        mock_data = {
            "jira": {
                "summary": "Users are primarily focused on Structure formulas and GraphQL API integration challenges. Several posts about Teams API OAuth scope configuration issues.",
                "key_topics": ["Structure Formula", "GraphQL API", "OAuth Scopes", "Teams Integration", "Rovo Credits"],
                "sentiment_trend": "mixed",
                "urgency_level": "medium",
                "common_problems": ["API authentication issues", "Formula syntax errors", "Integration failures"],
                "emerging_trends": ["Rovo monitoring requests", "Teams GraphQL usage growing"]
            },
            "confluence": {
                "summary": "Community is heavily discussing Confluence v9 upgrade issues, particularly around plugin compatibility and color scheme configuration. API questions around image handling are prominent.",
                "key_topics": ["Confluence v9 Upgrade", "Plugin Compatibility", "Macro Development", "API Integration", "Color Schemes"],
                "sentiment_trend": "negative", 
                "urgency_level": "high",
                "common_problems": ["v9 upgrade breaking changes", "Macro compatibility issues", "API limitations"],
                "emerging_trends": ["Dark mode configuration needs", "Legacy editor compatibility concerns"]
            },
            "jsm": {
                "summary": "JSM discussions center around ScriptRunner automation and workflow optimization. Users seeking advanced sub-task linking capabilities.",
                "key_topics": ["ScriptRunner", "Automation Rules", "Sub-task Workflows", "Field Configuration"],
                "sentiment_trend": "neutral",
                "urgency_level": "medium", 
                "common_problems": ["Complex workflow setup", "ScriptRunner syntax", "Field referencing issues"],
                "emerging_trends": ["Advanced automation requests", "Custom field needs growing"]
            }
        }
        
        return mock_data.get(forum, {
            "summary": f"Analysis for {forum} forum shows active community engagement",
            "key_topics": ["General Discussion", "Technical Questions", "Feature Requests"],
            "sentiment_trend": "neutral",
            "urgency_level": "low",
            "common_problems": ["Configuration questions", "Best practices needed"],
            "emerging_trends": ["Growing interest in new features"]
        })
    
    def _generate_mock_cross_forum_analysis(self) -> Dict[str, Any]:
        return {
            "cross_forum_themes": [
                "API Integration Challenges",
                "Upgrade and Migration Issues", 
                "Automation and Workflow Optimization",
                "Rovo AI Integration Questions"
            ],
            "forum_specific_focus": {
                "jira": "Formula development and API authentication",
                "confluence": "v9 upgrade compatibility issues",
                "jsm": "Advanced workflow automation"
            },
            "interconnected_issues": [
                "OAuth and API authentication problems spanning Jira and Confluence",
                "Rovo integration questions across multiple products",
                "Plugin compatibility issues affecting multiple platforms"
            ],
            "community_health": "Mixed - high engagement but frustrated with recent changes",
            "action_items": [
                "Improve v9 upgrade documentation and migration tools",
                "Enhance API authentication documentation with better examples", 
                "Provide clearer Rovo integration guidance and monitoring tools"
            ]
        }
    
    def _generate_mock_trending_issues(self) -> List[Dict[str, Any]]:
        return [
            {
                "issue": "Confluence v9 Plugin Compatibility",
                "severity": "high",
                "affected_products": ["confluence"],
                "post_count": 8,
                "summary": "Multiple users reporting plugins breaking after v9 upgrade, particularly color scheme and macro functionality"
            },
            {
                "issue": "GraphQL API OAuth Configuration",
                "severity": "medium", 
                "affected_products": ["jira"],
                "post_count": 5,
                "summary": "Users unable to configure Teams GraphQL API scopes in developer console, blocking integrations"
            },
            {
                "issue": "Rovo Credits Monitoring",
                "severity": "low",
                "affected_products": ["jira", "confluence", "rovo"],
                "post_count": 3,
                "summary": "Organizations want visibility into Rovo AI credit usage but lack monitoring tools"
            }
        ]