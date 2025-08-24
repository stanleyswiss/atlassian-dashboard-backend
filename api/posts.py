from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import json

from database import get_db, PostOperations
from models import PostResponse, PostCreate, PostUpdate, SentimentLabel, PostCategory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/posts", tags=["posts"])

def convert_db_post_to_response(post) -> PostResponse:
    """Convert database post model to response model, parsing JSON fields"""
    
    # Parse JSON fields if they exist
    vision_analysis = None
    if post.vision_analysis:
        try:
            vision_analysis = json.loads(post.vision_analysis) if isinstance(post.vision_analysis, str) else post.vision_analysis
        except (json.JSONDecodeError, TypeError):
            vision_analysis = {}
    
    text_analysis = None
    if post.text_analysis:
        try:
            text_analysis = json.loads(post.text_analysis) if isinstance(post.text_analysis, str) else post.text_analysis
        except (json.JSONDecodeError, TypeError):
            text_analysis = {}
    
    extracted_issues = []
    if post.extracted_issues:
        try:
            extracted_issues = json.loads(post.extracted_issues) if isinstance(post.extracted_issues, str) else post.extracted_issues
        except (json.JSONDecodeError, TypeError):
            extracted_issues = []
    
    mentioned_products = []
    if post.mentioned_products:
        try:
            mentioned_products = json.loads(post.mentioned_products) if isinstance(post.mentioned_products, str) else post.mentioned_products
        except (json.JSONDecodeError, TypeError):
            mentioned_products = []
    
    # Create response model with parsed JSON
    post_dict = {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "author": post.author,
        "category": post.category,
        "url": post.url,
        "excerpt": post.excerpt,
        "date": post.date,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
        "sentiment_score": post.sentiment_score,
        "sentiment_label": post.sentiment_label,
        "enhanced_category": post.enhanced_category,
        "has_screenshots": bool(post.has_screenshots) if post.has_screenshots is not None else False,
        "vision_analysis": vision_analysis,
        "text_analysis": text_analysis,
        "problem_severity": post.problem_severity,
        "resolution_status": post.resolution_status,
        "business_impact": post.business_impact,
        "business_value": post.business_value,
        "extracted_issues": extracted_issues,
        "mentioned_products": mentioned_products,
    }
    
    return PostResponse(**post_dict)

@router.get("/", response_model=List[PostResponse])
async def get_posts(
    skip: int = Query(0, ge=0, description="Number of posts to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of posts to return"),
    category: Optional[str] = Query(None, description="Filter by category (jira, jsm, confluence, rovo, announcements)"),
    author: Optional[str] = Query(None, description="Filter by author name (partial match)"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment (positive, negative, neutral)"),
    db: Session = Depends(get_db)
):
    """Get posts with filtering and pagination"""
    try:
        # Validate category if provided
        if category and category not in [cat.value for cat in PostCategory]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid category. Must be one of: {[cat.value for cat in PostCategory]}"
            )
            
        # Validate sentiment if provided  
        if sentiment and sentiment not in [sent.value for sent in SentimentLabel]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sentiment. Must be one of: {[sent.value for sent in SentimentLabel]}"
            )
        
        posts = PostOperations.get_posts(
            db=db,
            skip=skip,
            limit=limit,
            category=category,
            author=author,
            sentiment=sentiment
        )
        
        return [convert_db_post_to_response(post) for post in posts]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get posts")

@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: Session = Depends(get_db)):
    """Get a single post by ID"""
    try:
        post = PostOperations.get_post(db, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
            
        return convert_db_post_to_response(post)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get post")

@router.post("/", response_model=PostResponse)
async def create_post(post: PostCreate, db: Session = Depends(get_db)):
    """Create a new post"""
    try:
        # Check if post with same URL already exists
        from database.models import PostDB
        existing_post = db.query(PostDB).filter(PostDB.url == str(post.url)).first()
        if existing_post:
            raise HTTPException(
                status_code=409, 
                detail="Post with this URL already exists"
            )
        
        db_post = PostOperations.create_post(db, post)
        return PostResponse.model_validate(db_post)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating post: {e}")
        raise HTTPException(status_code=500, detail="Failed to create post")

@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int, 
    post_update: PostUpdate, 
    db: Session = Depends(get_db)
):
    """Update an existing post"""
    try:
        # Check if post exists
        existing_post = PostOperations.get_post(db, post_id)
        if not existing_post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        # Check for URL conflicts if URL is being updated
        if post_update.url:
            from database.models import PostDB
            url_conflict = db.query(PostDB).filter(
                PostDB.url == str(post_update.url),
                PostDB.id != post_id
            ).first()
            if url_conflict:
                raise HTTPException(
                    status_code=409,
                    detail="Another post with this URL already exists"
                )
        
        updated_post = PostOperations.update_post(db, post_id, post_update)
        if not updated_post:
            raise HTTPException(status_code=404, detail="Post not found")
            
        return PostResponse.model_validate(updated_post)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update post")

@router.delete("/{post_id}")
async def delete_post(post_id: int, db: Session = Depends(get_db)):
    """Delete a post"""
    try:
        success = PostOperations.delete_post(db, post_id)
        if not success:
            raise HTTPException(status_code=404, detail="Post not found")
            
        return {"message": "Post deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete post")

@router.get("/search/by-content")
async def search_posts_by_content(
    query: str = Query(..., min_length=3, description="Search query (minimum 3 characters)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Search posts by title and content"""
    try:
        from database.models import PostDB
        from sqlalchemy import or_, func
        
        # Search in title and content
        search_filter = or_(
            PostDB.title.contains(query),
            PostDB.content.contains(query)
        )
        
        posts = db.query(PostDB).filter(search_filter)\
                  .order_by(PostDB.date.desc())\
                  .offset(skip)\
                  .limit(limit)\
                  .all()
        
        return [PostResponse.model_validate(post) for post in posts]
        
    except Exception as e:
        logger.error(f"Error searching posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to search posts")

@router.get("/stats/summary")
async def get_posts_summary(db: Session = Depends(get_db)):
    """Get summary statistics for posts"""
    try:
        from database.models import PostDB
        from sqlalchemy import func
        from collections import Counter
        
        # Total counts
        total_posts = db.query(PostDB).count()
        total_authors = db.query(func.count(func.distinct(PostDB.author))).scalar()
        
        # Category breakdown
        category_counts = db.query(PostDB.category, func.count(PostDB.id))\
                           .group_by(PostDB.category)\
                           .all()
        category_breakdown = {category: count for category, count in category_counts}
        
        # Sentiment breakdown
        sentiment_counts = db.query(PostDB.sentiment_label, func.count(PostDB.id))\
                            .filter(PostDB.sentiment_label.isnot(None))\
                            .group_by(PostDB.sentiment_label)\
                            .all()
        sentiment_breakdown = {sentiment: count for sentiment, count in sentiment_counts}
        
        # Average sentiment score
        avg_sentiment = db.query(func.avg(PostDB.sentiment_score))\
                          .filter(PostDB.sentiment_score.isnot(None))\
                          .scalar()
        
        # Top authors
        top_authors = db.query(PostDB.author, func.count(PostDB.id))\
                       .group_by(PostDB.author)\
                       .order_by(func.count(PostDB.id).desc())\
                       .limit(10)\
                       .all()
        
        return {
            "total_posts": total_posts,
            "total_authors": total_authors,
            "category_breakdown": category_breakdown,
            "sentiment_breakdown": sentiment_breakdown,
            "average_sentiment": round(float(avg_sentiment or 0), 2),
            "top_authors": [{"author": author, "post_count": count} for author, count in top_authors]
        }
        
    except Exception as e:
        logger.error(f"Error getting posts summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get posts summary")

@router.get("/categories/", response_model=List[str])
async def get_available_categories():
    """Get list of available post categories"""
    return [category.value for category in PostCategory]

@router.get("/sentiments/", response_model=List[str]) 
async def get_available_sentiments():
    """Get list of available sentiment labels"""
    return [sentiment.value for sentiment in SentimentLabel]