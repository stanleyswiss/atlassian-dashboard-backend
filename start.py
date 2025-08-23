#!/usr/bin/env python3
"""
Railway deployment startup script
Handles database initialization and app startup
"""
import os
import sys
import asyncio
import logging
from database import create_tables
from main import app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Start the application with Railway-specific configurations"""
    logger.info("🚀 Starting Atlassian Dashboard Backend...")
    
    # Get environment variables
    port = int(os.environ.get("PORT", 8000))
    environment = os.environ.get("ENVIRONMENT", "development")
    
    logger.info(f"🌐 Environment: {environment}")
    logger.info(f"🔌 Port: {port}")
    
    # Initialize database
    try:
        logger.info("🗄️ Creating database tables...")
        create_tables()
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        # Don't exit - let the app try to start anyway
    
    # Start the server
    import uvicorn
    logger.info(f"🚀 Starting server on 0.0.0.0:{port}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0", 
        port=port,
        reload=False,
        workers=1,
        log_level="info"
    )

if __name__ == "__main__":
    main()