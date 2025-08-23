#!/usr/bin/env python3
"""
Direct script to populate database with real Atlassian Community content
Run this to get immediate real data from Jira and Confluence forums
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))

from services.scraper import AtlassianScraper
from database.operations import DatabaseOperations
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def populate_real_data():
    """Populate database with real Atlassian Community posts"""
    logger.info("🚀 Starting real data population...")
    
    scraper = AtlassianScraper()
    db_ops = DatabaseOperations()
    
    # Only use forums that work without authentication
    working_forums = {
        'jira': 'Jira Questions', 
        'confluence': 'Confluence Questions'
    }
    
    total_posts = 0
    
    async with scraper:
        for forum_key, forum_name in working_forums.items():
            logger.info(f"🔍 Scraping {forum_name}...")
            
            try:
                # Scrape more posts per forum
                posts = await scraper.scrape_category(forum_key, max_posts=25)
                
                logger.info(f"📋 Found {len(posts)} posts from {forum_name}")
                
                # Store each post
                for i, post in enumerate(posts, 1):
                    try:
                        await db_ops.create_or_update_post({
                            'title': post.get('title', 'No title'),
                            'content': post.get('content', 'No content'),
                            'author': post.get('author', 'Anonymous'),
                            'category': forum_key,
                            'url': post.get('url', ''),
                            'excerpt': post.get('excerpt', ''),
                            'date': post.get('date', datetime.now())
                        })
                        
                        if i % 5 == 0:
                            logger.info(f"  💾 Saved {i}/{len(posts)} posts from {forum_name}")
                    
                    except Exception as e:
                        logger.error(f"  ❌ Error saving post {i}: {e}")
                
                total_posts += len(posts)
                logger.info(f"✅ Completed {forum_name}: {len(posts)} posts saved")
                
            except Exception as e:
                logger.error(f"❌ Error scraping {forum_name}: {e}")
    
    logger.info(f"🎉 Real data population complete! Total posts: {total_posts}")
    
    # Final count check
    final_count = await db_ops.get_posts_count()
    logger.info(f"📊 Database now contains {final_count} total posts")

if __name__ == "__main__":
    asyncio.run(populate_real_data())