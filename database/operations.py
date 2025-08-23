from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func, text
from .models import PostDB, AnalyticsDB, TrendDB
from .connection import get_session
from models import Post, PostCreate, PostUpdate

class PostOperations:
    @staticmethod
    def create_post(db: Session, post: PostCreate) -> PostDB:
        db_post = PostDB(
            title=post.title,
            content=post.content,
            author=post.author,
            category=post.category.value,
            url=str(post.url),
            excerpt=post.excerpt,
            date=datetime.now(),
            sentiment_score=post.sentiment_score,
            sentiment_label=post.sentiment_label.value if post.sentiment_label else None
        )
        db.add(db_post)
        db.commit()
        db.refresh(db_post)
        return db_post
    
    @staticmethod
    def get_post(db: Session, post_id: int) -> Optional[PostDB]:
        return db.query(PostDB).filter(PostDB.id == post_id).first()
    
    @staticmethod
    def get_posts(
        db: Session, 
        skip: int = 0, 
        limit: int = 100,
        category: Optional[str] = None,
        author: Optional[str] = None,
        sentiment: Optional[str] = None
    ) -> List[PostDB]:
        query = db.query(PostDB)
        
        if category:
            query = query.filter(PostDB.category == category)
        if author:
            query = query.filter(PostDB.author.contains(author))
        if sentiment:
            query = query.filter(PostDB.sentiment_label == sentiment)
            
        return query.order_by(desc(PostDB.date)).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_post(db: Session, post_id: int, post_update: PostUpdate) -> Optional[PostDB]:
        db_post = db.query(PostDB).filter(PostDB.id == post_id).first()
        if not db_post:
            return None
            
        update_data = post_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if field == "url" and value:
                value = str(value)
            elif field == "sentiment_label" and value:
                value = value.value
            elif field == "category" and value:
                value = value.value
            setattr(db_post, field, value)
        
        db.commit()
        db.refresh(db_post)
        return db_post
    
    @staticmethod
    def delete_post(db: Session, post_id: int) -> bool:
        db_post = db.query(PostDB).filter(PostDB.id == post_id).first()
        if not db_post:
            return False
        
        db.delete(db_post)
        db.commit()
        return True
    
    @staticmethod
    def get_posts_by_date_range(
        db: Session, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[PostDB]:
        return db.query(PostDB).filter(
            and_(PostDB.date >= start_date, PostDB.date <= end_date)
        ).order_by(desc(PostDB.date)).all()

class AnalyticsOperations:
    @staticmethod
    def create_daily_analytics(db: Session, analytics_date: date, data: Dict[str, Any]) -> AnalyticsDB:
        db_analytics = AnalyticsDB(
            date=analytics_date,
            total_posts=data.get("total_posts", 0),
            total_authors=data.get("total_authors", 0),
            sentiment_breakdown=data.get("sentiment_breakdown", {}),
            top_topics=data.get("top_topics", []),
            most_active_category=data.get("most_active_category", ""),
            average_sentiment=data.get("average_sentiment", 0.0)
        )
        db.add(db_analytics)
        db.commit()
        db.refresh(db_analytics)
        return db_analytics
    
    @staticmethod
    def get_analytics_by_date(db: Session, analytics_date: date) -> Optional[AnalyticsDB]:
        return db.query(AnalyticsDB).filter(AnalyticsDB.date == analytics_date).first()
    
    @staticmethod
    def get_analytics_range(
        db: Session, 
        start_date: date, 
        end_date: date
    ) -> List[AnalyticsDB]:
        return db.query(AnalyticsDB).filter(
            and_(AnalyticsDB.date >= start_date, AnalyticsDB.date <= end_date)
        ).order_by(desc(AnalyticsDB.date)).all()
    
    @staticmethod
    def update_analytics(
        db: Session, 
        analytics_date: date, 
        data: Dict[str, Any]
    ) -> Optional[AnalyticsDB]:
        db_analytics = db.query(AnalyticsDB).filter(AnalyticsDB.date == analytics_date).first()
        if not db_analytics:
            return None
        
        for field, value in data.items():
            if hasattr(db_analytics, field):
                setattr(db_analytics, field, value)
        
        db.commit()
        db.refresh(db_analytics)
        return db_analytics

class TrendOperations:
    @staticmethod
    def create_trend(db: Session, topic: str, trend_date: date, data: Dict[str, Any]) -> TrendDB:
        db_trend = TrendDB(
            topic=topic,
            date=trend_date,
            count=data.get("count", 0),
            sentiment_average=data.get("sentiment_average", 0.0),
            trending_score=data.get("trending_score", 0.0),
            categories=data.get("categories", []),
            last_seen=data.get("last_seen", datetime.now())
        )
        db.add(db_trend)
        db.commit()
        db.refresh(db_trend)
        return db_trend
    
    @staticmethod
    def get_trending_topics(
        db: Session, 
        limit: int = 10,
        min_score: float = 0.0
    ) -> List[TrendDB]:
        return db.query(TrendDB).filter(
            TrendDB.trending_score >= min_score
        ).order_by(desc(TrendDB.trending_score)).limit(limit).all()
    
    @staticmethod
    def get_topic_trend(db: Session, topic: str, days: int = 7) -> List[TrendDB]:
        start_date = date.today() - timedelta(days=days)
        return db.query(TrendDB).filter(
            and_(TrendDB.topic == topic, TrendDB.date >= start_date)
        ).order_by(desc(TrendDB.date)).all()
    
    @staticmethod
    def update_trend(
        db: Session, 
        topic: str, 
        trend_date: date, 
        data: Dict[str, Any]
    ) -> Optional[TrendDB]:
        db_trend = db.query(TrendDB).filter(
            and_(TrendDB.topic == topic, TrendDB.date == trend_date)
        ).first()
        
        if not db_trend:
            return None
        
        for field, value in data.items():
            if hasattr(db_trend, field):
                setattr(db_trend, field, value)
        
        db.commit()
        db.refresh(db_trend)
        return db_trend


class DatabaseOperations:
    """
    Unified database operations class for scheduler and background tasks
    """
    
    async def create_or_update_post(self, post_data: Dict[str, Any]) -> Optional[PostDB]:
        """Create or update a post from scraped data"""
        try:
            with get_session() as db:
                # Check if post already exists by URL
                existing_post = db.query(PostDB).filter(PostDB.url == post_data.get('url')).first()
                
                if existing_post:
                    # Update existing post
                    for field, value in post_data.items():
                        if hasattr(existing_post, field) and field != 'id':
                            setattr(existing_post, field, value)
                    
                    existing_post.updated_at = datetime.now()
                    db.commit()
                    db.refresh(existing_post)
                    return existing_post
                else:
                    # Create new post
                    db_post = PostDB(
                        title=post_data.get('title', ''),
                        content=post_data.get('content', ''),
                        author=post_data.get('author', ''),
                        category=post_data.get('category', ''),
                        url=post_data.get('url', ''),
                        excerpt=post_data.get('excerpt', ''),
                        date=post_data.get('date', datetime.now()),
                        sentiment_score=post_data.get('sentiment_score'),
                        sentiment_label=post_data.get('sentiment_label')
                    )
                    db.add(db_post)
                    db.commit()
                    db.refresh(db_post)
                    return db_post
                    
        except Exception as e:
            print(f"Error creating/updating post: {e}")
            return None
    
    async def get_posts_without_sentiment(self) -> List[PostDB]:
        """Get posts that don't have sentiment analysis"""
        try:
            with get_session() as db:
                return db.query(PostDB).filter(PostDB.sentiment_score.is_(None)).limit(50).all()
        except Exception as e:
            print(f"Error getting posts without sentiment: {e}")
            return []
    
    async def update_post_sentiment(self, post_id: int, score: float, label: str) -> bool:
        """Update post sentiment score and label"""
        try:
            with get_session() as db:
                post = db.query(PostDB).filter(PostDB.id == post_id).first()
                if post:
                    post.sentiment_score = score
                    post.sentiment_label = label
                    post.updated_at = datetime.now()
                    db.commit()
                    return True
                return False
        except Exception as e:
            print(f"Error updating post sentiment: {e}")
            return False
    
    async def get_posts_count(self) -> int:
        """Get total number of posts"""
        try:
            with get_session() as db:
                return db.query(PostDB).count()
        except Exception as e:
            print(f"Error getting posts count: {e}")
            return 0
    
    async def get_recent_posts_count(self, hours: int = 24) -> int:
        """Get count of posts from last N hours"""
        try:
            with get_session() as db:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                return db.query(PostDB).filter(PostDB.created_at >= cutoff_time).count()
        except Exception as e:
            print(f"Error getting recent posts count: {e}")
            return 0
    
    async def delete_all_posts(self) -> int:
        """Delete all posts (for reset functionality)"""
        try:
            with get_session() as db:
                count = db.query(PostDB).count()
                db.query(PostDB).delete()
                db.commit()
                return count
        except Exception as e:
            print(f"Error deleting posts: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            with get_session() as db:
                db.execute(text("SELECT 1"))
                return True
        except Exception as e:
            print(f"Database health check failed: {e}")
            return False