#!/usr/bin/env python3
"""
Database cleanup script to remove spam and irrelevant content
Run this to clean up JetBlue and other spam data from the database
"""

import os
import sys
from datetime import datetime
import logging

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import get_session
from database.models import PostDB
from sqlalchemy import or_

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Spam keywords to filter out
SPAM_KEYWORDS = [
    'jetblue', 'air france', 'airline', 'customer list', 'phone numbers', 
    'email list', 'buy list', 'purchase list', 'contact list', 'marketing list',
    'exodus wallet', 'gemini customer', 'crypto', 'wallet support',
    'customer service numbers', 'contact service', 'customer contact'
]

# Required Atlassian keywords - at least one must be present
ATLASSIAN_KEYWORDS = [
    'jira', 'confluence', 'bitbucket', 'trello', 'jsm', 'service desk', 
    'atlassian', 'bamboo', 'fisheye', 'crucible', 'crowd', 'marketplace',
    'agile', 'scrum', 'kanban', 'workflow', 'automation', 'plugin', 'addon',
    'api', 'rest', 'webhook', 'integration'
]

def is_spam(post):
    """Check if a post is spam based on title and content"""
    title_lower = (post.title or '').lower()
    content_lower = (post.content or '')[:500].lower()  # Check first 500 chars
    excerpt_lower = (post.excerpt or '').lower()
    
    # Check for spam keywords
    for spam_word in SPAM_KEYWORDS:
        if spam_word in title_lower or spam_word in content_lower or spam_word in excerpt_lower:
            return True
    
    return False

def is_atlassian_related(post):
    """Check if a post is related to Atlassian products"""
    title_lower = (post.title or '').lower()
    content_lower = (post.content or '')[:500].lower()
    excerpt_lower = (post.excerpt or '').lower()
    category_lower = (post.category or '').lower()
    
    # Check if any Atlassian keyword is present
    for keyword in ATLASSIAN_KEYWORDS:
        if (keyword in title_lower or 
            keyword in content_lower or 
            keyword in excerpt_lower or
            keyword in category_lower):
            return True
    
    return False

def cleanup_database():
    """Remove spam posts from the database"""
    with get_session() as db:
        try:
            # Get all posts
            all_posts = db.query(PostDB).all()
            total_posts = len(all_posts)
            logger.info(f"Total posts in database: {total_posts}")
            
            spam_posts = []
            non_atlassian_posts = []
            
            for post in all_posts:
                # Check if it's spam
                if is_spam(post):
                    spam_posts.append(post)
                    logger.info(f"🚫 Spam detected: {post.title[:50]}...")
                # Check if it's not Atlassian-related
                elif not is_atlassian_related(post):
                    non_atlassian_posts.append(post)
                    logger.info(f"⚠️  Non-Atlassian: {post.title[:50]}...")
            
            # Confirm before deletion
            total_to_delete = len(spam_posts) + len(non_atlassian_posts)
            
            if total_to_delete > 0:
                logger.info(f"\n📊 Cleanup Summary:")
                logger.info(f"  - Total posts: {total_posts}")
                logger.info(f"  - Spam posts: {len(spam_posts)}")
                logger.info(f"  - Non-Atlassian posts: {len(non_atlassian_posts)}")
                logger.info(f"  - Total to delete: {total_to_delete}")
                logger.info(f"  - Posts to keep: {total_posts - total_to_delete}")
                
                # Delete spam posts
                for post in spam_posts:
                    db.delete(post)
                    logger.info(f"  ✅ Deleted spam: {post.title[:50]}...")
                
                # Optionally delete non-Atlassian posts (uncomment if desired)
                # for post in non_atlassian_posts:
                #     db.delete(post)
                #     logger.info(f"  ✅ Deleted non-Atlassian: {post.title[:50]}...")
                
                db.commit()
                logger.info(f"\n✨ Cleanup complete! Deleted {len(spam_posts)} spam posts.")
                
                # Show remaining posts count
                remaining = db.query(PostDB).count()
                logger.info(f"📈 Remaining posts in database: {remaining}")
            else:
                logger.info("✨ No spam or irrelevant posts found. Database is clean!")
                
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")
            db.rollback()
            raise

def show_sample_spam():
    """Show a sample of spam posts without deleting them"""
    with get_session() as db:
        all_posts = db.query(PostDB).all()
        
        logger.info("\n🔍 Sample of posts that would be deleted:")
        count = 0
        for post in all_posts:
            if is_spam(post):
                logger.info(f"  SPAM: {post.title[:80]}")
                count += 1
                if count >= 10:  # Show max 10 samples
                    break
        
        if count == 0:
            logger.info("  No spam posts found!")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up spam data from the database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without actually deleting')
    parser.add_argument('--include-non-atlassian', action='store_true', help='Also delete non-Atlassian posts')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No data will be deleted")
        show_sample_spam()
    else:
        cleanup_database()