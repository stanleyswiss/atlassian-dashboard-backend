from datetime import datetime, date
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class SentimentTrend(BaseModel):
    date: date
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    neutral_count: int = Field(ge=0)
    average_sentiment: float = Field(ge=-1.0, le=1.0)

class TopicTrend(BaseModel):
    topic: str
    count: int = Field(ge=0)
    sentiment_average: float = Field(ge=-1.0, le=1.0)
    trending_score: float = Field(ge=0.0)
    last_seen: datetime

class AnalyticsBase(BaseModel):
    date: date
    total_posts: int = Field(ge=0)
    total_authors: int = Field(ge=0)
    sentiment_breakdown: Dict[str, int]
    top_topics: List[str]
    most_active_category: str
    average_sentiment: float = Field(ge=-1.0, le=1.0)

class Analytics(AnalyticsBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AnalyticsResponse(BaseModel):
    daily_stats: Analytics
    sentiment_trends: List[SentimentTrend]
    trending_topics: List[TopicTrend]
    
class DashboardOverview(BaseModel):
    total_posts_today: int
    total_posts_week: int
    community_health_score: float = Field(ge=0.0, le=100.0)
    most_active_forum: str
    sentiment_breakdown: Dict[str, float]
    recent_activity_change: float
    top_issues: List[str]