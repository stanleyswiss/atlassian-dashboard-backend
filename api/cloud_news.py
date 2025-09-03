"""
Cloud News API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import json

from database import get_db, CloudNewsOperations
from models import (
    CloudNewsResponse, CloudNewsSummary, CloudNewsFilters, 
    CloudNewsStats, FeatureType, TargetAudience
)
from services.cloud_news_scraper import CloudNewsScraper

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cloud-news", tags=["cloud-news"])

def convert_db_news_to_response(news) -> CloudNewsResponse:
    """Convert database cloud news model to response model, parsing JSON fields"""
    
    def safe_json_parse(value, default):
        """Safely parse JSON string, return default on error"""
        if value is None:
            return default
        if not value:
            return default
        if not isinstance(value, str):
            return value if value is not None else default
        try:
            parsed = json.loads(value)
            return parsed if parsed is not None else default
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"JSON parse error for value '{value}': {e}")
            return default
    
    # Parse JSON fields safely
    ai_tags = safe_json_parse(news.ai_tags, [])
    
    # Create response model
    news_dict = {
        "id": news.id,
        "source_url": news.source_url,
        "blog_date": news.blog_date,
        "blog_title": news.blog_title,
        "feature_title": news.feature_title,
        "feature_content": news.feature_content,
        "feature_type": news.feature_type,
        "product_area": news.product_area,
        "ai_summary": news.ai_summary,
        "ai_impact_description": news.ai_impact_description,
        "ai_target_audience": news.ai_target_audience,
        "ai_tags": ai_tags,
        "created_at": news.created_at,
        "updated_at": news.updated_at,
    }
    
    return CloudNewsResponse(**news_dict)

@router.get("/", response_model=List[CloudNewsResponse])
async def get_cloud_news(
    skip: int = Query(0, ge=0, description="Number of news items to skip"),
    limit: int = Query(50, ge=1, le=200, description="Number of news items to return"),
    feature_type: Optional[FeatureType] = Query(None, description="Filter by feature type"),
    product_area: Optional[str] = Query(None, description="Filter by product area"),
    days_back: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    target_audience: Optional[TargetAudience] = Query(None, description="Filter by target audience"),
    db: Session = Depends(get_db)
):
    """Get cloud news with filtering and pagination"""
    try:
        logger.info(f"Getting cloud news: skip={skip}, limit={limit}, feature_type={feature_type}")
        
        news_items = CloudNewsOperations.get_cloud_news(
            db=db,
            skip=skip,
            limit=limit,
            feature_type=feature_type.value if feature_type else None,
            product_area=product_area,
            days_back=days_back
        )
        
        logger.info(f"Retrieved {len(news_items)} cloud news items from database")
        
        # Convert news items with error handling
        response_news = []
        for news in news_items:
            try:
                response_item = convert_db_news_to_response(news)
                
                # Apply target audience filter if specified
                if target_audience and response_item.ai_target_audience != target_audience:
                    continue
                    
                response_news.append(response_item)
            except Exception as conv_error:
                logger.error(f"Error converting news item {news.id}: {conv_error}")
                continue
        
        return response_news
        
    except Exception as e:
        logger.error(f"Error getting cloud news: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cloud news")

@router.get("/summary", response_model=List[CloudNewsSummary])
async def get_cloud_news_summary(
    days_back: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(20, ge=1, le=100, description="Number of news items to return"),
    feature_type: Optional[FeatureType] = Query(None, description="Filter by feature type"),
    db: Session = Depends(get_db)
):
    """Get summarized cloud news for dashboard display"""
    try:
        news_items = CloudNewsOperations.get_cloud_news(
            db=db,
            skip=0,
            limit=limit,
            feature_type=feature_type.value if feature_type else None,
            days_back=days_back
        )
        
        # Convert to summary format
        summaries = []
        for news in news_items:
            try:
                summary = CloudNewsSummary(
                    id=news.id,
                    feature_title=news.feature_title,
                    feature_type=news.feature_type,
                    product_area=news.product_area,
                    blog_date=news.blog_date,
                    ai_summary=news.ai_summary,
                    ai_target_audience=news.ai_target_audience
                )
                summaries.append(summary)
            except Exception as e:
                logger.error(f"Error converting news {news.id} to summary: {e}")
                continue
        
        return summaries
        
    except Exception as e:
        logger.error(f"Error getting cloud news summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cloud news summary")

@router.get("/{news_id}", response_model=CloudNewsResponse)
async def get_cloud_news_item(news_id: int, db: Session = Depends(get_db)):
    """Get a single cloud news item by ID"""
    try:
        news = CloudNewsOperations.get_cloud_news_item(db, news_id)
        if not news:
            raise HTTPException(status_code=404, detail="Cloud news item not found")
            
        return convert_db_news_to_response(news)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cloud news item {news_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cloud news item")

@router.post("/scrape")
async def trigger_cloud_news_scrape(
    background_tasks: BackgroundTasks,
    days_back: int = Query(30, ge=1, le=365, description="Number of days to look back for news")
):
    """Trigger cloud news scraping in the background"""
    try:
        async def run_scrape():
            try:
                scraper = CloudNewsScraper(days_to_look_back=days_back)
                result = await scraper.run_full_scrape()
                logger.info(f"Background cloud news scrape completed: {result}")
            except Exception as e:
                logger.error(f"Background cloud news scrape failed: {e}")
        
        background_tasks.add_task(run_scrape)
        
        return {
            "message": "Cloud news scraping started in background",
            "days_back": days_back,
            "status": "started"
        }
        
    except Exception as e:
        logger.error(f"Error starting cloud news scrape: {e}")
        raise HTTPException(status_code=500, detail="Failed to start cloud news scraping")

@router.get("/stats/overview", response_model=CloudNewsStats)
async def get_cloud_news_stats(
    days_back: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """Get cloud news statistics"""
    try:
        stats_data = CloudNewsOperations.get_cloud_news_stats(db, days_back)
        
        # Convert recent updates to summary format
        recent_summaries = []
        for news in stats_data['recent_updates']:
            try:
                summary = CloudNewsSummary(
                    id=news.id,
                    feature_title=news.feature_title,
                    feature_type=news.feature_type,
                    product_area=news.product_area,
                    blog_date=news.blog_date,
                    ai_summary=news.ai_summary,
                    ai_target_audience=news.ai_target_audience
                )
                recent_summaries.append(summary)
            except Exception as e:
                logger.error(f"Error converting recent news {news.id}: {e}")
                continue
        
        return CloudNewsStats(
            total_features=stats_data['total_features'],
            new_this_week=stats_data['new_this_week'],
            coming_soon=stats_data['coming_soon'],
            product_breakdown=stats_data['product_breakdown'],
            recent_updates=recent_summaries
        )
        
    except Exception as e:
        logger.error(f"Error getting cloud news stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cloud news statistics")

@router.get("/products/list")
async def get_available_product_areas(db: Session = Depends(get_db)):
    """Get list of product areas that have cloud news"""
    try:
        from database.models import CloudNewsDB
        from sqlalchemy import func, distinct
        
        # Get unique product areas with counts
        product_areas = db.query(
            CloudNewsDB.product_area,
            func.count(CloudNewsDB.id).label('feature_count')
        ).filter(
            CloudNewsDB.product_area.isnot(None)
        ).group_by(
            CloudNewsDB.product_area
        ).order_by(CloudNewsDB.product_area).all()
        
        return [
            {
                "name": area.product_area or 'Unknown',
                "feature_count": area.feature_count
            } for area in product_areas
        ]
        
    except Exception as e:
        logger.error(f"Error getting available product areas: {e}")
        raise HTTPException(status_code=500, detail="Failed to get available product areas")

@router.get("/features/by-type")
async def get_features_by_type(
    days_back: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """Get cloud news features grouped by type"""
    try:
        from database.models import CloudNewsDB
        from sqlalchemy import func, and_
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Get features by type
        new_this_week = CloudNewsOperations.get_cloud_news(
            db=db,
            skip=0,
            limit=50,
            feature_type="NEW_THIS_WEEK",
            days_back=days_back
        )
        
        coming_soon = CloudNewsOperations.get_cloud_news(
            db=db,
            skip=0,
            limit=50,
            feature_type="COMING_SOON",
            days_back=days_back
        )
        
        return {
            "new_this_week": [
                {
                    "id": item.id,
                    "feature_title": item.feature_title,
                    "product_area": item.product_area,
                    "blog_date": item.blog_date.isoformat(),
                    "ai_summary": item.ai_summary
                } for item in new_this_week
            ],
            "coming_soon": [
                {
                    "id": item.id,
                    "feature_title": item.feature_title,
                    "product_area": item.product_area,
                    "blog_date": item.blog_date.isoformat(),
                    "ai_summary": item.ai_summary
                } for item in coming_soon
            ],
            "days_back": days_back
        }
        
    except Exception as e:
        logger.error(f"Error getting features by type: {e}")
        raise HTTPException(status_code=500, detail="Failed to get features by type")

@router.post("/{news_id}/analyze")
async def analyze_cloud_news_item(
    news_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger AI analysis for a specific cloud news item"""
    try:
        news = CloudNewsOperations.get_cloud_news_item(db, news_id)
        if not news:
            raise HTTPException(status_code=404, detail="Cloud news item not found")
        
        async def run_analysis():
            try:
                from services.ai_analyzer import AIAnalyzer
                analyzer = AIAnalyzer()
                
                # Prepare news data for AI analysis
                news_data = {
                    'feature_title': news.feature_title,
                    'feature_content': news.feature_content,
                    'product_area': news.product_area or '',
                    'feature_type': news.feature_type
                }
                
                # Run AI analysis (implement this method in AIAnalyzer)
                # ai_result = await analyzer.analyze_cloud_news(news_data)
                
                # For now, just log that analysis would run
                logger.info(f"Would analyze cloud news {news_id}: {news.feature_title}")
                
            except Exception as e:
                logger.error(f"Error analyzing cloud news {news_id}: {e}")
        
        background_tasks.add_task(run_analysis)
        
        return {
            "message": f"AI analysis started for cloud news item {news_id}",
            "news": {
                "id": news.id,
                "feature_title": news.feature_title,
                "product_area": news.product_area
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting analysis for cloud news {news_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start cloud news analysis")

@router.get("/search/by-content")
async def search_cloud_news(
    query: str = Query(..., min_length=3, description="Search query (minimum 3 characters)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    feature_type: Optional[FeatureType] = Query(None, description="Filter by feature type"),
    product_area: Optional[str] = Query(None, description="Filter by product area"),
    db: Session = Depends(get_db)
):
    """Search cloud news by content"""
    try:
        from database.models import CloudNewsDB
        from sqlalchemy import or_, func
        
        # Search in feature title and content
        search_filter = or_(
            CloudNewsDB.feature_title.contains(query),
            CloudNewsDB.feature_content.contains(query)
        )
        
        query_obj = db.query(CloudNewsDB).filter(search_filter)
        
        # Apply additional filters
        if feature_type:
            query_obj = query_obj.filter(CloudNewsDB.feature_type == feature_type.value)
        
        if product_area:
            query_obj = query_obj.filter(CloudNewsDB.product_area.contains(product_area))
        
        news_items = query_obj.order_by(CloudNewsDB.blog_date.desc())\
                            .offset(skip)\
                            .limit(limit)\
                            .all()
        
        return [convert_db_news_to_response(news) for news in news_items]
        
    except Exception as e:
        logger.error(f"Error searching cloud news: {e}")
        raise HTTPException(status_code=500, detail="Failed to search cloud news")