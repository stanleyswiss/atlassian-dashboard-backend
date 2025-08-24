from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl

class SentimentLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

class PostCategory(str, Enum):
    JIRA = "jira"
    JSM = "jsm"
    CONFLUENCE = "confluence"
    ROVO = "rovo"
    ANNOUNCEMENTS = "announcements"

class EnhancedCategory(str, Enum):
    CRITICAL_ISSUE = "critical_issue"
    PROBLEM_WITH_EVIDENCE = "problem_with_evidence"
    PROBLEM_REPORT = "problem_report"
    SOLUTION_SHARING = "solution_sharing"
    AWESOME_USE_CASE = "awesome_use_case"
    FEATURE_REQUEST = "feature_request"
    CONFIGURATION_HELP = "configuration_help"
    ADVANCED_TECHNICAL = "advanced_technical"
    GENERAL_DISCUSSION = "general_discussion"
    UNCATEGORIZED = "uncategorized"

class ProblemSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    IN_PROGRESS = "in_progress" 
    NEEDS_HELP = "needs_help"
    UNANSWERED = "unanswered"

class BusinessImpact(str, Enum):
    PRODUCTIVITY_LOSS = "productivity_loss"
    DATA_ACCESS_BLOCKED = "data_access_blocked"
    WORKFLOW_BROKEN = "workflow_broken"
    FEATURE_UNAVAILABLE = "feature_unavailable"
    MINOR_INCONVENIENCE = "minor_inconvenience"
    NONE = "none"

class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    html_content: Optional[str] = Field(None)  # Original HTML with images preserved
    author: str = Field(..., min_length=1, max_length=100)
    category: PostCategory
    url: HttpUrl
    excerpt: str = Field(..., max_length=500)
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    sentiment_label: Optional[SentimentLabel] = None
    
    # Enhanced analysis fields
    enhanced_category: Optional[EnhancedCategory] = None
    has_screenshots: Optional[bool] = Field(default=False)
    vision_analysis: Optional[Dict[str, Any]] = Field(default=None)
    text_analysis: Optional[Dict[str, Any]] = Field(default=None)
    problem_severity: Optional[ProblemSeverity] = None
    resolution_status: Optional[ResolutionStatus] = None
    business_impact: Optional[BusinessImpact] = None
    business_value: Optional[str] = Field(None, max_length=50)
    extracted_issues: Optional[List[str]] = Field(default_factory=list)
    mentioned_products: Optional[List[str]] = Field(default_factory=list)

class PostCreate(PostBase):
    pass

class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=1)
    author: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[PostCategory] = None
    url: Optional[HttpUrl] = None
    excerpt: Optional[str] = Field(None, max_length=500)
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    sentiment_label: Optional[SentimentLabel] = None

class Post(PostBase):
    id: int
    date: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PostResponse(Post):
    pass