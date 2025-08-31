import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import time

from services.scraper import AtlassianScraper
from services.ai_analyzer import AIAnalyzer
from services.data_processor import DataProcessor
from database.operations import DatabaseOperations

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskScheduler:
    def __init__(self):
        self.scraper = AtlassianScraper()
        self.ai_analyzer = None  # Initialize lazily when needed
        self.db_ops = DatabaseOperations()
        self.is_running = False
        self.last_scrape = None
        self.scrape_interval = 3 * 60 * 60  # 3 hours (as documented)
        self.analytics_interval = 60 * 60  # 1 hour
    
    def get_ai_analyzer(self):
        """Get AI analyzer with current API key from settings"""
        if self.ai_analyzer is None:
            try:
                from api.settings import get_openai_api_key, is_sentiment_analysis_enabled
                if is_sentiment_analysis_enabled():
                    api_key = get_openai_api_key()
                    if api_key and not api_key.startswith("*"):
                        self.ai_analyzer = AIAnalyzer(api_key=api_key)
                    else:
                        logger.warning("OpenAI API key not configured, sentiment analysis disabled")
                        return None
                else:
                    logger.info("Sentiment analysis disabled in settings")
                    return None
            except Exception as e:
                logger.error(f"Failed to initialize AI analyzer: {e}")
                return None
        return self.ai_analyzer
        
    async def start(self):
        """Start the background scheduler"""
        logger.info("🚀 Starting Task Scheduler...")
        self.is_running = True
        
        # Run initial data collection
        await self.run_full_collection()
        
        # Start background tasks
        await asyncio.gather(
            self.scraping_loop(),
            self.analytics_loop(),
            self.health_monitor_loop()
        )
    
    async def stop(self):
        """Stop the scheduler gracefully"""
        logger.info("🛑 Stopping Task Scheduler...")
        self.is_running = False
    
    async def scraping_loop(self):
        """Background loop for scraping new posts"""
        while self.is_running:
            try:
                logger.info("🕷️ Starting scheduled scrape...")
                await self.run_scraping_task()
                self.last_scrape = datetime.now()
                logger.info(f"✅ Scraping completed at {self.last_scrape}")
                
            except Exception as e:
                logger.error(f"❌ Scraping error: {e}")
            
            # Wait for next scrape interval
            await asyncio.sleep(self.scrape_interval)
    
    async def analytics_loop(self):
        """Background loop for generating analytics"""
        while self.is_running:
            try:
                logger.info("📊 Generating analytics...")
                await self.run_analytics_task()
                logger.info("✅ Analytics generation completed")
                
            except Exception as e:
                logger.error(f"❌ Analytics error: {e}")
            
            # Wait for next analytics interval
            await asyncio.sleep(self.analytics_interval)
    
    async def health_monitor_loop(self):
        """Background loop for monitoring system health"""
        while self.is_running:
            try:
                # Monitor system health every 5 minutes
                await asyncio.sleep(5 * 60)
                await self.check_system_health()
                
            except Exception as e:
                logger.error(f"❌ Health monitor error: {e}")
    
    async def run_full_collection(self):
        """Run complete data collection pipeline"""
        logger.info("🔄 Running full data collection pipeline...")
        
        # Step 1: Scrape new posts
        await self.run_scraping_task()
        
        # Step 2: Analyze sentiment for unanalyzed posts
        await self.run_sentiment_analysis()
        
        # Step 3: Generate comprehensive AI summaries for posts without them
        await self.run_comprehensive_ai_analysis()
        
        # Step 4: Generate analytics
        await self.run_analytics_task()
        
        logger.info("✅ Full data collection pipeline completed!")
    
    async def run_scraping_task(self):
        """Scrape posts from all forums"""
        stats = {
            'total_posts': 0,
            'new_posts': 0,
            'errors': 0,
            'forums': {}
        }
        
        try:
            # Scrape all forums
            async with self.scraper:
                scrape_results = await self.scraper.scrape_all_categories(max_posts_per_category=50, max_pages_per_category=3)
            
            for forum, posts in scrape_results.items():
                forum_stats = {'scraped': 0, 'new': 0, 'errors': 0}
                
                for post_data in posts:
                    try:
                        # Save to database
                        saved_post = await self.db_ops.create_or_update_post(post_data)
                        
                        if saved_post:
                            forum_stats['new'] += 1
                            stats['new_posts'] += 1
                        
                        forum_stats['scraped'] += 1
                        stats['total_posts'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error saving post: {e}")
                        forum_stats['errors'] += 1
                        stats['errors'] += 1
                
                stats['forums'][forum] = forum_stats
                logger.info(f"📝 {forum}: {forum_stats['scraped']} scraped, {forum_stats['new']} new")
        
        except Exception as e:
            logger.error(f"Scraping task failed: {e}")
            raise
        
        logger.info(f"📊 Scraping Summary: {stats['total_posts']} total, {stats['new_posts']} new, {stats['errors']} errors")
        return stats
    
    async def run_sentiment_analysis(self):
        """Run sentiment analysis on posts without sentiment scores"""
        logger.info("🧠 Running sentiment analysis...")
        
        try:
            # Get posts without sentiment analysis
            unanalyzed_posts = await self.db_ops.get_posts_without_sentiment()
            
            if not unanalyzed_posts:
                logger.info("✅ No posts need sentiment analysis")
                return
            
            logger.info(f"🧠 Analyzing sentiment for {len(unanalyzed_posts)} posts...")
            
            # Get AI analyzer with current settings
            ai_analyzer = self.get_ai_analyzer()
            if not ai_analyzer:
                logger.warning("AI analyzer not available, skipping sentiment analysis")
                return
            
            analyzed_count = 0
            for post in unanalyzed_posts:
                try:
                    # Analyze sentiment
                    sentiment_result = await ai_analyzer.analyze_sentiment(
                        f"{post.title or ''} {post.content or ''}"
                    )
                    
                    # Update post with sentiment
                    await self.db_ops.update_post_sentiment(
                        post.id,
                        sentiment_result.get('sentiment_score', 0.0),
                        sentiment_result.get('sentiment_label', 'neutral')
                    )
                    
                    analyzed_count += 1
                    
                    # Rate limiting to avoid API overload
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error analyzing post {post.id}: {e}")
                    continue
            
            logger.info(f"✅ Sentiment analysis completed for {analyzed_count} posts")
            
        except Exception as e:
            logger.error(f"Sentiment analysis task failed: {e}")
    
    async def run_comprehensive_ai_analysis(self):
        """Generate comprehensive AI summaries for posts without them"""
        logger.info("🤖 Running comprehensive AI analysis...")
        
        try:
            # Get posts without AI summaries (ai_summary is null)
            from database import get_session
            from database.models import PostDB
            
            with get_session() as db:
                posts_needing_analysis = db.query(PostDB).filter(
                    PostDB.ai_summary.is_(None)
                ).order_by(PostDB.created_at.desc()).limit(10).all()  # Process 10 at a time
                
                if not posts_needing_analysis:
                    logger.info("✅ No posts need comprehensive AI analysis")
                    return
                
                logger.info(f"🤖 Analyzing {len(posts_needing_analysis)} posts with comprehensive AI...")
                
                # Get AI analyzer
                ai_analyzer = self.get_ai_analyzer()
                if not ai_analyzer:
                    logger.warning("AI analyzer not available, skipping comprehensive analysis")
                    return
                
                analyzed_count = 0
                for post in posts_needing_analysis:
                    try:
                        # Convert to dict format for AI processing
                        post_dict = {
                            'id': post.id,
                            'title': post.title or '',
                            'content': post.content or '',
                            'author': post.author or '',
                            'category': post.category or '',
                            'url': str(post.url) if post.url else '',
                            'date': post.date.isoformat() if post.date else None,
                            'sentiment_score': post.sentiment_score,
                            'sentiment_label': post.sentiment_label
                        }
                        
                        # Generate comprehensive AI summary
                        summary_result = await ai_analyzer.summarize_post(
                            post.title or '', 
                            post.content or ''
                        )
                        
                        if summary_result:
                            # Update post with AI summary data
                            import json
                            post.ai_summary = summary_result.get('summary', '')
                            post.ai_category = summary_result.get('category', '')
                            post.ai_key_points = json.dumps(summary_result.get('key_points', []))
                            post.ai_action_required = summary_result.get('action_required', 'none')
                            post.ai_hashtags = json.dumps(summary_result.get('hashtags', []))
                            
                            analyzed_count += 1
                            logger.debug(f"Generated AI summary for post {post.id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to analyze post {post.id}: {e}")
                        continue
                
                # Commit all changes
                db.commit()
                logger.info(f"✅ Comprehensive AI analysis completed for {analyzed_count} posts")
                
        except Exception as e:
            logger.error(f"Comprehensive AI analysis task failed: {e}")
    
    async def run_analytics_task(self):
        """Generate daily analytics and trends"""
        logger.info("📊 Generating analytics...")
        
        try:
            # Generate daily analytics for today
            today = datetime.now().date()
            analytics = await self.data_processor.generate_daily_analytics(today)
            
            if analytics:
                logger.info(f"✅ Generated analytics for {today}")
            
            # Update trending topics
            await self.data_processor.update_trending_topics()
            logger.info("✅ Updated trending topics")
            
        except Exception as e:
            logger.error(f"Analytics task failed: {e}")
    
    async def check_system_health(self):
        """Check system health and log status"""
        try:
            # Check database connection
            db_healthy = await self.db_ops.health_check()
            
            # Check last scrape time
            scrape_healthy = True
            if self.last_scrape:
                time_since_scrape = datetime.now() - self.last_scrape
                scrape_healthy = time_since_scrape < timedelta(minutes=30)
            
            # Log health status
            if db_healthy and scrape_healthy:
                logger.info("💚 System health: All systems operational")
            else:
                logger.warning(f"⚠️ System health: DB={db_healthy}, Scrape={scrape_healthy}")
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        return {
            'is_running': self.is_running,
            'last_scrape': self.last_scrape.isoformat() if self.last_scrape else None,
            'scrape_interval_minutes': self.scrape_interval // 60,
            'analytics_interval_minutes': self.analytics_interval // 60
        }

# Global scheduler instance
scheduler = None

async def start_scheduler():
    """Start the global scheduler"""
    global scheduler
    if scheduler is None:
        scheduler = TaskScheduler()
    
    if not scheduler.is_running:
        await scheduler.start()

async def stop_scheduler():
    """Stop the global scheduler"""
    global scheduler
    if scheduler and scheduler.is_running:
        await scheduler.stop()

def get_scheduler_status():
    """Get scheduler status"""
    global scheduler
    if scheduler:
        return scheduler.get_status()
    return {'is_running': False}

# Manual trigger functions for API endpoints
async def trigger_scraping():
    """Manually trigger scraping"""
    global scheduler
    if not scheduler:
        scheduler = TaskScheduler()
    
    return await scheduler.run_scraping_task()

async def trigger_full_collection():
    """Manually trigger full collection pipeline"""
    global scheduler
    if not scheduler:
        scheduler = TaskScheduler()
    
    await scheduler.run_full_collection()
    return {"message": "Full collection pipeline completed"}

if __name__ == "__main__":
    # Run scheduler standalone for testing
    async def main():
        scheduler = TaskScheduler()
        await scheduler.start()
    
    asyncio.run(main())