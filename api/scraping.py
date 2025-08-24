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
    Get current scraping and scheduler status
    """
    try:
        # Get scheduler status
        scheduler_status = get_scheduler_status()
        
        # Get database stats
        db_ops = DatabaseOperations()
        total_posts = await db_ops.get_posts_count()
        recent_posts = await db_ops.get_recent_posts_count(hours=24)
        
        return {
            "scheduler": scheduler_status,
            "database": {
                "total_posts": total_posts,
                "posts_last_24h": recent_posts
            },
            "last_activity": "Check logs for detailed activity"
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