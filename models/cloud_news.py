from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from enum import Enum

class FeatureType(str, Enum):
    NEW_THIS_WEEK = "NEW_THIS_WEEK"
    COMING_SOON = "COMING_SOON"

class TargetAudience(str, Enum):
    ADMINISTRATORS = "administrators"
    END_USERS = "end_users"
    DEVELOPERS = "developers"
    ALL_USERS = "all_users"

class CloudNewsBase(BaseModel):
    source_url: str = Field(..., description="Source blog URL")
    blog_date: datetime = Field(..., description="Blog post date")
    blog_title: str = Field(..., description="Blog post title")
    feature_title: str = Field(..., description="Feature title")
    feature_content: str = Field(..., description="HTML content of the feature")
    feature_type: FeatureType = Field(..., description="Type of feature update")
    product_area: Optional[str] = Field(None, description="Product area (Jira, Confluence, etc.)")

class CloudNewsCreate(CloudNewsBase):
    pass

class CloudNewsUpdate(BaseModel):
    blog_date: Optional[datetime] = None
    blog_title: Optional[str] = None
    feature_title: Optional[str] = None
    feature_content: Optional[str] = None
    feature_type: Optional[FeatureType] = None
    product_area: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_impact_description: Optional[str] = None
    ai_target_audience: Optional[TargetAudience] = None
    ai_tags: Optional[List[str]] = None

class CloudNewsResponse(CloudNewsBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    ai_summary: Optional[str] = None
    ai_impact_description: Optional[str] = None
    ai_target_audience: Optional[TargetAudience] = None
    ai_tags: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

class CloudNewsSummary(BaseModel):
    """Summary view for dashboard"""
    id: int
    feature_title: str
    feature_type: FeatureType
    product_area: Optional[str] = None
    blog_date: datetime
    ai_summary: Optional[str] = None
    ai_target_audience: Optional[TargetAudience] = None

class CloudNewsFilters(BaseModel):
    feature_type: Optional[FeatureType] = None
    product_area: Optional[str] = None
    days_back: int = Field(default=7, ge=1, le=365, description="Number of days to look back")
    target_audience: Optional[TargetAudience] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)

class CloudNewsStats(BaseModel):
    """Statistics for Cloud News"""
    total_features: int
    new_this_week: int
    coming_soon: int
    product_breakdown: dict = Field(default_factory=dict)
    recent_updates: List[CloudNewsSummary]