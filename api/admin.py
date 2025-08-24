from fastapi import APIRouter, HTTPException
from sqlalchemy import text, inspect
from database.connection import engine, get_database_url
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/test")
async def test_admin_api():
    """Test endpoint to verify admin API is working"""
    return {
        "success": True,
        "message": "Admin API is working",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/test-posts-query")
async def test_posts_query():
    """Test querying posts table to identify schema issues"""
    
    try:
        with engine.connect() as conn:
            # Try simple query first
            result = conn.execute(text("SELECT COUNT(*) as count FROM posts"))
            total_posts = result.fetchone()[0]
            
            # Try querying with enhanced columns
            result = conn.execute(text("""
                SELECT id, title, enhanced_category, has_screenshots, business_value 
                FROM posts 
                LIMIT 1
            """))
            sample_post = result.fetchone()
            
            return {
                "success": True,
                "total_posts": total_posts,
                "sample_post": dict(sample_post._mapping) if sample_post else None,
                "message": "Posts table query successful"
            }
            
    except Exception as e:
        logger.error(f"Posts query test failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Posts table query failed"
        }

@router.post("/migrate-database")
async def migrate_database(force_recreate: bool = False):
    """Add missing enhanced analysis columns to database"""
    
    logger.info(f"Starting database migration... (force_recreate={force_recreate})")
    
    try:
        # Get current schema
        inspector = inspect(engine)
        
        # Check if posts table exists
        if not inspector.has_table('posts'):
            raise HTTPException(status_code=500, detail="Posts table does not exist!")
        
        # Get existing columns
        existing_columns = {col['name'] for col in inspector.get_columns('posts')}
        
        # Get database URL to determine database type
        database_url = get_database_url()
        is_postgres = database_url.startswith('postgresql')
        
        # Define new columns to add (adjust for database type)
        if is_postgres:
            new_columns_map = {
                "enhanced_category": "VARCHAR(50)",
                "has_screenshots": "INTEGER DEFAULT 0",  # Use INTEGER for boolean in Postgres too for compatibility
                "vision_analysis": "JSONB",  # Use JSONB for better performance
                "text_analysis": "JSONB", 
                "problem_severity": "VARCHAR(20)",
                "resolution_status": "VARCHAR(20)",  # Match model size
                "business_impact": "VARCHAR(30)",
                "business_value": "VARCHAR(50)",  # Match model - should be VARCHAR not INTEGER
                "extracted_issues": "JSONB",
                "mentioned_products": "JSONB"
            }
        else:
            # SQLite - use TEXT for JSON fields
            new_columns_map = {
                "enhanced_category": "VARCHAR(50)",
                "has_screenshots": "INTEGER DEFAULT 0",
                "vision_analysis": "TEXT",  # SQLite stores JSON as TEXT
                "text_analysis": "TEXT",
                "problem_severity": "VARCHAR(20)", 
                "resolution_status": "VARCHAR(20)",
                "business_impact": "VARCHAR(30)",
                "business_value": "VARCHAR(50)",
                "extracted_issues": "TEXT",
                "mentioned_products": "TEXT"
            }
        
        added_columns = []
        skipped_columns = []
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                for column_name, column_def in new_columns_map.items():
                    if column_name not in existing_columns:
                        # Add column
                        conn.execute(text(f"ALTER TABLE posts ADD COLUMN {column_name} {column_def}"))
                        added_columns.append(column_name)
                        logger.info(f"Added column: {column_name}")
                    elif force_recreate:
                        # Drop and recreate column with correct type
                        try:
                            conn.execute(text(f"ALTER TABLE posts DROP COLUMN {column_name}"))
                            conn.execute(text(f"ALTER TABLE posts ADD COLUMN {column_name} {column_def}"))
                            added_columns.append(f"{column_name} (recreated)")
                            logger.info(f"Recreated column: {column_name}")
                        except Exception as col_error:
                            logger.warning(f"Could not recreate column {column_name}: {col_error}")
                            skipped_columns.append(f"{column_name} (recreation failed)")
                    else:
                        skipped_columns.append(column_name)
                
                # Check if analytics table exists, if not create it
                if not inspector.has_table('analytics'):
                    if is_postgres:
                        analytics_sql = """
                        CREATE TABLE analytics (
                            id SERIAL PRIMARY KEY,
                            date DATE NOT NULL,
                            total_posts INTEGER DEFAULT 0,
                            sentiment_breakdown TEXT,
                            category_distribution TEXT,
                            trending_topics TEXT,
                            problem_resolution_stats TEXT,
                            business_insights TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    else:
                        analytics_sql = """
                        CREATE TABLE analytics (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date DATE NOT NULL,
                            total_posts INTEGER DEFAULT 0,
                            sentiment_breakdown TEXT,
                            category_distribution TEXT,
                            trending_topics TEXT,
                            problem_resolution_stats TEXT,
                            business_insights TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        """
                    conn.execute(text(analytics_sql))
                    added_columns.append("analytics_table")
                    logger.info("Created analytics table")
                
                # Check if settings table exists, if not create it
                if not inspector.has_table('settings'):
                    if is_postgres:
                        settings_sql = """
                        CREATE TABLE settings (
                            id SERIAL PRIMARY KEY,
                            key VARCHAR(100) NOT NULL UNIQUE,
                            value TEXT NOT NULL,
                            value_type VARCHAR(20) DEFAULT 'string',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE INDEX idx_settings_key ON settings(key);
                        """
                    else:
                        settings_sql = """
                        CREATE TABLE settings (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            key VARCHAR(100) NOT NULL UNIQUE,
                            value TEXT NOT NULL,
                            value_type VARCHAR(20) DEFAULT 'string',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE INDEX idx_settings_key ON settings(key);
                        """
                    conn.execute(text(settings_sql))
                    added_columns.append("settings_table")
                    logger.info("Created settings table")
                
                # Commit transaction
                trans.commit()
                
                logger.info(f"Migration completed. Added: {added_columns}, Skipped: {skipped_columns}")
                
                return {
                    "success": True,
                    "message": "Database migration completed successfully",
                    "added_columns": added_columns,
                    "skipped_columns": skipped_columns,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                # Rollback on error
                trans.rollback()
                logger.error(f"Migration transaction failed: {e}")
                raise HTTPException(status_code=500, detail=f"Migration transaction failed: {str(e)}")
                
    except Exception as e:
        logger.error(f"Database migration error: {e}")
        return {
            "success": False,
            "message": f"Database migration failed: {str(e)}",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.post("/create-settings-table")
async def create_settings_table():
    """Create settings table specifically - for troubleshooting settings persistence"""
    try:
        from database.connection import get_database_url
        
        database_url = get_database_url()
        is_postgres = database_url.startswith('postgresql')
        
        with engine.connect() as conn:
            # Check if settings table already exists
            inspector = inspect(engine)
            if inspector.has_table('settings'):
                return {
                    "success": True,
                    "message": "Settings table already exists",
                    "action": "none_needed",
                    "timestamp": datetime.now().isoformat()
                }
            
            trans = conn.begin()
            try:
                # Create settings table
                if is_postgres:
                    settings_sql = """
                    CREATE TABLE settings (
                        id SERIAL PRIMARY KEY,
                        key VARCHAR(100) NOT NULL UNIQUE,
                        value TEXT NOT NULL,
                        value_type VARCHAR(20) DEFAULT 'string',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX idx_settings_key ON settings(key);
                    """
                else:
                    settings_sql = """
                    CREATE TABLE settings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key VARCHAR(100) NOT NULL UNIQUE,
                        value TEXT NOT NULL,
                        value_type VARCHAR(20) DEFAULT 'string',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX idx_settings_key ON settings(key);
                    """
                
                conn.execute(text(settings_sql))
                trans.commit()
                
                logger.info("Successfully created settings table")
                
                return {
                    "success": True,
                    "message": "Settings table created successfully",
                    "action": "created_settings_table",
                    "database_type": "PostgreSQL" if is_postgres else "SQLite",
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                trans.rollback()
                logger.error(f"Failed to create settings table: {e}")
                return {
                    "success": False,
                    "message": f"Failed to create settings table: {str(e)}",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                
    except Exception as e:
        logger.error(f"Error creating settings table: {e}")
        return {
            "success": False,
            "message": f"Error creating settings table: {str(e)}",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/debug-settings")
async def debug_settings():
    """Debug settings persistence - test if settings can be read/written"""
    try:
        from api.settings import get_all_settings, set_setting_in_db, get_setting_from_db
        
        # Test 1: Try to read current settings
        current_settings = get_all_settings()
        
        # Test 2: Try to write a test setting
        test_write = set_setting_in_db("debug_test", "test_value", "string")
        
        # Test 3: Try to read the test setting back
        test_read = get_setting_from_db("debug_test", "not_found")
        
        # Test 4: Check if settings table has any data
        from database.connection import get_session
        from database.models import SettingsDB
        
        with get_session() as db:
            settings_count = db.query(SettingsDB).count()
            all_settings_in_db = db.query(SettingsDB).all()
            
            db_settings_list = [
                {
                    "key": s.key,
                    "value": s.value,
                    "value_type": s.value_type,
                    "created_at": s.created_at.isoformat()
                }
                for s in all_settings_in_db
            ]
        
        return {
            "success": True,
            "debug_info": {
                "current_settings": current_settings,
                "test_write_success": test_write,
                "test_read_result": test_read,
                "settings_count_in_db": settings_count,
                "all_db_settings": db_settings_list
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Settings debug error: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/analyze-posts-status")
async def analyze_posts_status():
    """Check the status of AI analysis on current posts"""
    try:
        from database.connection import get_session
        from database.models import PostDB
        from datetime import datetime, timedelta
        
        with get_session() as db:
            # Get all posts
            all_posts = db.query(PostDB).all()
            total_posts = len(all_posts)
            
            # Check Vision AI analysis status
            posts_with_vision = db.query(PostDB).filter(PostDB.vision_analysis.isnot(None)).count()
            posts_with_enhanced_category = db.query(PostDB).filter(PostDB.enhanced_category.isnot(None)).count()
            posts_with_screenshots = db.query(PostDB).filter(PostDB.has_screenshots == 1).count()
            
            # Get recent posts (last 24 hours)
            recent_cutoff = datetime.now() - timedelta(hours=24)
            recent_posts = db.query(PostDB).filter(PostDB.created_at >= recent_cutoff).all()
            recent_count = len(recent_posts)
            
            # Sample some recent posts to check their analysis status
            sample_posts = recent_posts[:5]  # First 5 recent posts
            sample_analysis = []
            
            for post in sample_posts:
                sample_analysis.append({
                    "id": post.id,
                    "title": post.title[:50] + "..." if len(post.title) > 50 else post.title,
                    "category": post.category,
                    "created_at": post.created_at.isoformat(),
                    "has_vision_analysis": bool(post.vision_analysis),
                    "has_enhanced_category": bool(post.enhanced_category),
                    "enhanced_category": post.enhanced_category,
                    "has_screenshots": bool(post.has_screenshots),
                    "problem_severity": post.problem_severity,
                    "business_impact": post.business_impact
                })
            
            # Check if any posts have actual analysis data
            posts_with_any_analysis = db.query(PostDB).filter(
                (PostDB.vision_analysis.isnot(None)) | 
                (PostDB.enhanced_category.isnot(None)) |
                (PostDB.problem_severity.isnot(None))
            ).count()
            
            return {
                "success": True,
                "analysis_status": {
                    "total_posts": total_posts,
                    "recent_posts_24h": recent_count,
                    "posts_with_vision_analysis": posts_with_vision,
                    "posts_with_enhanced_category": posts_with_enhanced_category,
                    "posts_with_screenshots": posts_with_screenshots,
                    "posts_with_any_analysis": posts_with_any_analysis,
                    "analysis_coverage_percent": round((posts_with_any_analysis / total_posts * 100), 1) if total_posts > 0 else 0
                },
                "sample_recent_posts": sample_analysis,
                "diagnosis": {
                    "vision_ai_working": posts_with_vision > 0,
                    "enhanced_analysis_working": posts_with_enhanced_category > 0,
                    "likely_issue": "No AI analysis running on scraped posts" if posts_with_any_analysis == 0 else "AI analysis partially working"
                },
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error analyzing posts status: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.post("/analyze-all-posts")
async def analyze_all_posts_with_ai():
    """Analyze all existing posts with Vision AI and enhanced analysis"""
    try:
        from database.connection import get_session
        from database.models import PostDB
        from services.enhanced_analyzer import EnhancedAnalyzer
        from api.settings import is_vision_analysis_enabled
        import json
        
        if not is_vision_analysis_enabled():
            return {
                "success": False,
                "message": "Vision AI is not enabled. Please enable it in settings and ensure OpenAI API key is configured.",
                "timestamp": datetime.now().isoformat()
            }
        
        with get_session() as db:
            # Get all posts without analysis
            posts_to_analyze = db.query(PostDB).filter(
                (PostDB.vision_analysis.is_(None)) | 
                (PostDB.enhanced_category.is_(None))
            ).all()
            
            if not posts_to_analyze:
                return {
                    "success": True,
                    "message": "All posts are already analyzed",
                    "posts_analyzed": 0,
                    "timestamp": datetime.now().isoformat()
                }
            
            analyzer = EnhancedAnalyzer()
            analyzed_count = 0
            errors = []
            
            for post in posts_to_analyze:
                try:
                    # Convert to dict for analyzer
                    post_dict = {
                        'id': post.id,
                        'title': post.title,
                        'content': post.content,
                        'url': post.url,
                        'category': post.category,
                        'author': post.author
                    }
                    
                    # Run comprehensive analysis
                    analysis_result = await analyzer.analyze_post_comprehensive(post_dict)
                    
                    # Update post with analysis results
                    post.enhanced_category = analysis_result.get('enhanced_category', 'uncategorized')
                    post.vision_analysis = json.dumps(analysis_result.get('vision_analysis', {}))
                    post.text_analysis = json.dumps(analysis_result.get('text_analysis', {}))
                    
                    # Extract specific fields from analysis
                    vision_data = analysis_result.get('vision_analysis', {})
                    text_data = analysis_result.get('text_analysis', {})
                    business_insights = analysis_result.get('business_insights', {})
                    
                    post.has_screenshots = vision_data.get('has_images', 0)
                    post.problem_severity = text_data.get('urgency_level', 'unknown')
                    post.resolution_status = text_data.get('resolution_status', 'unknown')
                    post.business_impact = business_insights.get('user_experience_impact', 'minimal')
                    post.business_value = business_insights.get('business_value', 'low')
                    
                    # Extract issues and products
                    post.extracted_issues = json.dumps(vision_data.get('extracted_issues', []))
                    post.mentioned_products = json.dumps(text_data.get('mentioned_products', []))
                    
                    # Basic sentiment (fallback if not present)
                    if not post.sentiment_score:
                        sentiment = text_data.get('user_sentiment', 'neutral')
                        if sentiment == 'frustrated':
                            post.sentiment_score = -0.5
                            post.sentiment_label = 'negative'
                        elif sentiment == 'excited':
                            post.sentiment_score = 0.5
                            post.sentiment_label = 'positive'
                        else:
                            post.sentiment_score = 0.0
                            post.sentiment_label = 'neutral'
                    
                    analyzed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error analyzing post {post.id}: {e}")
                    errors.append(f"Post {post.id}: {str(e)}")
                    continue
            
            # Commit all changes
            db.commit()
            
            return {
                "success": True,
                "message": f"Successfully analyzed {analyzed_count} posts",
                "total_posts": len(posts_to_analyze),
                "posts_analyzed": analyzed_count,
                "errors": errors if errors else None,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/database-info")
async def get_database_info():
    """Get information about the current database schema"""
    
    try:
        database_url = get_database_url()
        inspector = inspect(engine)
        
        # Get table info
        tables = inspector.get_table_names()
        
        schema_info = {}
        for table_name in tables:
            if table_name in ['posts', 'analytics']:
                columns = inspector.get_columns(table_name)
                schema_info[table_name] = [
                    {
                        "name": col['name'],
                        "type": str(col['type']),
                        "nullable": col['nullable'],
                        "default": col.get('default')
                    }
                    for col in columns
                ]
        
        return {
            "database_url": database_url.split('@')[0] + '@***',  # Hide credentials
            "tables": tables,
            "schema_info": schema_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting database info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get database info: {str(e)}")