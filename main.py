from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from config import settings
from database import create_tables
from api import dashboard_router, posts_router, analytics_router
from api.scraping import router as scraping_router
from api.settings import router as settings_router

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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "atlassian-dashboard-api",
        "version": "1.0.0",
        "database": "connected"
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
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )