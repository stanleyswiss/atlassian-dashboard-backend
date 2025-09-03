#!/usr/bin/env python3
"""
Database migration script to add enhanced analysis fields
"""
import os
import sys
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text, MetaData, inspect
from database.connection import get_database_url
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_cloud_news_constraint():
    """Fix Cloud News database constraint from source_url only to source_url + feature_title"""
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    
    # Get current schema
    inspector = inspect(engine)
    
    # Check if cloud_news table exists
    if not inspector.has_table('cloud_news'):
        logger.error("Cloud News table does not exist!")
        return False
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            logger.info("🔍 Checking current Cloud News constraints...")
            
            # Check if old constraint exists
            result = conn.execute(text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'cloud_news' 
                AND constraint_type = 'UNIQUE'
                AND constraint_name = 'cloud_news_source_url_key'
            """))
            
            old_constraint_exists = result.fetchone() is not None
            logger.info(f"Old constraint exists: {old_constraint_exists}")
            
            if old_constraint_exists:
                logger.info("🗑️  Dropping old constraint...")
                conn.execute(text("ALTER TABLE cloud_news DROP CONSTRAINT cloud_news_source_url_key"))
                logger.info("✅ Old constraint dropped")
            
            # Check if new constraint already exists
            result = conn.execute(text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'cloud_news' 
                AND constraint_type = 'UNIQUE'
                AND constraint_name = 'unique_source_feature'
            """))
            
            new_constraint_exists = result.fetchone() is not None
            logger.info(f"New constraint exists: {new_constraint_exists}")
            
            if not new_constraint_exists:
                logger.info("🔧 Creating new composite constraint...")
                conn.execute(text("""
                    ALTER TABLE cloud_news 
                    ADD CONSTRAINT unique_source_feature 
                    UNIQUE (source_url, feature_title)
                """))
                logger.info("✅ New composite constraint created")
            
            # Commit transaction
            trans.commit()
            logger.info("🎉 Cloud News constraint fix completed!")
            return True
            
        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"❌ Cloud News constraint fix failed: {e}")
            return False

def migrate_database():
    """Add missing columns to existing database"""
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    
    # Get current schema
    inspector = inspect(engine)
    
    # Check if posts table exists
    if not inspector.has_table('posts'):
        logger.error("Posts table does not exist! Please run database initialization first.")
        return False
    
    # Get existing columns
    existing_columns = {col['name'] for col in inspector.get_columns('posts')}
    logger.info(f"Existing columns: {existing_columns}")
    
    # Define new columns to add
    new_columns = [
        "enhanced_category VARCHAR(50)",
        "has_screenshots BOOLEAN DEFAULT FALSE",
        "vision_analysis TEXT",  # JSON stored as text
        "text_analysis TEXT",    # JSON stored as text
        "problem_severity VARCHAR(20)",
        "resolution_status VARCHAR(30)",
        "business_impact VARCHAR(20)",
        "business_value INTEGER DEFAULT 0",
        "extracted_issues TEXT", # JSON stored as text
        "mentioned_products TEXT", # JSON stored as text
        "thread_data TEXT", # Full thread/reply data
        "has_accepted_solution BOOLEAN DEFAULT FALSE", # Quick flag for solution status
        "total_replies INTEGER DEFAULT 0", # Number of replies in thread
        "ai_summary TEXT", # AI-generated concise summary
        "ai_category VARCHAR(50)", # AI-determined category
        "ai_key_points TEXT", # JSON array of key points
        "ai_action_required VARCHAR(20)", # high, medium, low, none
        "ai_hashtags TEXT" # JSON array of hashtags
    ]
    
    column_names = [
        "enhanced_category",
        "has_screenshots", 
        "vision_analysis",
        "text_analysis",
        "problem_severity",
        "resolution_status",
        "business_impact", 
        "business_value",
        "extracted_issues",
        "mentioned_products",
        "thread_data",
        "has_accepted_solution",
        "total_replies",
        "ai_summary",
        "ai_category",
        "ai_key_points",
        "ai_action_required",
        "ai_hashtags"
    ]
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            for column_name, column_def in zip(column_names, new_columns):
                if column_name not in existing_columns:
                    logger.info(f"Adding column: {column_name}")
                    
                    # Add column
                    conn.execute(text(f"ALTER TABLE posts ADD COLUMN {column_def}"))
                    logger.info(f"✅ Added column: {column_name}")
                else:
                    logger.info(f"⏭️  Column {column_name} already exists, skipping")
            
            # Check if analytics table exists, if not create it
            if not inspector.has_table('analytics'):
                logger.info("Creating analytics table...")
                analytics_sql = """
                CREATE TABLE analytics (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    total_posts INTEGER DEFAULT 0,
                    sentiment_breakdown TEXT,  -- JSON
                    category_distribution TEXT,  -- JSON  
                    trending_topics TEXT,  -- JSON
                    problem_resolution_stats TEXT,  -- JSON
                    business_insights TEXT,  -- JSON
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
                conn.execute(text(analytics_sql))
                logger.info("✅ Created analytics table")
            
            # Commit transaction
            trans.commit()
            logger.info("🎉 Database migration completed successfully!")
            return True
            
        except Exception as e:
            # Rollback on error
            trans.rollback()
            logger.error(f"❌ Migration failed: {e}")
            return False

if __name__ == "__main__":
    success = migrate_database()
    if success:
        print("✅ Database migration completed successfully!")
        sys.exit(0)
    else:
        print("❌ Database migration failed!")
        sys.exit(1)