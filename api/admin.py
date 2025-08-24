from fastapi import APIRouter, HTTPException
from sqlalchemy import text, inspect
from database.connection import engine, get_database_url
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.post("/migrate-database")
async def migrate_database():
    """Add missing enhanced analysis columns to database"""
    
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
                "has_screenshots": "BOOLEAN DEFAULT FALSE",
                "vision_analysis": "TEXT",
                "text_analysis": "TEXT", 
                "problem_severity": "VARCHAR(20)",
                "resolution_status": "VARCHAR(30)",
                "business_impact": "VARCHAR(20)",
                "business_value": "INTEGER DEFAULT 0",
                "extracted_issues": "TEXT",
                "mentioned_products": "TEXT"
            }
        else:
            # SQLite
            new_columns_map = {
                "enhanced_category": "VARCHAR(50)",
                "has_screenshots": "BOOLEAN DEFAULT 0",
                "vision_analysis": "TEXT",
                "text_analysis": "TEXT",
                "problem_severity": "VARCHAR(20)", 
                "resolution_status": "VARCHAR(30)",
                "business_impact": "VARCHAR(20)",
                "business_value": "INTEGER DEFAULT 0",
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
                
                # Commit transaction
                trans.commit()
                
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
                logger.error(f"Migration failed: {e}")
                raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")
                
    except Exception as e:
        logger.error(f"Database migration error: {e}")
        raise HTTPException(status_code=500, detail=f"Database migration failed: {str(e)}")

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