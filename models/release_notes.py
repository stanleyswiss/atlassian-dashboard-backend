from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from enum import Enum

class ProductType(str, Enum):
    ATLASSIAN_PRODUCT = "atlassian_product"
    MARKETPLACE_APP = "marketplace_app"

class ImpactLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ReleaseCategory(str, Enum):
    BUG_FIX = "bug_fix"
    NEW_FEATURE = "new_feature"
    ENHANCEMENT = "enhancement"
    SECURITY = "security"
    DEPRECATION = "deprecation"
    PERFORMANCE = "performance"

class ReleaseNoteBase(BaseModel):
    product_name: str = Field(..., description="Name of the product")
    product_type: ProductType = Field(..., description="Type of product")
    product_id: Optional[str] = Field(None, description="Product ID for marketplace apps")
    version: str = Field(..., description="Version number")
    build_number: Optional[str] = Field(None, description="Build number")
    release_date: datetime = Field(..., description="Release date")
    release_summary: Optional[str] = Field(None, description="Release summary")
    release_notes: Optional[str] = Field(None, description="HTML content of release notes")
    release_notes_url: Optional[str] = Field(None, description="URL to release notes")
    download_url: Optional[str] = Field(None, description="Download URL")
    is_major_release: bool = Field(default=False, description="Is this a major release")
    is_security_release: bool = Field(default=False, description="Is this a security release")

class ReleaseNoteCreate(ReleaseNoteBase):
    pass

class ReleaseNoteUpdate(BaseModel):
    product_name: Optional[str] = None
    version: Optional[str] = None
    build_number: Optional[str] = None
    release_date: Optional[datetime] = None
    release_summary: Optional[str] = None
    release_notes: Optional[str] = None
    release_notes_url: Optional[str] = None
    download_url: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_key_changes: Optional[List[str]] = None
    ai_impact_level: Optional[ImpactLevel] = None
    ai_categories: Optional[List[ReleaseCategory]] = None
    is_major_release: Optional[bool] = None
    is_security_release: Optional[bool] = None

class ReleaseNoteResponse(ReleaseNoteBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    ai_summary: Optional[str] = None
    ai_key_changes: Optional[List[str]] = None
    ai_impact_level: Optional[ImpactLevel] = None
    ai_categories: Optional[List[ReleaseCategory]] = None
    created_at: datetime
    updated_at: datetime

class ReleaseNoteSummary(BaseModel):
    """Summary view for dashboard"""
    id: int
    product_name: str
    product_type: ProductType
    version: str
    release_date: datetime
    ai_summary: Optional[str] = None
    ai_impact_level: Optional[ImpactLevel] = None
    is_major_release: bool
    is_security_release: bool

class ReleaseNoteFilters(BaseModel):
    product_type: Optional[ProductType] = None
    product_name: Optional[str] = None
    days_back: int = Field(default=7, ge=1, le=365, description="Number of days to look back")
    major_releases_only: bool = Field(default=False, description="Only show major releases")
    security_releases_only: bool = Field(default=False, description="Only show security releases")
    impact_level: Optional[ImpactLevel] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)