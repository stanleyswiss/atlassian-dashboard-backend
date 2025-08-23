from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

from database import get_db, AnalyticsOperations, TrendOperations, PostOperations
from models import AnalyticsResponse, SentimentTrend, TopicTrend

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/daily/{target_date}")
async def get_daily_analytics(
    target_date: date,
    db: Session = Depends(get_db)
):
    """Get analytics for a specific date"""
    try:
        analytics = AnalyticsOperations.get_analytics_by_date(db, target_date)
        if not analytics:
            raise HTTPException(
                status_code=404, 
                detail=f"No analytics found for {target_date}"
            )
            
        return {
            "date": analytics.date,
            "total_posts": analytics.total_posts,
            "total_authors": analytics.total_authors,
            "sentiment_breakdown": analytics.sentiment_breakdown,
            "top_topics": analytics.top_topics,
            "most_active_category": analytics.most_active_category,
            "average_sentiment": analytics.average_sentiment,
            "created_at": analytics.created_at,
            "updated_at": analytics.updated_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting daily analytics for {target_date}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get daily analytics")

@router.get("/range")
async def get_analytics_range(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """Get analytics for a date range"""
    try:
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="Start date must be before or equal to end date"
            )
            
        if (end_date - start_date).days > 365:
            raise HTTPException(
                status_code=400,
                detail="Date range cannot exceed 365 days"
            )
        
        analytics_list = AnalyticsOperations.get_analytics_range(db, start_date, end_date)
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_days": len(analytics_list),
            "analytics": [
                {
                    "date": analytics.date,
                    "total_posts": analytics.total_posts,
                    "total_authors": analytics.total_authors,
                    "sentiment_breakdown": analytics.sentiment_breakdown,
                    "top_topics": analytics.top_topics,
                    "most_active_category": analytics.most_active_category,
                    "average_sentiment": analytics.average_sentiment
                }
                for analytics in analytics_list
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analytics range: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics range")

@router.get("/sentiment-trends")
async def get_sentiment_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Get sentiment trends over time"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        analytics_list = AnalyticsOperations.get_analytics_range(db, start_date, end_date)
        analytics_by_date = {analytics.date: analytics for analytics in analytics_list}
        
        sentiment_trends = []
        current_date = start_date
        
        while current_date <= end_date:
            if current_date in analytics_by_date:
                analytics = analytics_by_date[current_date]
                breakdown = analytics.sentiment_breakdown
                
                trend = SentimentTrend(
                    date=current_date,
                    positive_count=breakdown.get('positive', 0),
                    negative_count=breakdown.get('negative', 0),
                    neutral_count=breakdown.get('neutral', 0),
                    average_sentiment=analytics.average_sentiment
                )
            else:
                trend = SentimentTrend(
                    date=current_date,
                    positive_count=0,
                    negative_count=0,
                    neutral_count=0,
                    average_sentiment=0.0
                )
                
            sentiment_trends.append(trend)
            current_date += timedelta(days=1)
            
        return {
            "period": f"{days} days",
            "start_date": start_date,
            "end_date": end_date,
            "trends": sentiment_trends
        }
        
    except Exception as e:
        logger.error(f"Error getting sentiment trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sentiment trends")

@router.get("/topic-trends")
async def get_topic_trends(
    limit: int = Query(20, ge=1, le=100, description="Number of topics to return"),
    min_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum trending score"),
    db: Session = Depends(get_db)
):
    """Get trending topics with scores"""
    try:
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
            
        return {
            "total_topics": len(topic_trends),
            "min_score_filter": min_score,
            "topics": topic_trends
        }
        
    except Exception as e:
        logger.error(f"Error getting topic trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get topic trends")

@router.get("/topic/{topic_name}/history")
async def get_topic_history(
    topic_name: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Get historical data for a specific topic"""
    try:
        history = TrendOperations.get_topic_trend(db, topic_name, days)
        
        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"No history found for topic '{topic_name}'"
            )
        
        return {
            "topic": topic_name,
            "period_days": days,
            "data_points": len(history),
            "history": [
                {
                    "date": trend.date,
                    "count": trend.count,
                    "sentiment_average": trend.sentiment_average,
                    "trending_score": trend.trending_score,
                    "categories": trend.categories,
                    "last_seen": trend.last_seen
                }
                for trend in history
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting topic history for '{topic_name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to get topic history")

@router.get("/forum-comparison")
async def get_forum_comparison(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Compare activity across different forums/categories"""
    try:
        # Get date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get posts for the period
        posts = PostOperations.get_posts_by_date_range(db, start_date, end_date)
        
        # Group by category
        from collections import defaultdict
        category_stats = defaultdict(lambda: {
            'post_count': 0,
            'author_count': 0,
            'authors': set(),
            'sentiment_scores': [],
            'topics': []
        })
        
        for post in posts:
            stats = category_stats[post.category]
            stats['post_count'] += 1
            stats['authors'].add(post.author)
            
            if post.sentiment_score is not None:
                stats['sentiment_scores'].append(post.sentiment_score)
        
        # Calculate final stats
        forum_comparison = {}
        for category, stats in category_stats.items():
            author_count = len(stats['authors'])
            avg_sentiment = (
                sum(stats['sentiment_scores']) / len(stats['sentiment_scores'])
                if stats['sentiment_scores'] else 0.0
            )
            
            forum_comparison[category] = {
                'post_count': stats['post_count'],
                'author_count': author_count,
                'average_sentiment': round(avg_sentiment, 2),
                'posts_per_author': round(stats['post_count'] / author_count if author_count > 0 else 0, 1)
            }
        
        # Sort by post count
        sorted_forums = sorted(
            forum_comparison.items(),
            key=lambda x: x[1]['post_count'],
            reverse=True
        )
        
        return {
            "period_days": days,
            "total_forums": len(forum_comparison),
            "comparison": dict(sorted_forums),
            "summary": {
                "most_active": sorted_forums[0][0] if sorted_forums else None,
                "total_posts": sum(stats['post_count'] for stats in forum_comparison.values()),
                "total_unique_authors": len(set().union(*[stats['authors'] for stats in category_stats.values()]))
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting forum comparison: {e}")
        raise HTTPException(status_code=500, detail="Failed to get forum comparison")

@router.get("/summary")
async def get_analytics_summary(
    days: int = Query(7, ge=1, le=90, description="Number of days to summarize"),
    db: Session = Depends(get_db)
):
    """Get comprehensive analytics summary"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        
        # Get analytics for the period
        analytics_list = AnalyticsOperations.get_analytics_range(db, start_date, end_date)
        
        if not analytics_list:
            return {
                "period": f"Last {days} days",
                "message": "No analytics data available for this period"
            }
        
        # Calculate summary statistics
        total_posts = sum(a.total_posts for a in analytics_list)
        total_authors = sum(a.total_authors for a in analytics_list)
        avg_sentiment = sum(a.average_sentiment for a in analytics_list) / len(analytics_list)
        
        # Sentiment aggregation
        sentiment_totals = {'positive': 0, 'negative': 0, 'neutral': 0}
        for analytics in analytics_list:
            for sentiment, count in analytics.sentiment_breakdown.items():
                sentiment_totals[sentiment] += count
        
        # Most common topics
        all_topics = []
        for analytics in analytics_list:
            all_topics.extend(analytics.top_topics)
        
        from collections import Counter
        topic_counts = Counter(all_topics)
        top_topics = [topic for topic, count in topic_counts.most_common(10)]
        
        # Most active categories
        category_counts = Counter(a.most_active_category for a in analytics_list)
        
        return {
            "period": f"Last {days} days",
            "start_date": start_date,
            "end_date": end_date,
            "summary": {
                "total_posts": total_posts,
                "total_authors": total_authors,
                "average_sentiment": round(avg_sentiment, 2),
                "sentiment_breakdown": sentiment_totals,
                "top_topics": top_topics,
                "category_activity": dict(category_counts.most_common())
            },
            "daily_average": {
                "posts_per_day": round(total_posts / days, 1),
                "authors_per_day": round(total_authors / days, 1)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics summary")

@router.post("/generate-daily/{target_date}")
async def generate_daily_analytics(
    target_date: date,
    db: Session = Depends(get_db)
):
    """Manually trigger daily analytics generation for a specific date"""
    try:
        from services.data_processor import DataProcessor
        
        processor = DataProcessor(db)
        analytics = await processor._generate_daily_analytics(target_date)
        
        if analytics:
            return {
                "message": f"Analytics generated successfully for {target_date}",
                "analytics_id": analytics.id,
                "total_posts": analytics.total_posts,
                "total_authors": analytics.total_authors
            }
        else:
            return {
                "message": f"No posts found for {target_date}, analytics not generated"
            }
            
    except Exception as e:
        logger.error(f"Error generating daily analytics for {target_date}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate daily analytics")