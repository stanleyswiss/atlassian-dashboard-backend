from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import logging
from config import settings
from database import create_tables
from api import dashboard_router, posts_router, analytics_router
from api.scraping import router as scraping_router
from api.settings import router as settings_router
from api.content_intelligence import router as intelligence_router
from api.business_intelligence import router as bi_router
from api.admin import router as admin_router
from api.roadmap import router as roadmap_router
from api.forums import router as forums_router
from api.diagnostic import router as diagnostic_router
from scheduler import start_scheduler, stop_scheduler, get_scheduler_status

logger = logging.getLogger(__name__)

# Create database tables on startup
create_tables()

app = FastAPI(
    title="Atlassian Community Dashboard API",
    description="API for monitoring Atlassian Community activity with sentiment analysis and trending topics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(dashboard_router)
app.include_router(posts_router)
app.include_router(analytics_router)
app.include_router(scraping_router)
app.include_router(settings_router)
app.include_router(intelligence_router)
app.include_router(bi_router)
app.include_router(admin_router)
app.include_router(roadmap_router)
app.include_router(forums_router)
app.include_router(diagnostic_router)

@app.on_event("startup")
async def startup_event():
    """Initialize and start the background scheduler"""
    logger.info("🚀 Starting Atlassian Dashboard API...")
    try:
        # Start the background scheduler for automated scraping
        logger.info("📅 Starting background scheduler...")
        asyncio.create_task(start_scheduler())
        logger.info("✅ Background scheduler started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Gracefully shutdown the scheduler"""
    logger.info("🛑 Shutting down Atlassian Dashboard API...")
    try:
        await stop_scheduler()
        logger.info("✅ Scheduler stopped gracefully")
    except Exception as e:
        logger.error(f"❌ Error stopping scheduler: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint with scheduler status"""
    scheduler_status = get_scheduler_status()
    return {
        "status": "healthy",
        "service": "atlassian-dashboard-api",
        "version": "1.0.0",
        "database": "connected",
        "scheduler": scheduler_status
    }

@app.get("/scheduler/status")
async def scheduler_status():
    """Get current scheduler status"""
    return {
        "success": True,
        "scheduler": get_scheduler_status(),
        "message": "Scheduler status retrieved successfully"
    }

@app.get("/")
async def root():
    """API root endpoint with navigation"""
    return {
        "message": "Welcome to Atlassian Community Dashboard API",
        "version": "1.0.0",
        "endpoints": {
            "documentation": "/docs",
            "health_check": "/health",
            "dashboard_overview": "/api/dashboard/overview",
            "recent_posts": "/api/dashboard/recent-posts",
            "trending_topics": "/api/dashboard/trending-topics",
            "posts": "/api/posts/",
            "analytics": "/api/analytics/",
            "settings": "/api/settings",
            "scraping": "/api/scraping/"
        },
        "features": [
            "Community post scraping",
            "AI-powered sentiment analysis", 
            "Trending topic detection",
            "Daily analytics generation",
            "Real-time dashboard data"
        ]
    }

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False  # Disable reload in production
    )