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
    import os
    from config import settings
    
    api_key_env = os.environ.get("OPENAI_API_KEY", "")
    api_key_settings = settings.openai_api_key
    
    return {
        "success": True,
        "message": "Admin API is working",
        "openai_check": {
            "env_key_exists": bool(api_key_env),
            "env_key_length": len(api_key_env) if api_key_env else 0,
            "settings_key_exists": bool(api_key_settings), 
            "settings_key_length": len(api_key_settings) if api_key_settings else 0,
            "env_key_prefix": api_key_env[:7] + "..." if api_key_env and len(api_key_env) > 10 else "NOT_SET"
        },
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
                "html_content": "TEXT",  # Critical: HTML content with images for vision analysis
                "enhanced_category": "VARCHAR(50)",
                "has_screenshots": "INTEGER DEFAULT 0",  # Use INTEGER for boolean in Postgres too for compatibility
                "vision_analysis": "JSONB",  # Use JSONB for better performance
                "text_analysis": "JSONB", 
                "problem_severity": "VARCHAR(20)",
                "resolution_status": "VARCHAR(20)",  # Match model size
                "business_impact": "VARCHAR(30)",
                "business_value": "VARCHAR(50)",  # Match model - should be VARCHAR not INTEGER
                "extracted_issues": "JSONB",
                "mentioned_products": "JSONB",
                "thread_data": "JSONB",  # Full thread/reply data
                "has_accepted_solution": "BOOLEAN DEFAULT FALSE",
                "total_replies": "INTEGER DEFAULT 0",
                # AI-generated summary fields - MISSING FROM DATABASE!
                "ai_summary": "TEXT",  # AI-generated concise summary
                "ai_category": "VARCHAR(50)",  # AI-determined category
                "ai_key_points": "JSONB",  # JSON array of key points
                "ai_action_required": "VARCHAR(20)",  # high, medium, low, none
                "ai_hashtags": "JSONB"  # JSON array of hashtags
            }
        else:
            # SQLite - use TEXT for JSON fields
            new_columns_map = {
                "html_content": "TEXT",  # Critical: HTML content with images for vision analysis
                "enhanced_category": "VARCHAR(50)",
                "has_screenshots": "INTEGER DEFAULT 0",
                "vision_analysis": "TEXT",  # SQLite stores JSON as TEXT
                "text_analysis": "TEXT",
                "problem_severity": "VARCHAR(20)", 
                "resolution_status": "VARCHAR(20)",
                "business_impact": "VARCHAR(30)",
                "business_value": "VARCHAR(50)",
                "extracted_issues": "TEXT",
                "mentioned_products": "TEXT",
                "thread_data": "TEXT",  # Full thread/reply data
                "has_accepted_solution": "INTEGER DEFAULT 0",  # SQLite uses INTEGER for boolean
                "total_replies": "INTEGER DEFAULT 0",
                # AI-generated summary fields - MISSING FROM DATABASE!
                "ai_summary": "TEXT",  # AI-generated concise summary
                "ai_category": "VARCHAR(50)",  # AI-determined category
                "ai_key_points": "TEXT",  # JSON array stored as TEXT in SQLite
                "ai_action_required": "VARCHAR(20)",  # high, medium, low, none
                "ai_hashtags": "TEXT"  # JSON array stored as TEXT in SQLite
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
async def analyze_all_posts_with_ai(batch_size: int = 5, force_reanalyze: bool = False):
    """Analyze all existing posts with Vision AI and enhanced analysis (chunked processing)"""
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
            if force_reanalyze:
                # Force re-analysis of all posts (ignoring existing analysis)
                posts_to_analyze = db.query(PostDB).limit(batch_size).all()
                logger.info(f"🔄 Force re-analyzing {len(posts_to_analyze)} posts (ignoring existing analysis)")
            else:
                # Get posts without analysis only
                posts_to_analyze = db.query(PostDB).filter(
                    (PostDB.vision_analysis.is_(None)) | 
                    (PostDB.enhanced_category.is_(None))
                ).limit(batch_size).all()  # Process in smaller batches
            
            if not posts_to_analyze:
                return {
                    "success": True,
                    "message": "All posts are already analyzed",
                    "posts_analyzed": 0,
                    "remaining_posts": 0,
                    "timestamp": datetime.now().isoformat()
                }
            
            # Count total remaining posts
            if force_reanalyze:
                total_remaining = db.query(PostDB).count()
            else:
                total_remaining = db.query(PostDB).filter(
                    (PostDB.vision_analysis.is_(None)) | 
                    (PostDB.enhanced_category.is_(None))
                ).count()
            
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
                    
                    # Extract specific fields from analysis with safer enum mapping
                    vision_data = analysis_result.get('vision_analysis', {})
                    text_data = analysis_result.get('text_analysis', {})
                    business_insights = analysis_result.get('business_insights', {})
                    
                    post.has_screenshots = vision_data.get('has_images', 0)
                    
                    # Map AI analysis to valid enum values
                    urgency = text_data.get('urgency_level', 'none')
                    if urgency in ['critical', 'high', 'medium', 'low', 'none']:
                        post.problem_severity = urgency
                    else:
                        post.problem_severity = 'none'
                    
                    resolution = text_data.get('resolution_status', 'unanswered')
                    if resolution in ['resolved', 'in_progress', 'needs_help', 'unanswered']:
                        post.resolution_status = resolution
                    else:
                        post.resolution_status = 'unanswered'
                    
                    impact = business_insights.get('user_experience_impact', 'none')
                    if impact in ['productivity_loss', 'data_access_blocked', 'workflow_broken', 'feature_unavailable', 'minor_inconvenience', 'none']:
                        post.business_impact = impact
                    else:
                        post.business_impact = 'none'
                    
                    business_val = business_insights.get('business_value', 'low')
                    post.business_value = business_val
                    
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
                    
                    # Commit after each post to avoid losing work on timeout
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"Error analyzing post {post.id}: {e}")
                    errors.append(f"Post {post.id}: {str(e)}")
                    continue
            
            remaining_after_batch = total_remaining - analyzed_count
            
            return {
                "success": True,
                "message": f"Successfully analyzed {analyzed_count} posts",
                "batch_size": len(posts_to_analyze),
                "posts_analyzed": analyzed_count,
                "remaining_posts": max(0, remaining_after_batch),
                "progress_percent": round(((total_remaining - remaining_after_batch) / total_remaining * 100), 1) if total_remaining > 0 else 100,
                "errors": errors if errors else None,
                "continue_analysis": remaining_after_batch > 0,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.post("/analyze-next-batch")  
async def analyze_next_batch(batch_size: int = 3):
    """Continue analyzing posts in small batches to avoid timeouts"""
    return await analyze_all_posts_with_ai(batch_size)

@router.post("/force-reanalyze-posts")
async def force_reanalyze_all_posts(batch_size: int = 25):
    """Force re-analysis of all posts with real OpenAI API (replaces mock data)"""
    return await analyze_all_posts_with_ai(batch_size, force_reanalyze=True)

@router.post("/update-resolution-status")
async def update_resolution_status_for_existing_posts():
    """Update resolution_status field for existing posts based on has_accepted_solution"""
    try:
        from database.connection import get_session
        from database.models import PostDB
        from datetime import datetime
        
        logger.info("🔄 Starting resolution status update for existing posts")
        
        updated_count = 0
        with get_session() as db:
            # Get all posts that don't have resolution_status set
            posts_to_update = db.query(PostDB).filter(
                PostDB.resolution_status.is_(None)
            ).all()
            
            logger.info(f"📊 Found {len(posts_to_update)} posts without resolution status")
            
            for post in posts_to_update:
                # Set resolution status based on solution detection
                if post.has_accepted_solution:
                    post.resolution_status = 'resolved'
                elif post.total_replies and post.total_replies > 0:
                    post.resolution_status = 'in_progress'
                else:
                    post.resolution_status = 'unanswered'
                
                post.updated_at = datetime.now()
                updated_count += 1
            
            db.commit()
            logger.info(f"✅ Updated resolution status for {updated_count} posts")
        
        return {
            "success": True,
            "message": f"Updated resolution status for {updated_count} posts",
            "updated_count": updated_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to update resolution status: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.post("/add-ai-columns")
async def add_missing_ai_columns():
    """Add the specific AI summary columns that are missing"""
    try:
        logger.info("🔄 Adding missing AI summary columns")
        
        with engine.connect() as conn:
            trans = conn.begin()
            
            try:
                # Add the missing AI columns directly
                ai_columns = [
                    "ALTER TABLE posts ADD COLUMN ai_summary TEXT",
                    "ALTER TABLE posts ADD COLUMN ai_category VARCHAR(50)", 
                    "ALTER TABLE posts ADD COLUMN ai_key_points JSONB",
                    "ALTER TABLE posts ADD COLUMN ai_action_required VARCHAR(20)",
                    "ALTER TABLE posts ADD COLUMN ai_hashtags JSONB"
                ]
                
                added_columns = []
                errors = []
                
                for sql in ai_columns:
                    try:
                        conn.execute(text(sql))
                        column_name = sql.split("ADD COLUMN ")[1].split(" ")[0]
                        added_columns.append(column_name)
                        logger.info(f"Added AI column: {column_name}")
                    except Exception as col_error:
                        error_msg = str(col_error)
                        if "already exists" in error_msg:
                            column_name = sql.split("ADD COLUMN ")[1].split(" ")[0]
                            logger.info(f"Column {column_name} already exists")
                        else:
                            errors.append(f"Failed to add column: {error_msg}")
                            logger.error(f"Error adding column: {col_error}")
                
                trans.commit()
                
                return {
                    "success": True,
                    "message": "AI columns migration completed",
                    "added_columns": added_columns,
                    "errors": errors,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                trans.rollback()
                logger.error(f"AI columns migration failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.post("/migrate-database")
async def migrate_database_schema():
    """Run database migration to add missing columns"""
    try:
        from database.migrate import migrate_database
        import logging
        
        logger.info("🔄 Starting database migration")
        
        success = migrate_database()
        
        if success:
            return {
                "success": True,
                "message": "Database migration completed successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": "Database migration failed - check logs",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.post("/test-openai-call")
async def test_single_openai_call():
    """Test a single OpenAI API call to verify it works"""
    try:
        from services.enhanced_analyzer import EnhancedAnalyzer
        import logging
        
        logger.info("🧪 Testing single OpenAI API call")
        
        # Create analyzer instance
        analyzer = EnhancedAnalyzer()
        
        # Test with a simple post
        test_post = {
            'id': 'test_123',
            'title': 'Test OpenAI API Connection',
            'content': 'This is a test post to verify OpenAI API is working correctly.',
            'category': 'jira',
            'author': 'test_user'
        }
        
        # This should make a real API call if configured correctly
        result = await analyzer._analyze_text_enhanced(test_post)
        
        return {
            "success": True,
            "message": "OpenAI API call test completed",
            "test_result": {
                "result_type": "real_api" if not result.get('mock_analysis') else "mock_analysis",
                "api_response_keys": list(result.keys()),
                "has_mock_flag": result.get('mock_analysis', False)
            },
            "full_result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"OpenAI API test failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/openai-config-check")
async def check_openai_configuration():
    """Check OpenAI API configuration without exposing the key"""
    try:
        from config import settings
        from api.settings import is_vision_analysis_enabled, get_openai_api_key
        import os
        
        api_key = get_openai_api_key()
        config_api_key = settings.openai_api_key
        env_api_key = os.environ.get("OPENAI_API_KEY", "")
        
        return {
            "success": True,
            "openai_config": {
                "api_key_from_settings": bool(config_api_key),
                "api_key_length_settings": len(config_api_key) if config_api_key else 0,
                "api_key_from_env": bool(env_api_key),
                "api_key_length_env": len(env_api_key) if env_api_key else 0,
                "api_key_from_function": bool(api_key),
                "api_key_length_function": len(api_key) if api_key else 0,
                "vision_analysis_enabled": is_vision_analysis_enabled(),
                "api_key_prefix": api_key[:7] + "..." if api_key and len(api_key) > 10 else "NOT_SET",
                "environment_keys": list(os.environ.keys())[:10] # First 10 env vars
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking OpenAI config: {e}")
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

@router.post("/fix-empty-authors")
async def fix_empty_authors():
    """Fix posts with empty or null author fields by setting them to 'Anonymous'"""
    try:
        from database.connection import get_session
        from database.models import PostDB
        
        logger.info("🔄 Starting fix for posts with empty authors")
        
        updated_count = 0
        with get_session() as db:
            # Find posts with empty or null authors
            posts_with_empty_authors = db.query(PostDB).filter(
                (PostDB.author.is_(None)) | 
                (PostDB.author == '') |
                (PostDB.author == ' ')
            ).all()
            
            logger.info(f"📊 Found {len(posts_with_empty_authors)} posts with empty/null authors")
            
            for post in posts_with_empty_authors:
                old_author = post.author
                post.author = "Anonymous"
                post.updated_at = datetime.now()
                updated_count += 1
                logger.debug(f"Updated post {post.id}: '{old_author}' -> 'Anonymous'")
            
            db.commit()
            logger.info(f"✅ Fixed {updated_count} posts with empty authors")
        
        return {
            "success": True,
            "message": f"Fixed {updated_count} posts with empty authors",
            "updated_count": updated_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to fix empty authors: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.post("/extract-solutions-from-thread-data")
async def extract_solutions_from_existing_thread_data():
    """Extract has_accepted_solution from existing thread_data JSON without re-scraping"""
    try:
        from database.connection import get_session
        from database.models import PostDB
        import json
        
        logger.info("🔍 Checking for posts with thread_data...")
        
        updated_count = 0
        posts_with_thread_data = 0
        posts_with_solutions = 0
        
        with get_session() as db:
            # Find posts with thread_data
            all_posts = db.query(PostDB).all()
            
            for post in all_posts:
                if post.thread_data:
                    posts_with_thread_data += 1
                    try:
                        # Parse the JSON thread_data
                        thread_data = json.loads(post.thread_data)
                        
                        # Extract solution info
                        has_solution = thread_data.get('has_accepted_solution', False)
                        total_replies = thread_data.get('total_replies', 0)
                        
                        # Update the post if it has a solution but field not set
                        if has_solution and not post.has_accepted_solution:
                            post.has_accepted_solution = True
                            post.total_replies = total_replies
                            updated_count += 1
                            logger.info(f"✅ Updated post {post.id}: has_accepted_solution = True")
                        
                        if has_solution:
                            posts_with_solutions += 1
                            
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse thread_data for post {post.id}")
                        continue
            
            db.commit()
            logger.info(f"✅ Extraction complete! Updated {updated_count} posts")
        
        return {
            "success": True,
            "message": f"Extracted solution data from existing thread_data",
            "stats": {
                "total_posts": len(all_posts),
                "posts_with_thread_data": posts_with_thread_data,
                "posts_with_solutions_in_json": posts_with_solutions,
                "posts_updated": updated_count
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to extract solutions from thread_data: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }