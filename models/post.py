from datetime import datetime
from typing import Optional
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

class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    author: str = Field(..., min_length=1, max_length=100)
    category: PostCategory
    url: HttpUrl
    excerpt: str = Field(..., max_length=500)
    sentiment_score: Optional[float] = Field(None, ge=-1.0, le=1.0)
    sentiment_label: Optional[SentimentLabel] = None

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