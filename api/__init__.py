from .dashboard import router as dashboard_router
from .posts import router as posts_router
from .analytics import router as analytics_router

__all__ = [
    "dashboard_router",
    "posts_router", 
    "analytics_router"
]