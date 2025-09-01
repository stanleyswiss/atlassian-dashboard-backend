from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func, text
from .models import PostDB, AnalyticsDB, TrendDB, ReleaseNoteDB, CloudNewsDB
from .connection import get_session
from models import Post, PostCreate, PostUpdate

class PostOperations:
    @staticmethod
    def create_post(db: Session, post: PostCreate) -> PostDB:
        # Handle thread_data serialization
        import json
        thread_data_json = None
        if hasattr(post, 'thread_data') and post.thread_data:
            thread_data_json = json.dumps(post.thread_data)
        
        db_post = PostDB(
            title=post.title,
            content=post.content,
            html_content=post.html_content,
            author=post.author,
            category=post.category.value,
            url=str(post.url),
            excerpt=post.excerpt,
            date=datetime.now(),
            sentiment_score=post.sentiment_score,
            sentiment_label=post.sentiment_label.value if post.sentiment_label else None,
            thread_data=thread_data_json,
            has_accepted_solution=getattr(post, 'has_accepted_solution', False),
            total_replies=getattr(post, 'total_replies', 0)
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
    def get_recent_posts(db: Session, days: int = 7, limit: int = 100) -> List[PostDB]:
        """Get recent posts within specified days"""
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        return db.query(PostDB).filter(
            PostDB.created_at >= cutoff_date
        ).order_by(desc(PostDB.created_at)).limit(limit).all()
    
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
        import json
        
        db_analytics = AnalyticsDB(
            date=analytics_date,
            total_posts=data.get("total_posts", 0),
            total_authors=data.get("total_authors", 0),
            sentiment_breakdown=json.dumps(data.get("sentiment_breakdown", {})),
            top_topics=json.dumps(data.get("top_topics", [])),
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
        import json
        
        db_analytics = db.query(AnalyticsDB).filter(AnalyticsDB.date == analytics_date).first()
        if not db_analytics:
            return None
        
        for field, value in data.items():
            if hasattr(db_analytics, field):
                # Convert dict/list fields to JSON strings for PostgreSQL
                if field in ['sentiment_breakdown', 'top_topics'] and isinstance(value, (dict, list)):
                    setattr(db_analytics, field, json.dumps(value))
                else:
                    setattr(db_analytics, field, value)
        
        db.commit()
        db.refresh(db_analytics)
        return db_analytics

class TrendOperations:
    @staticmethod
    def create_trend(db: Session, topic: str, trend_date: date, data: Dict[str, Any]) -> TrendDB:
        import json
        
        db_trend = TrendDB(
            topic=topic,
            date=trend_date,
            count=data.get("count", 0),
            sentiment_average=data.get("sentiment_average", 0.0),
            trending_score=data.get("trending_score", 0.0),
            categories=json.dumps(data.get("categories", [])),
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
        import json
        
        db_trend = db.query(TrendDB).filter(
            and_(TrendDB.topic == topic, TrendDB.date == trend_date)
        ).first()
        
        if not db_trend:
            return None
        
        for field, value in data.items():
            if hasattr(db_trend, field):
                # Convert list fields to JSON strings for PostgreSQL
                if field == 'categories' and isinstance(value, list):
                    setattr(db_trend, field, json.dumps(value))
                else:
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
                    # Extract thread_data if present
                    thread_data = post_data.get('thread_data', {})
                    
                    # Update existing post
                    for field, value in post_data.items():
                        if hasattr(existing_post, field) and field != 'id' and field != 'thread_data':
                            setattr(existing_post, field, value)
                    
                    # Handle thread_data separately
                    if thread_data:
                        existing_post.has_accepted_solution = thread_data.get('has_accepted_solution', False)
                        existing_post.total_replies = thread_data.get('total_replies', 0)
                        
                        # Store thread_data as JSON
                        import json
                        existing_post.thread_data = json.dumps(thread_data)
                    
                    existing_post.updated_at = datetime.now()
                    db.commit()
                    db.refresh(existing_post)
                    return existing_post
                else:
                    # Extract thread_data if present
                    thread_data = post_data.get('thread_data', {})
                    
                    # Create new post
                    db_post = PostDB(
                        title=post_data.get('title', ''),
                        content=post_data.get('content', ''),
                        html_content=post_data.get('html_content'),
                        author=post_data.get('author', ''),
                        category=post_data.get('category', ''),
                        url=post_data.get('url', ''),
                        excerpt=post_data.get('excerpt', ''),
                        date=post_data.get('date', datetime.now()),
                        sentiment_score=post_data.get('sentiment_score'),
                        sentiment_label=post_data.get('sentiment_label'),
                        # Thread-related fields
                        has_accepted_solution=thread_data.get('has_accepted_solution', False) if thread_data else False,
                        total_replies=thread_data.get('total_replies', 0) if thread_data else 0
                    )
                    
                    # Store thread_data as JSON if present
                    if thread_data:
                        import json
                        db_post.thread_data = json.dumps(thread_data)
                    
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

class ReleaseNoteOperations:
    """Database operations for Release Notes"""
    
    @staticmethod
    def create_release_note(db: Session, release_data: Dict[str, Any]) -> ReleaseNoteDB:
        """Create a new release note entry"""
        import json
        
        db_release = ReleaseNoteDB(
            product_name=release_data['product_name'],
            product_type=release_data['product_type'],
            product_id=release_data.get('product_id'),
            version=release_data['version'],
            build_number=release_data.get('build_number'),
            release_date=release_data['release_date'],
            release_summary=release_data.get('release_summary'),
            release_notes=release_data.get('release_notes'),
            release_notes_url=release_data.get('release_notes_url'),
            download_url=release_data.get('download_url'),
            is_major_release=release_data.get('is_major_release', False),
            is_security_release=release_data.get('is_security_release', False)
        )
        
        db.add(db_release)
        db.commit()
        db.refresh(db_release)
        return db_release
    
    @staticmethod
    def get_release_notes(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        product_type: Optional[str] = None,
        product_name: Optional[str] = None,
        days_back: int = 7,
        major_releases_only: bool = False,
        security_releases_only: bool = False
    ) -> List[ReleaseNoteDB]:
        """Get release notes with filtering"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        query = db.query(ReleaseNoteDB).filter(ReleaseNoteDB.release_date >= cutoff_date)
        
        if product_type:
            query = query.filter(ReleaseNoteDB.product_type == product_type)
        
        if product_name:
            query = query.filter(ReleaseNoteDB.product_name.contains(product_name))
        
        if major_releases_only:
            query = query.filter(ReleaseNoteDB.is_major_release == True)
        
        if security_releases_only:
            query = query.filter(ReleaseNoteDB.is_security_release == True)
        
        return query.order_by(desc(ReleaseNoteDB.release_date)).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_release_note(db: Session, release_id: int) -> Optional[ReleaseNoteDB]:
        """Get a single release note by ID"""
        return db.query(ReleaseNoteDB).filter(ReleaseNoteDB.id == release_id).first()
    
    @staticmethod
    def update_release_note_ai_data(db: Session, release_id: int, ai_data: Dict[str, Any]) -> bool:
        """Update AI analysis data for a release note"""
        import json
        
        release = db.query(ReleaseNoteDB).filter(ReleaseNoteDB.id == release_id).first()
        if not release:
            return False
        
        release.ai_summary = ai_data.get('ai_summary')
        release.ai_key_changes = json.dumps(ai_data.get('ai_key_changes', [])) if ai_data.get('ai_key_changes') else None
        release.ai_impact_level = ai_data.get('ai_impact_level')
        release.ai_categories = json.dumps(ai_data.get('ai_categories', [])) if ai_data.get('ai_categories') else None
        
        db.commit()
        return True
    
    @staticmethod
    def get_or_create_release_note(db: Session, release_data: Dict[str, Any]) -> ReleaseNoteDB:
        """Get existing release note or create new one"""
        existing = db.query(ReleaseNoteDB).filter(
            and_(
                ReleaseNoteDB.product_name == release_data['product_name'],
                ReleaseNoteDB.version == release_data['version'],
                ReleaseNoteDB.product_type == release_data['product_type']
            )
        ).first()
        
        if existing:
            # Update existing with new data
            for key, value in release_data.items():
                if hasattr(existing, key) and key != 'id':
                    setattr(existing, key, value)
            existing.updated_at = datetime.now()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            return ReleaseNoteOperations.create_release_note(db, release_data)

class CloudNewsOperations:
    """Database operations for Cloud News"""
    
    @staticmethod
    def create_cloud_news(db: Session, news_data: Dict[str, Any]) -> CloudNewsDB:
        """Create a new cloud news entry"""
        db_news = CloudNewsDB(
            source_url=news_data['source_url'],
            blog_date=news_data['blog_date'],
            blog_title=news_data['blog_title'],
            feature_title=news_data['feature_title'],
            feature_content=news_data['feature_content'],
            feature_type=news_data['feature_type'],
            product_area=news_data.get('product_area')
        )
        
        db.add(db_news)
        db.commit()
        db.refresh(db_news)
        return db_news
    
    @staticmethod
    def get_cloud_news(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        feature_type: Optional[str] = None,
        product_area: Optional[str] = None,
        days_back: int = 7
    ) -> List[CloudNewsDB]:
        """Get cloud news with filtering"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        query = db.query(CloudNewsDB).filter(CloudNewsDB.blog_date >= cutoff_date)
        
        if feature_type:
            query = query.filter(CloudNewsDB.feature_type == feature_type)
        
        if product_area:
            query = query.filter(CloudNewsDB.product_area.contains(product_area))
        
        return query.order_by(desc(CloudNewsDB.blog_date)).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_cloud_news_item(db: Session, news_id: int) -> Optional[CloudNewsDB]:
        """Get a single cloud news item by ID"""
        return db.query(CloudNewsDB).filter(CloudNewsDB.id == news_id).first()
    
    @staticmethod
    def update_cloud_news_ai_data(db: Session, news_id: int, ai_data: Dict[str, Any]) -> bool:
        """Update AI analysis data for cloud news"""
        import json
        
        news = db.query(CloudNewsDB).filter(CloudNewsDB.id == news_id).first()
        if not news:
            return False
        
        news.ai_summary = ai_data.get('ai_summary')
        news.ai_impact_description = ai_data.get('ai_impact_description')
        news.ai_target_audience = ai_data.get('ai_target_audience')
        news.ai_tags = json.dumps(ai_data.get('ai_tags', [])) if ai_data.get('ai_tags') else None
        
        db.commit()
        return True
    
    @staticmethod
    def get_or_create_cloud_news(db: Session, news_data: Dict[str, Any]) -> CloudNewsDB:
        """Get existing cloud news or create new one"""
        existing = db.query(CloudNewsDB).filter(
            CloudNewsDB.source_url == news_data['source_url']
        ).first()
        
        if existing:
            # Update existing with new data
            for key, value in news_data.items():
                if hasattr(existing, key) and key != 'id':
                    setattr(existing, key, value)
            existing.updated_at = datetime.now()
            db.commit()
            db.refresh(existing)
            return existing
        else:
            return CloudNewsOperations.create_cloud_news(db, news_data)
    
    @staticmethod
    def get_cloud_news_stats(db: Session, days_back: int = 7) -> Dict[str, Any]:
        """Get statistics for cloud news"""
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        total_features = db.query(CloudNewsDB).filter(CloudNewsDB.blog_date >= cutoff_date).count()
        new_this_week = db.query(CloudNewsDB).filter(
            and_(CloudNewsDB.blog_date >= cutoff_date, CloudNewsDB.feature_type == "NEW_THIS_WEEK")
        ).count()
        coming_soon = db.query(CloudNewsDB).filter(
            and_(CloudNewsDB.blog_date >= cutoff_date, CloudNewsDB.feature_type == "COMING_SOON")
        ).count()
        
        # Product breakdown
        product_stats = db.query(
            CloudNewsDB.product_area,
            func.count(CloudNewsDB.id).label('count')
        ).filter(
            CloudNewsDB.blog_date >= cutoff_date
        ).group_by(CloudNewsDB.product_area).all()
        
        product_breakdown = {stat[0] or 'Unknown': stat[1] for stat in product_stats}
        
        # Recent updates
        recent = db.query(CloudNewsDB).filter(
            CloudNewsDB.blog_date >= cutoff_date
        ).order_by(desc(CloudNewsDB.blog_date)).limit(5).all()
        
        return {
            'total_features': total_features,
            'new_this_week': new_this_week,
            'coming_soon': coming_soon,
            'product_breakdown': product_breakdown,
            'recent_updates': recent
        }