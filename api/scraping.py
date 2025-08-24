from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Dict, Any
import logging
from datetime import datetime

from scheduler import trigger_scraping, trigger_full_collection, get_scheduler_status
from services.scraper import AtlassianScraper
from database.operations import DatabaseOperations
from demo_data_generator import DemoDataGenerator

router = APIRouter(prefix="/api/scraping", tags=["scraping"])
logger = logging.getLogger(__name__)

@router.post("/trigger")
async def trigger_manual_scraping(background_tasks: BackgroundTasks):
    """
    Manually trigger scraping of all Atlassian forums
    """
    try:
        # Run scraping in background
        background_tasks.add_task(trigger_scraping)
        
        return {
            "message": "Scraping initiated",
            "status": "running",
            "note": "Check /api/scraping/status for progress"
        }
    except Exception as e:
        logger.error(f"Failed to trigger scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trigger-all")
async def trigger_all_forums_scraping(background_tasks: BackgroundTasks):
    """
    Trigger immediate scraping of all forums with progress tracking
    """
    try:
        async def scrape_all_task():
            """Background task to scrape all forums"""
            try:
                logger.info("🚀 Starting background scraping of all forums...")
                scraper = AtlassianScraper()
                db_ops = DatabaseOperations()
                
                total_posts_scraped = 0
                forums_scraped = []
                
                async with scraper:
                    # Scrape each forum
                    for forum_name in scraper.BASE_URLS.keys():
                        try:
                            logger.info(f"🔍 Scraping {forum_name}...")
                            posts = await scraper.scrape_category(forum_name, max_posts=20, max_pages=2)
                            
                            # Store posts in database
                            for post in posts:
                                try:
                                    await db_ops.create_or_update_post({
                                        'title': post.get('title', 'No title'),
                                        'content': post.get('content', 'No content'),
                                        'author': post.get('author', 'Anonymous'),
                                        'category': forum_name,
                                        'url': post.get('url', ''),
                                        'excerpt': post.get('excerpt', ''),
                                        'date': post.get('date', datetime.now())
                                    })
                                except Exception as save_error:
                                    logger.error(f"Error saving post: {save_error}")
                                    continue
                            
                            total_posts_scraped += len(posts)
                            if len(posts) > 0:
                                forums_scraped.append(forum_name)
                            
                            logger.info(f"✅ Scraped {len(posts)} posts from {forum_name}")
                            
                        except Exception as forum_error:
                            logger.error(f"❌ Error scraping {forum_name}: {forum_error}")
                            continue
                
                logger.info(f"🎉 Background scraping completed! Total: {total_posts_scraped} posts from {len(forums_scraped)} forums")
                
            except Exception as e:
                logger.error(f"❌ Background scraping task failed: {e}")
        
        # Start background task immediately
        background_tasks.add_task(scrape_all_task)
        
        # Return immediately with success
        return {
            "success": True,
            "message": "Scraping initiated successfully",
            "posts_scraped": "In progress...",
            "forums": list(AtlassianScraper().BASE_URLS.keys()),
            "status": "running",
            "note": "Scraping is running in the background. Check posts page in 2-3 minutes for results.",
            "timestamp": datetime.now().isoformat()
        }
            
    except Exception as e:
        logger.error(f"Failed to trigger all forums scraping: {e}")
        return {
            "success": False,
            "message": f"Scraping failed to start: {str(e)}",
            "posts_scraped": 0,
            "timestamp": datetime.now().isoformat()
        }

@router.post("/scrape-working-forums")
async def scrape_working_forums(background_tasks: BackgroundTasks, max_posts: int = 30):
    """
    Scrape only the working forums (Jira and Confluence) with more posts
    """
    try:
        async def scrape_real_content():
            scraper = AtlassianScraper()
            db_ops = DatabaseOperations()
            
            # Only scrape working forums
            working_forums = ["jira", "confluence", "jsm"]
            
            async with scraper:
                for forum in working_forums:
                    logger.info(f"🔍 Scraping real content from {forum}")
                    posts = await scraper.scrape_category(forum, max_posts, max_pages=3)
                    
                    # Store posts in database
                    for post in posts:
                        await db_ops.create_or_update_post({
                            'title': post.get('title', 'No title'),
                            'content': post.get('content', 'No content'),
                            'author': post.get('author', 'Anonymous'),
                            'category': forum,
                            'url': post.get('url', ''),
                            'excerpt': post.get('excerpt', ''),
                            'date': post.get('date', datetime.now())
                        })
                    
                    logger.info(f"✅ Stored {len(posts)} real posts from {forum}")
        
        # Run real content scraping in background
        background_tasks.add_task(scrape_real_content)
        
        return {
            "message": f"Real content scraping initiated (Jira + Confluence)",
            "status": "running",
            "forums": ["jira", "confluence"],
            "max_posts_each": max_posts,
            "note": f"Scraping up to {max_posts} real posts from each working forum. This will take 2-4 minutes."
        }
    except Exception as e:
        logger.error(f"Failed to trigger real scraping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/populate-real-now")
async def populate_real_data_now(background_tasks: BackgroundTasks):
    """
    Immediately populate database with real content from working forums
    This bypasses the scheduler and directly scrapes Jira + Confluence
    """
    try:
        async def populate_now():
            logger.info("🚀 Starting immediate real data population...")
            scraper = AtlassianScraper()
            db_ops = DatabaseOperations()
            
            # Only use forums that work without authentication  
            working_forums = ['jira', 'confluence', 'jsm']
            total_posts = 0
            
            async with scraper:
                for forum in working_forums:
                    logger.info(f"🔍 Scraping real content from {forum}...")
                    
                    try:
                        # Scrape 25 posts per forum across 3 pages for better coverage
                        posts = await scraper.scrape_category(forum, max_posts=25, max_pages=3)
                        logger.info(f"📋 Found {len(posts)} real posts from {forum}")
                        
                        # Store each post
                        for post in posts:
                            try:
                                await db_ops.create_or_update_post({
                                    'title': post.get('title', 'No title'),
                                    'content': post.get('content', 'No content'), 
                                    'author': post.get('author', 'Anonymous'),
                                    'category': forum,
                                    'url': post.get('url', ''),
                                    'excerpt': post.get('excerpt', ''),
                                    'date': post.get('date', datetime.now())
                                })
                            except Exception as e:
                                logger.error(f"Error saving post: {e}")
                        
                        total_posts += len(posts)
                        logger.info(f"✅ Saved {len(posts)} real posts from {forum}")
                        
                    except Exception as e:
                        logger.error(f"❌ Error scraping {forum}: {e}")
            
            logger.info(f"🎉 Real data population complete! Total: {total_posts} posts")
        
        # Run real data population in background
        background_tasks.add_task(populate_now)
        
        return {
            "message": "Real content population initiated",
            "status": "running",
            "description": "Scraping 25 real posts each from Jira, Confluence, and JSM forums", 
            "expected_posts": "~75 real posts",
            "forums": ["jira", "confluence", "jsm"],
            "note": "This will take 2-3 minutes. Real content only - no demo data!"
        }
        
    except Exception as e:
        logger.error(f"Failed to populate real data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/full-collection")
async def trigger_full_data_collection(background_tasks: BackgroundTasks):
    """
    Manually trigger full data collection pipeline:
    1. Scrape new posts
    2. Analyze sentiment
    3. Generate analytics
    """
    try:
        # Run full collection in background
        background_tasks.add_task(trigger_full_collection)
        
        return {
            "message": "Full data collection pipeline initiated",
            "status": "running", 
            "pipeline": [
                "1. Scraping posts from all forums",
                "2. Analyzing sentiment with AI",
                "3. Generating analytics and trends"
            ],
            "note": "This may take 2-5 minutes. Check /api/scraping/status for progress"
        }
    except Exception as e:
        logger.error(f"Failed to trigger full collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_scraping_status():
    """
    Get current scraping and scheduler status with detailed activity info
    """
    try:
        from database.connection import get_session
        from database.models import PostDB
        from datetime import datetime, timedelta
        from collections import Counter
        
        # Get database stats
        db_ops = DatabaseOperations()
        total_posts = await db_ops.get_posts_count()
        recent_posts_24h = await db_ops.get_recent_posts_count(hours=24)
        recent_posts_1h = await db_ops.get_recent_posts_count(hours=1)
        
        # Get detailed breakdown by forum and time
        with get_session() as db:
            # Posts by forum in last 24h
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_posts_query = db.query(PostDB).filter(PostDB.created_at >= recent_cutoff).all()
            
            forum_stats = Counter([post.category for post in recent_posts_query])
            
            # Find most recent post for "last activity"
            latest_post = db.query(PostDB).order_by(PostDB.created_at.desc()).first()
            last_activity_time = latest_post.created_at.isoformat() if latest_post else None
            last_activity_ago = None
            
            if latest_post:
                delta = datetime.now() - latest_post.created_at.replace(tzinfo=None)
                if delta.days > 0:
                    last_activity_ago = f"{delta.days} days ago"
                elif delta.seconds > 3600:
                    hours = delta.seconds // 3600
                    last_activity_ago = f"{hours} hours ago"
                elif delta.seconds > 60:
                    minutes = delta.seconds // 60
                    last_activity_ago = f"{minutes} minutes ago"
                else:
                    last_activity_ago = "Just now"
        
        # Calculate health score
        health_score = min(100, max(0, 50 + min(recent_posts_24h * 2, 50)))
        
        return {
            "scraping_health": {
                "status": "active" if recent_posts_1h > 0 else "idle",
                "health_score": health_score,
                "last_activity": last_activity_time,
                "last_activity_ago": last_activity_ago
            },
            "database": {
                "total_posts": total_posts,
                "posts_last_24h": recent_posts_24h,
                "posts_last_hour": recent_posts_1h,
                "forum_breakdown_24h": dict(forum_stats)
            },
            "forums": {
                "available": ["jira", "jsm", "confluence", "rovo", "announcements"],
                "active_forums": list(forum_stats.keys()),
                "most_active_forum": max(forum_stats.keys(), key=forum_stats.get) if forum_stats else None
            },
            "recommendations": [
                "Database contains posts - scraping has been successful" if total_posts > 0 else "No posts found - try running 'Scrape on Demand'",
                f"Recent activity: {recent_posts_24h} posts in last 24h" if recent_posts_24h > 0 else "No recent activity - consider triggering scraping",
                "Health score good" if health_score > 70 else "Consider running fresh scraping to improve health score"
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-single-forum/{forum}")
async def test_single_forum_scraping(forum: str):
    """
    Test scraping a single forum for debugging
    Available forums: jira, jsm, confluence, rovo, announcements
    """
    valid_forums = ["jira", "jsm", "confluence", "rovo", "announcements"]
    
    if forum not in valid_forums:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid forum. Must be one of: {valid_forums}"
        )
    
    try:
        scraper = AtlassianScraper()
        
        # Test scrape single forum
        async with scraper:
            posts = await scraper.scrape_category(forum, max_posts=5, max_pages=2)
        
        return {
            "forum": forum,
            "posts_scraped": len(posts),
            "sample_posts": [
                {
                    "title": post.get("title", "")[:100] + "..." if len(post.get("title", "")) > 100 else post.get("title", ""),
                    "author": post.get("author", ""),
                    "url": post.get("url", "")
                }
                for post in posts[:3]  # Show first 3 posts
            ]
        }
    except Exception as e:
        logger.error(f"Failed to test forum scraping: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

@router.get("/forums")
async def get_available_forums():
    """
    Get list of available forums for scraping
    """
    scraper = AtlassianScraper()
    
    return {
        "forums": list(scraper.BASE_URLS.keys()),
        "forum_details": {
            "jira": {
                "name": "Jira Questions",
                "url": scraper.BASE_URLS["jira"]
            },
            "jsm": {
                "name": "Jira Service Management", 
                "url": scraper.BASE_URLS["jsm"]
            },
            "confluence": {
                "name": "Confluence Questions",
                "url": scraper.BASE_URLS["confluence"] 
            },
            "rovo": {
                "name": "Rovo",
                "url": scraper.BASE_URLS["rovo"]
            },
            "announcements": {
                "name": "Announcements",
                "url": scraper.BASE_URLS["announcements"]
            }
        }
    }

@router.post("/fresh-start")
async def fresh_start_scraping(background_tasks: BackgroundTasks):
    """
    Clear all data and start fresh scraping - perfect for getting clean BI data
    """
    try:
        async def fresh_start_task():
            """Background task for fresh start"""
            try:
                logger.info("🗑️ Starting fresh start: clearing all data...")
                db_ops = DatabaseOperations()
                
                # Delete all existing posts
                deleted_count = await db_ops.delete_all_posts()
                logger.info(f"🗑️ Cleared {deleted_count} existing posts")
                
                # Start fresh scraping
                logger.info("🚀 Starting fresh scraping of all forums...")
                scraper = AtlassianScraper()
                
                total_posts_scraped = 0
                forums_scraped = []
                
                async with scraper:
                    # Scrape each forum with more posts for better BI data
                    for forum_name in scraper.BASE_URLS.keys():
                        try:
                            logger.info(f"🔍 Fresh scraping {forum_name}...")
                            posts = await scraper.scrape_category(forum_name, max_posts=30, max_pages=3)
                            
                            # Store posts in database
                            for post in posts:
                                try:
                                    await db_ops.create_or_update_post({
                                        'title': post.get('title', 'No title'),
                                        'content': post.get('content', 'No content'),
                                        'author': post.get('author', 'Anonymous'),
                                        'category': forum_name,
                                        'url': post.get('url', ''),
                                        'excerpt': post.get('excerpt', ''),
                                        'date': post.get('date', datetime.now())
                                    })
                                except Exception as save_error:
                                    logger.error(f"Error saving post: {save_error}")
                                    continue
                            
                            total_posts_scraped += len(posts)
                            if len(posts) > 0:
                                forums_scraped.append(forum_name)
                            
                            logger.info(f"✅ Fresh scraped {len(posts)} posts from {forum_name}")
                            
                        except Exception as forum_error:
                            logger.error(f"❌ Error fresh scraping {forum_name}: {forum_error}")
                            continue
                
                logger.info(f"🎉 Fresh start completed! Total: {total_posts_scraped} posts from {len(forums_scraped)} forums")
                logger.info("📊 Your BI Dashboard now has fresh data to analyze!")
                
            except Exception as e:
                logger.error(f"❌ Fresh start task failed: {e}")
        
        # Start fresh start task immediately
        background_tasks.add_task(fresh_start_task)
        
        return {
            "success": True,
            "message": "Fresh start initiated - clearing data and re-scraping",
            "action": "reset_and_scrape",
            "status": "running",
            "expected_posts": "~150 fresh posts across all forums",
            "note": "Perfect for populating your BI Dashboard with fresh data. Check back in 4-5 minutes!",
            "timestamp": datetime.now().isoformat()
        }
            
    except Exception as e:
        logger.error(f"Failed to trigger fresh start: {e}")
        return {
            "success": False,
            "message": f"Fresh start failed to initialize: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@router.delete("/reset-data")
async def reset_all_data():
    """
    DANGER: Reset all scraped data (for development only)
    """
    try:
        db_ops = DatabaseOperations()
        
        # Delete all posts (keep analytics for now)
        deleted_count = await db_ops.delete_all_posts()
        
        return {
            "message": "All scraped data has been reset",
            "deleted_posts": deleted_count,
            "warning": "This action cannot be undone"
        }
    except Exception as e:
        logger.error(f"Failed to reset data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-demo-data")
async def generate_demo_data(background_tasks: BackgroundTasks):
    """
    Generate realistic demo data for the dashboard
    This creates sample posts with sentiment analysis
    """
    try:
        async def generate_data():
            generator = DemoDataGenerator()
            await generator.populate_demo_data()
            await generator.simulate_live_activity()
        
        # Run demo data generation in background
        background_tasks.add_task(generate_data)
        
        return {
            "message": "Demo data generation initiated",
            "status": "running",
            "description": "Generating 50+ realistic community posts with sentiment analysis",
            "note": "Check /api/scraping/status for progress. This will take 1-2 minutes."
        }
    except Exception as e:
        logger.error(f"Failed to generate demo data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulate-activity")
async def simulate_live_activity():
    """
    Add a few new posts to simulate ongoing community activity
    """
    try:
        generator = DemoDataGenerator()
        new_posts_count = await generator.simulate_live_activity()
        
        return {
            "message": "Live activity simulation completed",
            "new_posts": new_posts_count,
            "description": f"Added {new_posts_count} new posts to simulate real-time community activity"
        }
    except Exception as e:
        logger.error(f"Failed to simulate activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))