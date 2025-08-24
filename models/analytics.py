from datetime import datetime, date
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from models.post import EnhancedCategory, ProblemSeverity, BusinessImpact

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

# Enhanced Business Intelligence Models

class CriticalIssue(BaseModel):
    issue_title: str
    severity: ProblemSeverity
    report_count: int = Field(ge=1)
    affected_products: List[str]
    first_reported: datetime
    latest_report: datetime
    business_impact: BusinessImpact
    sample_posts: List[Dict[str, str]]
    resolution_urgency: str = Field(default="immediate")

class AwesomeDiscovery(BaseModel):
    title: str
    summary: str
    author: str
    url: str
    products_used: List[str]
    technical_level: str
    has_screenshots: bool = Field(default=False)
    engagement_potential: str = Field(default="medium")
    discovery_type: str = Field(default="use_case")

class TrendingSolution(BaseModel):
    solution_title: str
    problem_solved: str
    solution_type: str
    author: str
    url: str
    products_affected: List[str]
    technical_level: str
    has_visual_guide: bool = Field(default=False)
    effectiveness_score: int = Field(ge=0, le=10)
    popularity_trend: str = Field(default="stable")

class UnresolvedProblem(BaseModel):
    problem_title: str
    urgency: ProblemSeverity
    days_unresolved: int = Field(ge=0)
    author: str
    url: str
    affected_products: List[str]
    problem_type: str
    has_screenshots: bool = Field(default=False)
    business_impact: BusinessImpact
    help_potential: str = Field(default="medium")

class FeatureRequest(BaseModel):
    feature_title: str
    requested_for: List[str]  # Products
    user_value: str
    implementation_complexity: str
    author: str
    url: str
    similar_requests: int = Field(ge=1, default=1)
    business_justification: str
    priority_score: int = Field(ge=0, le=10, default=5)

class BusinessIntelligence(BaseModel):
    generated_at: datetime
    time_period: str
    total_posts_analyzed: int
    
    # Executive Summary
    executive_summary: Dict[str, Any]
    
    # Key Categories
    critical_issues: List[CriticalIssue]
    awesome_discoveries: List[AwesomeDiscovery]
    trending_solutions: List[TrendingSolution]
    unresolved_problems: List[UnresolvedProblem]
    feature_requests: List[FeatureRequest]
    
    # Business Metrics
    business_metrics: Dict[str, Any]
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list)

class CommunityHealthMetrics(BaseModel):
    overall_health_score: int = Field(ge=0, le=100)
    critical_issue_rate: float = Field(ge=0.0, le=100.0)
    solution_sharing_rate: float = Field(ge=0.0, le=100.0)
    problem_resolution_rate: float = Field(ge=0.0, le=100.0)
    user_satisfaction_trend: str = Field(default="stable")
    
    # Category breakdown
    category_distribution: Dict[EnhancedCategory, int]
    
    # Product health
    product_health_scores: Dict[str, int]  # Per Atlassian product
    
    # Trends
    weekly_trend: str = Field(default="stable")  # improving, declining, stable
    engagement_trend: str = Field(default="stable")

class BusinessInsight(BaseModel):
    insight_type: str  # "opportunity", "risk", "trend", "recommendation"
    title: str
    description: str
    priority: str = Field(default="medium")  # high, medium, low
    affected_products: List[str]
    supporting_data: Dict[str, Any]
    action_items: List[str] = Field(default_factory=list)
    
class EnhancedDashboardOverview(DashboardOverview):
    # Enhanced fields for business intelligence
    critical_issues_count: int = Field(ge=0, default=0)
    awesome_discoveries_count: int = Field(ge=0, default=0)
    trending_solutions_count: int = Field(ge=0, default=0)
    unresolved_problems_count: int = Field(ge=0, default=0)
    
    # Business health indicators
    community_health_metrics: CommunityHealthMetrics
    top_business_insights: List[BusinessInsight] = Field(default_factory=list)
    
    # Vision AI summary
    posts_with_screenshots: int = Field(ge=0, default=0)
    vision_analysis_coverage: float = Field(ge=0.0, le=100.0, default=0.0)