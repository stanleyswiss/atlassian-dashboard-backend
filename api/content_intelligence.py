from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List
import logging
from datetime import datetime

from services.content_intelligence import ContentIntelligenceService
from api.settings import get_openai_api_key

router = APIRouter(prefix="/api/intelligence", tags=["content-intelligence"])
logger = logging.getLogger(__name__)

@router.get("/forum-summary/{forum}")
async def get_forum_summary(
    forum: str, 
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze")
) -> Dict[str, Any]:
    """
    Get AI-powered summary for a specific forum
    """
    valid_forums = ["jira", "confluence", "jsm", "rovo", "announcements"]
    
    if forum not in valid_forums:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid forum. Must be one of: {valid_forums}"
        )
    
    try:
        api_key = get_openai_api_key()
        intelligence_service = ContentIntelligenceService(api_key)
        
        summary = await intelligence_service.generate_forum_summary(forum, days)
        
        return {
            "success": True,
            "data": summary
        }
        
    except Exception as e:
        logger.error(f"Error generating forum summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cross-forum-insights")
async def get_cross_forum_insights(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze")
) -> Dict[str, Any]:
    """
    Get AI-powered insights across all forums
    """
    try:
        api_key = get_openai_api_key()
        intelligence_service = ContentIntelligenceService(api_key)
        
        insights = await intelligence_service.generate_cross_forum_insights(days)
        
        return {
            "success": True,
            "data": insights
        }
        
    except Exception as e:
        logger.error(f"Error generating cross-forum insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trending-issues")
async def get_trending_issues(
    days: int = Query(3, ge=1, le=14, description="Number of days to analyze")
) -> Dict[str, Any]:
    """
    Get trending issues across all forums
    """
    try:
        api_key = get_openai_api_key()
        intelligence_service = ContentIntelligenceService(api_key)
        
        trending = await intelligence_service.get_trending_issues(days)
        
        return {
            "success": True,
            "data": {
                "trending_issues": trending,
                "analysis_period": f"Last {days} days",
                "generated_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting trending issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/community-pulse")
async def get_community_pulse() -> Dict[str, Any]:
    """
    Get overall community health and activity pulse
    """
    try:
        api_key = get_openai_api_key()
        intelligence_service = ContentIntelligenceService(api_key)
        
        # Get data for multiple time periods
        weekly_insights = await intelligence_service.generate_cross_forum_insights(7)
        trending_issues = await intelligence_service.get_trending_issues(3)
        
        # Generate forum summaries
        forums = ["jira", "confluence", "jsm"]  # Focus on working forums
        forum_health = {}
        
        for forum in forums:
            summary = await intelligence_service.generate_forum_summary(forum, 7)
            forum_health[forum] = {
                "activity_level": "high" if summary.get("post_count", 0) > 5 else "moderate",
                "sentiment": summary.get("sentiment_trend", "neutral"),
                "key_focus": summary.get("key_topics", [])[:3]
            }
        
        return {
            "success": True,
            "data": {
                "overall_health": "active",  # Could be calculated from sentiment trends
                "weekly_insights": weekly_insights,
                "trending_issues": trending_issues,
                "forum_health": forum_health,
                "generated_at": datetime.now().isoformat(),
                "summary": "Community showing active engagement across all forums with mixed sentiment due to recent platform changes"
            }
        }
        
    except Exception as e:
        logger.error(f"Error generating community pulse: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/topic-evolution/{topic}")
async def get_topic_evolution(
    topic: str,
    days: int = Query(14, ge=7, le=60, description="Number of days to analyze")
) -> Dict[str, Any]:
    """
    Track how a specific topic is evolving across forums
    """
    try:
        api_key = get_openai_api_key()
        intelligence_service = ContentIntelligenceService(api_key)
        
        # This would analyze how a topic (e.g., "rovo", "v9 upgrade", "api") 
        # is being discussed across different forums over time
        
        # For now, return mock evolution data
        evolution_data = {
            "topic": topic,
            "time_period": f"Last {days} days",
            "forums_discussing": ["jira", "confluence", "jsm"],
            "sentiment_evolution": {
                "week_1": "neutral",
                "week_2": "negative",
                "current": "mixed"
            },
            "volume_trend": "increasing",
            "key_developments": [
                f"Initial {topic} questions focused on basic setup",
                f"Week 2: Users reporting {topic} integration issues",
                f"Current: Community sharing {topic} workarounds and solutions"
            ],
            "related_topics": ["api integration", "authentication", "configuration"]
        }
        
        return {
            "success": True,
            "data": evolution_data
        }
        
    except Exception as e:
        logger.error(f"Error analyzing topic evolution: {e}")
        raise HTTPException(status_code=500, detail=str(e))