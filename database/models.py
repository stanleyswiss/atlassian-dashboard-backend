from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Date, Boolean, UniqueConstraint
from sqlalchemy.sql import func
from datetime import datetime
from .connection import Base

class PostDB(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False, index=True)
    content = Column(Text, nullable=False)
    html_content = Column(Text, nullable=True)  # Preserves original HTML with images
    author = Column(String(100), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # jira, jsm, confluence, rovo, announcements
    url = Column(String(1000), nullable=False, unique=True)
    excerpt = Column(String(500), nullable=False)
    date = Column(DateTime, nullable=False, index=True)
    
    # Sentiment analysis fields (legacy)
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    sentiment_label = Column(String(20), nullable=True, index=True)  # positive, negative, neutral
    
    # Enhanced analysis fields
    enhanced_category = Column(String(50), nullable=True, index=True)  # critical_issue, solution_sharing, etc.
    has_screenshots = Column(Integer, nullable=True, default=0)  # 0/1 boolean (as INTEGER)
    vision_analysis = Column(Text, nullable=True)  # JSON stored as TEXT for compatibility
    text_analysis = Column(Text, nullable=True)  # JSON stored as TEXT for compatibility
    problem_severity = Column(String(20), nullable=True, index=True)  # critical, high, medium, low, none
    resolution_status = Column(String(20), nullable=True, index=True)  # resolved, in_progress, needs_help, unanswered
    business_impact = Column(String(30), nullable=True, index=True)  # productivity_loss, workflow_broken, etc.
    business_value = Column(Integer, nullable=True, default=0)  # Use INTEGER to match current schema
    extracted_issues = Column(Text, nullable=True)  # JSON stored as TEXT for compatibility
    mentioned_products = Column(Text, nullable=True)  # JSON stored as TEXT for compatibility
    
    # Thread/discussion data
    thread_data = Column(Text, nullable=True)  # JSON with replies, solution status, participants
    has_accepted_solution = Column(Boolean, default=False)  # Quick flag for solution status
    total_replies = Column(Integer, default=0)  # Number of replies in thread
    
    # AI-generated summary fields
    ai_summary = Column(Text, nullable=True)  # AI-generated concise summary
    ai_category = Column(String(50), nullable=True)  # AI-determined category
    ai_key_points = Column(Text, nullable=True)  # JSON array of key points
    ai_action_required = Column(String(20), nullable=True)  # high, medium, low, none
    ai_hashtags = Column(Text, nullable=True)  # JSON array of hashtags
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class SettingsDB(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True, index=True)
    value = Column(Text, nullable=False)  # JSON stored as text
    value_type = Column(String(20), nullable=False, default='string')  # string, integer, boolean, json
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class AnalyticsDB(Base):
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    
    # Basic metrics
    total_posts = Column(Integer, nullable=False, default=0)
    total_authors = Column(Integer, nullable=False, default=0)
    
    # Sentiment breakdown (JSON stored as TEXT)
    sentiment_breakdown = Column(Text, nullable=False, default='{}')  # {"positive": 10, "negative": 5, "neutral": 15}
    
    # Top topics and categories
    top_topics = Column(Text, nullable=False, default='[]')  # ["bug", "feature request", "question"]
    most_active_category = Column(String(50), nullable=False)
    
    # Calculated scores
    average_sentiment = Column(Float, nullable=False, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class TrendDB(Base):
    __tablename__ = "trends"
    
    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String(200), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Trend metrics
    count = Column(Integer, nullable=False, default=0)
    sentiment_average = Column(Float, nullable=False, default=0.0)
    trending_score = Column(Float, nullable=False, default=0.0)
    
    # Categories where this topic appears
    categories = Column(Text, nullable=False, default='[]')  # ["jira", "confluence"]
    
    # Timestamps
    last_seen = Column(DateTime, nullable=False, default=func.now())
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class ReleaseNoteDB(Base):
    __tablename__ = "release_notes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Product information
    product_name = Column(String(200), nullable=False, index=True)  # "Jira", "Confluence", "ScriptRunner for Jira", etc.
    product_type = Column(String(50), nullable=False, index=True)  # "atlassian_product", "marketplace_app"
    product_id = Column(String(50), nullable=True, index=True)  # App ID for marketplace apps
    
    # Version information
    version = Column(String(100), nullable=False, index=True)
    build_number = Column(String(50), nullable=True)
    release_date = Column(DateTime, nullable=False, index=True)
    
    # Release details
    release_summary = Column(Text, nullable=True)
    release_notes = Column(Text, nullable=True)  # HTML content of release notes
    release_notes_url = Column(String(1000), nullable=True)
    download_url = Column(String(1000), nullable=True)
    
    # Analysis fields
    ai_summary = Column(Text, nullable=True)  # AI-generated summary
    ai_key_changes = Column(Text, nullable=True)  # JSON array of key changes
    ai_impact_level = Column(String(20), nullable=True)  # high, medium, low
    ai_categories = Column(Text, nullable=True)  # JSON array ["bug_fix", "new_feature", "security"]
    
    # Filtering helpers
    is_major_release = Column(Boolean, default=False)
    is_security_release = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class CloudNewsDB(Base):
    __tablename__ = "cloud_news"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source information
    source_url = Column(String(1000), nullable=False)
    blog_date = Column(DateTime, nullable=False, index=True)
    blog_title = Column(String(500), nullable=False)
    
    # Feature information
    feature_title = Column(String(300), nullable=False, index=True)
    feature_content = Column(Text, nullable=False)  # HTML content
    feature_type = Column(String(20), nullable=False, index=True)  # "NEW_THIS_WEEK", "COMING_SOON"
    product_area = Column(String(100), nullable=True, index=True)  # "Jira", "Confluence", "Bitbucket", etc.
    
    # Analysis fields
    ai_summary = Column(Text, nullable=True)
    ai_impact_description = Column(Text, nullable=True)
    ai_target_audience = Column(String(100), nullable=True)  # "administrators", "end_users", "developers"
    ai_tags = Column(Text, nullable=True)  # JSON array of tags
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Composite unique constraint on source_url + feature_title to allow multiple features per URL
    __table_args__ = (
        UniqueConstraint('source_url', 'feature_title', name='unique_source_feature'),
    )