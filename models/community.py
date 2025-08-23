from datetime import datetime
from typing import Dict, List
from pydantic import BaseModel, Field

class ForumActivity(BaseModel):
    forum_name: str
    post_count: int = Field(ge=0)
    author_count: int = Field(ge=0)
    average_sentiment: float = Field(ge=-1.0, le=1.0)
    top_topics: List[str]
    activity_trend: str  # "increasing", "stable", "decreasing"

class CommunityHealth(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    factors: Dict[str, float]
    recommendations: List[str]
    last_calculated: datetime

class CommunityStats(BaseModel):
    total_posts: int = Field(ge=0)
    total_authors: int = Field(ge=0)
    active_forums: int = Field(ge=0)
    forum_breakdown: Dict[str, ForumActivity]
    community_health: CommunityHealth
    response_time_avg: float = Field(ge=0.0)  # hours
    engagement_rate: float = Field(ge=0.0, le=100.0)
    
class RecentActivity(BaseModel):
    posts_last_hour: int = Field(ge=0)
    posts_last_24h: int = Field(ge=0)
    posts_last_week: int = Field(ge=0)
    trending_topics: List[str]
    most_discussed_products: List[str]
    sentiment_shift: float = Field(ge=-100.0, le=100.0)