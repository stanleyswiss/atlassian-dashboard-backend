from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
import logging
import json

from database import get_db, PostOperations, AnalyticsOperations, TrendOperations
from models import DashboardOverview, PostResponse, SentimentTrend, TopicTrend
from services import DataProcessor, collect_community_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

def convert_db_post_to_response(post) -> PostResponse:
    """Convert database post model to response model, parsing JSON fields"""
    
    def safe_json_parse(value, default):
        """Safely parse JSON string, return default on error"""
        if not value:
            return default
        if not isinstance(value, str):
            return value if value is not None else default
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return default
    
    # Parse JSON fields safely and quickly
    vision_analysis = safe_json_parse(post.vision_analysis, {})
    text_analysis = safe_json_parse(post.text_analysis, {})
    extracted_issues = safe_json_parse(post.extracted_issues, [])
    mentioned_products = safe_json_parse(post.mentioned_products, [])
    
    # Create response model with parsed JSON
    post_dict = {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "author": post.author,
        "category": post.category,
        "url": post.url,
        "excerpt": post.excerpt,
        "date": post.date,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
        "sentiment_score": post.sentiment_score,
        "sentiment_label": post.sentiment_label,
        "enhanced_category": post.enhanced_category,
        "has_screenshots": bool(post.has_screenshots) if post.has_screenshots is not None else False,
        "vision_analysis": vision_analysis,
        "text_analysis": text_analysis,
        "problem_severity": post.problem_severity,
        "resolution_status": post.resolution_status,
        "business_impact": post.business_impact,
        "business_value": post.business_value,
        "extracted_issues": extracted_issues,
        "mentioned_products": mentioned_products,
    }
    
    return PostResponse(**post_dict)

@router.get("/test")
async def test_endpoint(db: Session = Depends(get_db)):
    """Test endpoint to debug database connection"""
    try:
        posts = PostOperations.get_posts(db, limit=5)
        return {
            "status": "success",
            "posts_count": len(posts),
            "sample_post": posts[0].title if posts else "No posts found"
        }
    except Exception as e:
        logger.error(f"Test endpoint error: {e}")
        return {"status": "error", "error": str(e)}

@router.get("/overview")
async def get_dashboard_overview(db: Session = Depends(get_db)):
    """Get dashboard overview with key community metrics"""
    try:
        # Get all posts for simplicity (we'll use created_at instead of date field)
        all_posts = PostOperations.get_posts(db, limit=100)
        
        # Filter by last 24 hours and last week based on created_at
        now = datetime.now()
        today_start = now - timedelta(days=1)  # Last 24 hours
        week_start = now - timedelta(days=7)   # Last 7 days
        
        today_posts = [p for p in all_posts if p.created_at and p.created_at >= today_start]
        week_posts = [p for p in all_posts if p.created_at and p.created_at >= week_start]
        
        # Calculate basic health score
        total_posts_week = len(week_posts)
        posts_with_sentiment = len([p for p in week_posts if p.sentiment_score is not None])
        
        if total_posts_week > 0:
            sentiment_coverage = (posts_with_sentiment / total_posts_week) * 100
            activity_score = min(100, total_posts_week * 2)  # Cap at 100
            health_score = (sentiment_coverage + activity_score) / 2
        else:
            health_score = 50.0
        
        # Most active forum (category)
        if week_posts:
            from collections import Counter
            category_counts = Counter(p.category for p in week_posts)
            most_active_forum = category_counts.most_common(1)[0][0]
        else:
            most_active_forum = "jira"
        
        # Sentiment breakdown
        sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
        for post in week_posts:
            if post.sentiment_label:
                sentiment_counts[post.sentiment_label] += 1
        
        total_sentiment = sum(sentiment_counts.values())
        if total_sentiment > 0:
            sentiment_percentages = {
                k: round((v / total_sentiment) * 100, 1) for k, v in sentiment_counts.items()
            }
        else:
            sentiment_percentages = {'positive': 33.3, 'negative': 33.3, 'neutral': 33.3}
        
        # Simple activity change calculation
        activity_change = 15.5  # Mock positive growth for demo
        
        # Mock top issues for now
        top_issues = ["workflow permissions", "api integration", "performance issues", "automation rules", "user permissions"]
        
        return {
            "total_posts_today": len(today_posts),
            "total_posts_week": len(week_posts),
            "community_health_score": round(health_score, 1),
            "most_active_forum": most_active_forum,
            "sentiment_breakdown": sentiment_percentages,
            "recent_activity_change": activity_change,
            "top_issues": top_issues
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard overview: {e}")
        logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard overview: {str(e)}")

@router.get("/recent-posts", response_model=List[PostResponse])
async def get_recent_posts(
    limit: int = 10,
    category: str = None,
    db: Session = Depends(get_db)
):
    """Get recent posts with sentiment analysis"""
    try:
        posts = PostOperations.get_posts(
            db, 
            skip=0, 
            limit=limit,
            category=category
        )
        
        return [convert_db_post_to_response(post) for post in posts]
        
    except Exception as e:
        logger.error(f"Error getting recent posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent posts")

@router.get("/trending-topics", response_model=List[TopicTrend])
async def get_trending_topics(
    limit: int = 10,
    min_score: float = 0.0,
    db: Session = Depends(get_db)
):
    """Get trending topics and keywords"""
    try:
        # Try to get trends from database
        trends = TrendOperations.get_trending_topics(db, limit=limit, min_score=min_score)
        
        topic_trends = []
        for trend in trends:
            topic_trend = TopicTrend(
                topic=trend.topic,
                count=trend.count,
                sentiment_average=trend.sentiment_average,
                trending_score=trend.trending_score,
                last_seen=trend.last_seen
            )
            topic_trends.append(topic_trend)
        
        # If no trends found, return mock data
        if not topic_trends:
            logger.info("No trending topics found in database, returning mock data")
            mock_trends = [
                TopicTrend(
                    topic="workflow automation",
                    count=25,
                    sentiment_average=0.3,
                    trending_score=0.85,
                    last_seen=datetime.now()
                ),
                TopicTrend(
                    topic="user permissions",
                    count=18,
                    sentiment_average=-0.2,
                    trending_score=0.72,
                    last_seen=datetime.now()
                ),
                TopicTrend(
                    topic="API integration", 
                    count=15,
                    sentiment_average=0.1,
                    trending_score=0.68,
                    last_seen=datetime.now()
                ),
                TopicTrend(
                    topic="performance issues",
                    count=22,
                    sentiment_average=-0.4,
                    trending_score=0.65,
                    last_seen=datetime.now()
                ),
                TopicTrend(
                    topic="JSM automation",
                    count=12,
                    sentiment_average=0.2,
                    trending_score=0.58,
                    last_seen=datetime.now()
                ),
                TopicTrend(
                    topic="confluence templates",
                    count=8,
                    sentiment_average=0.5,
                    trending_score=0.45,
                    last_seen=datetime.now()
                ),
                TopicTrend(
                    topic="database connection",
                    count=14,
                    sentiment_average=-0.3,
                    trending_score=0.42,
                    last_seen=datetime.now()
                ),
                TopicTrend(
                    topic="Jira migration",
                    count=7,
                    sentiment_average=0.1,
                    trending_score=0.38,
                    last_seen=datetime.now()
                )
            ]
            
            # Apply filters
            filtered_trends = [
                trend for trend in mock_trends
                if trend.trending_score >= min_score
            ]
            
            return filtered_trends[:limit]
            
        return topic_trends
        
    except Exception as e:
        logger.error(f"Error getting trending topics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trending topics")

@router.get("/sentiment-timeline", response_model=List[SentimentTrend])
async def get_sentiment_timeline(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Get sentiment analysis over time"""
    try:
        # Get date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        # Get analytics for the date range
        analytics_list = AnalyticsOperations.get_analytics_range(db, start_date, end_date)
        analytics_by_date = {analytics.date: analytics for analytics in analytics_list}
        
        # Create sentiment trends for each day
        sentiment_trends = []
        current_date = start_date
        
        while current_date <= end_date:
            if current_date in analytics_by_date:
                analytics = analytics_by_date[current_date]
                breakdown = analytics.sentiment_breakdown
                
                sentiment_trend = SentimentTrend(
                    date=current_date,
                    positive_count=breakdown.get('positive', 0),
                    negative_count=breakdown.get('negative', 0),
                    neutral_count=breakdown.get('neutral', 0),
                    average_sentiment=analytics.average_sentiment
                )
            else:
                # No data for this date
                sentiment_trend = SentimentTrend(
                    date=current_date,
                    positive_count=0,
                    negative_count=0,
                    neutral_count=0,
                    average_sentiment=0.0
                )
                
            sentiment_trends.append(sentiment_trend)
            current_date += timedelta(days=1)
            
        return sentiment_trends
        
    except Exception as e:
        logger.error(f"Error getting sentiment timeline: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sentiment timeline")

@router.post("/refresh-data")
async def refresh_community_data(
    max_posts_per_category: int = 20,
    analyze_with_ai: bool = False,
    db: Session = Depends(get_db)
):
    """Trigger manual data collection and refresh"""
    try:
        logger.info(f"🔄 Manual data refresh requested (AI: {analyze_with_ai})")
        
        # Run data collection
        result = await collect_community_data(
            db, 
            max_posts_per_category=max_posts_per_category,
            analyze_with_ai=analyze_with_ai
        )
        
        return {
            "status": "success",
            "message": "Data refresh completed",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error refreshing data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh data: {str(e)}")

@router.get("/health-score")
async def get_community_health_score(db: Session = Depends(get_db)):
    """Get detailed community health score with breakdown"""
    try:
        processor = DataProcessor(db)
        health_score = processor.calculate_community_health_score()
        
        # Get additional health metrics
        today = date.today()
        week_start = today - timedelta(days=7)
        week_start_dt = datetime.combine(week_start, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        recent_posts = PostOperations.get_posts_by_date_range(db, week_start_dt, today_end)
        
        # Calculate factors
        activity_level = len(recent_posts) / 7  # posts per day
        unique_authors = len(set(post.author for post in recent_posts))
        
        sentiment_scores = [post.sentiment_score for post in recent_posts if post.sentiment_score is not None]
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        
        return {
            "overall_score": health_score,
            "factors": {
                "activity_level": round(activity_level, 1),
                "unique_authors": unique_authors,
                "average_sentiment": round(avg_sentiment, 2),
                "posts_this_week": len(recent_posts)
            },
            "recommendations": [
                "Monitor negative sentiment trends" if avg_sentiment < -0.2 else "Sentiment is healthy",
                "Encourage more community participation" if unique_authors < 10 else "Good author diversity",
                "Activity level is strong" if activity_level > 5 else "Consider promoting more engagement"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting health score: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health score")