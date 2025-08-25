from typing import List, Dict, Optional, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from collections import Counter, defaultdict
import logging
import asyncio

from database import PostOperations, AnalyticsOperations, TrendOperations
from database import PostDB, AnalyticsDB, TrendDB
from models import PostCreate, PostCategory, SentimentLabel, ResolutionStatus
from .scraper import AtlassianScraper
from .ai_analyzer import AIAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataProcessor:
    """
    Processes scraped data, performs AI analysis, and stores results in database
    Handles data aggregation, trend calculation, and analytics generation
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.post_ops = PostOperations()
        self.analytics_ops = AnalyticsOperations()
        self.trend_ops = TrendOperations()
        
    async def process_scraped_data(
        self, 
        scraped_data: Dict[str, List[Dict]], 
        analyze_with_ai: bool = True
    ) -> Dict[str, any]:
        """Process scraped data through AI analysis and store in database"""
        logger.info(f"📊 Processing scraped data from {len(scraped_data)} categories")
        
        # Flatten all posts
        all_posts = []
        for category, posts in scraped_data.items():
            for post in posts:
                post['category'] = category
                all_posts.append(post)
                
        logger.info(f"📝 Total posts to process: {len(all_posts)}")
        
        if not all_posts:
            return {'status': 'no_data', 'processed_posts': 0}
        
        # AI Analysis (optional)
        analyzed_data = None
        if analyze_with_ai:
            try:
                analyzer = AIAnalyzer()
                analyzed_data = await analyzer.analyze_posts_complete(all_posts)
                all_posts = analyzed_data['analyzed_posts']
                logger.info("✅ AI analysis completed")
            except Exception as e:
                logger.error(f"❌ AI analysis failed: {e}")
                analyze_with_ai = False
        
        # Store posts in database
        stored_posts = []
        duplicate_count = 0
        
        for post_data in all_posts:
            try:
                # Convert to PostCreate model
                post_create = self._convert_to_post_create(post_data)
                
                # Check for duplicates by URL
                existing = self.db.query(PostDB).filter(PostDB.url == str(post_create.url)).first()
                if existing:
                    duplicate_count += 1
                    logger.debug(f"⏭️ Skipping duplicate: {post_create.title[:50]}...")
                    continue
                
                # Store in database
                db_post = self.post_ops.create_post(self.db, post_create)
                stored_posts.append(db_post)
                
            except Exception as e:
                logger.error(f"❌ Error storing post: {e}")
                continue
        
        logger.info(f"✅ Stored {len(stored_posts)} new posts (skipped {duplicate_count} duplicates)")
        
        # Generate analytics for today
        today = date.today()
        analytics_data = await self._generate_daily_analytics(today, analyzed_data)
        
        # Update trends
        if analyzed_data and analyzed_data.get('trending_topics'):
            await self._update_trending_topics(analyzed_data['trending_topics'], today)
        
        return {
            'status': 'success',
            'processed_posts': len(stored_posts),
            'duplicate_posts': duplicate_count,
            'total_posts': len(all_posts),
            'ai_analysis_enabled': analyze_with_ai,
            'analytics_generated': analytics_data is not None,
            'timestamp': datetime.now()
        }
        
    def _convert_to_post_create(self, post_data: Dict) -> PostCreate:
        """Convert scraped post data to PostCreate model"""
        # Ensure excerpt is within length limit
        excerpt = post_data.get('excerpt', post_data.get('content', '')[:497])
        if len(excerpt) > 497:
            excerpt = excerpt[:497] + "..."
        
        # Extract thread data info
        thread_data = post_data.get('thread_data', {})
        has_accepted_solution = thread_data.get('has_accepted_solution', False) if thread_data else False
        total_replies = thread_data.get('total_replies', 0) if thread_data else 0
        
        post_create = PostCreate(
            title=post_data.get('title', 'No title'),
            content=post_data.get('content', 'No content'),
            html_content=post_data.get('html_content'),  # Include HTML content
            author=post_data.get('author', 'Anonymous'),
            category=PostCategory(post_data.get('category', 'jira')),
            url=post_data.get('url', 'https://example.com'),
            excerpt=excerpt,
            sentiment_score=post_data.get('sentiment_score'),
            sentiment_label=SentimentLabel(post_data.get('sentiment_label')) if post_data.get('sentiment_label') else None
        )
        
        # Add thread data attributes
        post_create.thread_data = thread_data
        post_create.has_accepted_solution = has_accepted_solution
        post_create.total_replies = total_replies
        
        # Set resolution status based on solution detection
        if has_accepted_solution:
            post_create.resolution_status = ResolutionStatus.resolved
        elif total_replies > 0:
            post_create.resolution_status = ResolutionStatus.in_progress
        else:
            post_create.resolution_status = ResolutionStatus.unanswered
        
        return post_create
        
    async def _generate_daily_analytics(self, target_date: date, analyzed_data: Optional[Dict] = None) -> Optional[AnalyticsDB]:
        """Generate daily analytics summary"""
        try:
            # Get posts for the target date
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
            
            daily_posts = self.post_ops.get_posts_by_date_range(
                self.db, start_datetime, end_datetime
            )
            
            if not daily_posts:
                logger.info(f"📊 No posts found for {target_date}")
                return None
                
            # Calculate metrics
            total_posts = len(daily_posts)
            unique_authors = len(set(post.author for post in daily_posts))
            
            # Sentiment breakdown
            sentiment_counts = Counter(post.sentiment_label for post in daily_posts if post.sentiment_label)
            sentiment_breakdown = {
                'positive': sentiment_counts.get('positive', 0),
                'negative': sentiment_counts.get('negative', 0),
                'neutral': sentiment_counts.get('neutral', 0)
            }
            
            # Average sentiment
            sentiment_scores = [post.sentiment_score for post in daily_posts if post.sentiment_score is not None]
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
            
            # Most active category
            category_counts = Counter(post.category for post in daily_posts)
            most_active_category = category_counts.most_common(1)[0][0] if category_counts else 'jira'
            
            # Top topics from analyzed data or extract from posts
            top_topics = []
            if analyzed_data and analyzed_data.get('trending_topics'):
                top_topics = [topic['topic'] for topic in analyzed_data['trending_topics'][:10]]
            else:
                # Simple topic extraction from titles
                all_titles = ' '.join(post.title.lower() for post in daily_posts)
                common_words = ['bug', 'error', 'workflow', 'permission', 'api', 'integration', 'plugin', 'performance']
                top_topics = [word for word in common_words if word in all_titles][:5]
            
            # Create or update analytics
            analytics_data = {
                'total_posts': total_posts,
                'total_authors': unique_authors,
                'sentiment_breakdown': sentiment_breakdown,
                'top_topics': top_topics,
                'most_active_category': most_active_category,
                'average_sentiment': avg_sentiment
            }
            
            # Check if analytics already exist for this date
            existing_analytics = self.analytics_ops.get_analytics_by_date(self.db, target_date)
            
            if existing_analytics:
                # Update existing
                db_analytics = self.analytics_ops.update_analytics(self.db, target_date, analytics_data)
                logger.info(f"📊 Updated analytics for {target_date}")
            else:
                # Create new
                db_analytics = self.analytics_ops.create_daily_analytics(self.db, target_date, analytics_data)
                logger.info(f"📊 Created analytics for {target_date}")
            
            return db_analytics
            
        except Exception as e:
            logger.error(f"❌ Error generating analytics for {target_date}: {e}")
            return None
            
    async def _update_trending_topics(self, trending_topics: List[Dict], target_date: date):
        """Update trending topics in database"""
        try:
            for topic_data in trending_topics:
                topic = topic_data.get('topic', '')
                if not topic:
                    continue
                    
                # Calculate sentiment average from the topic data
                sentiment_map = {'positive': 0.5, 'negative': -0.5, 'neutral': 0.0}
                sentiment_avg = sentiment_map.get(topic_data.get('sentiment', 'neutral'), 0.0)
                
                trend_data = {
                    'count': topic_data.get('frequency', 1),
                    'sentiment_average': sentiment_avg,
                    'trending_score': topic_data.get('trend_score', 0.0) / 100.0,  # Normalize to 0-1
                    'categories': [topic_data.get('category', 'general')],
                    'last_seen': datetime.now()
                }
                
                # Try to update existing trend or create new
                existing_trend = self.db.query(TrendDB).filter(
                    TrendDB.topic == topic,
                    TrendDB.date == target_date
                ).first()
                
                if existing_trend:
                    self.trend_ops.update_trend(self.db, topic, target_date, trend_data)
                else:
                    self.trend_ops.create_trend(self.db, topic, target_date, trend_data)
                    
            logger.info(f"📈 Updated {len(trending_topics)} trending topics for {target_date}")
            
        except Exception as e:
            logger.error(f"❌ Error updating trending topics: {e}")
            
    async def collect_and_process_data(
        self, 
        max_posts_per_category: int = 20,
        categories: Optional[List[str]] = None,
        analyze_with_ai: bool = True
    ) -> Dict[str, any]:
        """Complete data collection and processing pipeline"""
        logger.info("🚀 Starting complete data collection and processing pipeline")
        
        try:
            # Step 1: Scrape data
            logger.info("🕷️ Step 1: Scraping Atlassian Community")
            
            async with AtlassianScraper() as scraper:
                if categories:
                    scraped_data = {}
                    for category in categories:
                        scraped_data[category] = await scraper.scrape_category(category, max_posts_per_category)
                else:
                    scraped_data = await scraper.scrape_all_categories(max_posts_per_category)
            
            # Step 2: Process and analyze
            logger.info("🤖 Step 2: Processing and analyzing data")
            result = await self.process_scraped_data(scraped_data, analyze_with_ai)
            
            # Step 3: Generate summary
            total_scraped = sum(len(posts) for posts in scraped_data.values())
            
            logger.info(f"✅ Pipeline complete!")
            logger.info(f"   📊 Scraped: {total_scraped} posts")
            logger.info(f"   💾 Stored: {result['processed_posts']} new posts")
            logger.info(f"   🤖 AI Analysis: {'✅' if analyze_with_ai else '❌'}")
            
            result.update({
                'scraped_posts': total_scraped,
                'pipeline_status': 'success'
            })
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'pipeline_status': 'failed',
                'timestamp': datetime.now()
            }
    
    def calculate_community_health_score(self) -> float:
        """Calculate overall community health score (0-100)"""
        try:
            # Get recent posts (last 7 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            recent_posts = self.post_ops.get_posts_by_date_range(self.db, start_date, end_date)
            
            if not recent_posts:
                return 50.0  # Neutral score if no data
            
            # Factors for health score
            factors = {}
            
            # 1. Activity level (30% weight)
            posts_per_day = len(recent_posts) / 7
            activity_score = min(100, posts_per_day * 10)  # 10 posts/day = 100%
            factors['activity'] = activity_score * 0.3
            
            # 2. Sentiment ratio (40% weight)
            sentiments = [post.sentiment_score for post in recent_posts if post.sentiment_score is not None]
            if sentiments:
                avg_sentiment = sum(sentiments) / len(sentiments)
                sentiment_score = ((avg_sentiment + 1) / 2) * 100  # Convert -1,1 to 0,100
                factors['sentiment'] = sentiment_score * 0.4
            else:
                factors['sentiment'] = 50.0 * 0.4
            
            # 3. Response diversity (20% weight) - number of unique authors
            unique_authors = len(set(post.author for post in recent_posts))
            diversity_score = min(100, unique_authors * 5)  # 20 authors = 100%
            factors['diversity'] = diversity_score * 0.2
            
            # 4. Content quality (10% weight) - posts with longer content
            avg_content_length = sum(len(post.content) for post in recent_posts) / len(recent_posts)
            quality_score = min(100, avg_content_length / 10)  # 1000 chars = 100%
            factors['quality'] = quality_score * 0.1
            
            total_score = sum(factors.values())
            
            logger.info(f"🏥 Community health score: {total_score:.1f}")
            logger.info(f"   📊 Factors: {factors}")
            
            return round(total_score, 1)
            
        except Exception as e:
            logger.error(f"❌ Error calculating community health: {e}")
            return 50.0

# Helper function for easy usage
async def collect_community_data(
    db: Session, 
    max_posts_per_category: int = 20, 
    analyze_with_ai: bool = True
) -> Dict[str, any]:
    """Convenience function to collect and process community data"""
    processor = DataProcessor(db)
    return await processor.collect_and_process_data(max_posts_per_category, None, analyze_with_ai)