from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import json
from datetime import datetime

from database import get_db, PostOperations
from models import PostResponse, PostCreate, PostUpdate, SentimentLabel, PostCategory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/posts", tags=["posts"])

def convert_db_post_to_response(post) -> PostResponse:
    """Convert database post model to response model, parsing JSON fields"""
    
    def safe_json_parse(value, default):
        """Safely parse JSON string, return default on error"""
        if value is None:
            return default
        if not value:  # Empty string, 0, False, etc.
            return default
        if not isinstance(value, str):
            return value if value is not None else default
        if value.strip() == '':  # Empty or whitespace-only string
            return default
        try:
            parsed = json.loads(value)
            # If it's an empty dict/list that got stored somehow, return default
            if parsed == {} and isinstance(default, list):
                return default
            if parsed == [] and isinstance(default, dict):
                return default
            return parsed
        except (json.JSONDecodeError, TypeError, ValueError, AttributeError) as e:
            logger.warning(f"JSON parse error for value '{value}': {e}")
            return default
    
    # Parse JSON fields safely and quickly
    vision_analysis = safe_json_parse(post.vision_analysis, {})
    text_analysis = safe_json_parse(post.text_analysis, {})
    extracted_issues = safe_json_parse(post.extracted_issues, [])
    mentioned_products = safe_json_parse(post.mentioned_products, [])
    
    # Map invalid enum values to valid ones
    def map_enum_value(value, valid_values, default):
        """Map potentially invalid enum values to valid ones"""
        if not value or value not in valid_values:
            return default
        return value
    
    # Valid enum values (must match the enums in models/post.py)
    valid_problem_severity = ['critical', 'high', 'medium', 'low', 'none']
    valid_resolution_status = ['resolved', 'in_progress', 'needs_help', 'unanswered']
    valid_business_impact = ['productivity_loss', 'data_access_blocked', 'workflow_broken', 'feature_unavailable', 'minor_inconvenience', 'none']
    
    # Create response model with parsed JSON and valid enum values
    post_dict = {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "author": post.author if post.author and post.author.strip() else "Anonymous",
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
        "problem_severity": map_enum_value(post.problem_severity, valid_problem_severity, 'none'),
        "resolution_status": map_enum_value(post.resolution_status, valid_resolution_status, 'unanswered'),
        "business_impact": map_enum_value(post.business_impact, valid_business_impact, 'none'),
        "business_value": post.business_value,
        "extracted_issues": extracted_issues,
        "mentioned_products": mentioned_products,
    }
    
    return PostResponse(**post_dict)

@router.get("/debug/count")
async def debug_posts_count(db: Session = Depends(get_db)):
    """Super simple debug endpoint to test database connection"""
    try:
        from database.models import PostDB
        count = db.query(PostDB).count()
        return {
            "success": True,
            "total_posts": count,
            "message": "Database connection working"
        }
    except Exception as e:
        logger.error(f"Debug count error: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@router.get("/debug/convert")
async def debug_post_conversion(limit: int = 3, db: Session = Depends(get_db)):
    """Debug endpoint to test PostResponse conversion"""
    try:
        posts = PostOperations.get_posts(db=db, limit=limit)
        
        converted_posts = []
        errors = []
        
        for i, post in enumerate(posts):
            try:
                logger.info(f"Converting post {post.id}")
                converted_post = convert_db_post_to_response(post)
                converted_posts.append({
                    "id": converted_post.id,
                    "title": converted_post.title[:50] + "..." if len(converted_post.title) > 50 else converted_post.title,
                    "category": converted_post.category,
                    "enhanced_category": converted_post.enhanced_category,
                    "has_vision": bool(converted_post.vision_analysis),
                    "has_text": bool(converted_post.text_analysis),
                    "status": "success"
                })
            except Exception as e:
                logger.error(f"Error converting post {post.id}: {e}")
                import traceback
                error_info = {
                    "post_id": post.id,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "raw_vision_type": type(post.vision_analysis).__name__,
                    "raw_text_type": type(post.text_analysis).__name__,
                }
                errors.append(error_info)
                
        return {
            "success": True,
            "converted_count": len(converted_posts),
            "error_count": len(errors),
            "converted_posts": converted_posts,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Debug conversion error: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@router.get("/debug/raw")
async def debug_raw_posts(limit: int = 5, db: Session = Depends(get_db)):
    """Debug endpoint to see raw database data"""
    try:
        posts = PostOperations.get_posts(db=db, limit=limit)
        
        # Return raw data without model validation
        raw_posts = []
        for post in posts:
            raw_data = {
                "id": post.id,
                "title": post.title,
                "content": post.content[:100] + "..." if len(post.content) > 100 else post.content,
                "author": post.author if post.author and post.author.strip() else "Anonymous",
                "category": post.category,
                "url": post.url,
                "created_at": str(post.created_at),
                "vision_analysis_type": type(post.vision_analysis).__name__,
                "vision_analysis_value": str(post.vision_analysis)[:100] if post.vision_analysis else None,
                "text_analysis_type": type(post.text_analysis).__name__,
                "text_analysis_value": str(post.text_analysis)[:100] if post.text_analysis else None,
                "enhanced_category": post.enhanced_category,
                "has_screenshots": post.has_screenshots,
                "problem_severity": post.problem_severity,
            }
            raw_posts.append(raw_data)
        
        return {
            "success": True,
            "posts_count": len(raw_posts),
            "raw_posts": raw_posts
        }
        
    except Exception as e:
        logger.error(f"Debug endpoint error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

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
        logger.info(f"Getting posts: skip={skip}, limit={limit}, category={category}")
        start_time = datetime.now()
        
        # Limit to prevent timeouts
        safe_limit = min(limit, 50)  # Cap at 50 for now
        logger.info(f"Using safe_limit: {safe_limit}")
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
            limit=safe_limit,  # Use safe limit
            category=category,
            author=author,
            sentiment=sentiment
        )
        
        logger.info(f"Retrieved {len(posts)} posts from database")
        
        # Convert posts with timing and error handling
        response_posts = []
        for i, post in enumerate(posts):
            try:
                response_posts.append(convert_db_post_to_response(post))
            except Exception as conv_error:
                logger.error(f"Error converting post {i} (id: {getattr(post, 'id', 'unknown')}): {conv_error}")
                # Skip this post and continue
                continue
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Posts API completed in {duration:.2f} seconds")
        
        return response_posts
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get posts")

@router.get("/with-summaries")
async def get_posts_with_ai_summaries(
    skip: int = Query(0, ge=0, description="Number of posts to skip"),
    limit: int = Query(20, ge=1, le=50, description="Number of posts to return (max 50 for AI processing)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment"),
    db: Session = Depends(get_db)
):
    """Get posts with AI-generated summaries instead of full content"""
    try:
        from services.ai_analyzer import AIAnalyzer
        
        logger.info(f"Getting posts with AI summaries: skip={skip}, limit={limit}")
        
        # Validate parameters
        if category and category not in [cat.value for cat in PostCategory]:
            raise HTTPException(status_code=400, detail=f"Invalid category")
            
        if sentiment and sentiment not in [sent.value for sent in SentimentLabel]:
            raise HTTPException(status_code=400, detail=f"Invalid sentiment")
        
        # Get posts from database
        posts = PostOperations.get_posts(
            db=db,
            skip=skip,
            limit=limit,
            category=category,
            sentiment=sentiment
        )
        
        if not posts:
            return []
        
        # Convert posts to response format, using cached AI summaries when available
        enhanced_posts = []
        posts_needing_ai = []
        
        for post in posts:
            try:
                # Check if post already has AI summary cached
                if post.ai_summary:
                    # Use cached AI data
                    import json
                    def safe_json_parse(value, default):
                        if not value:
                            return default
                        try:
                            return json.loads(value) if isinstance(value, str) else value
                        except:
                            return default
                    
                    enhanced_post = {
                        'id': post.id,
                        'title': post.title or '',
                        'content': post.content or '',
                        'author': post.author or '',
                        'category': post.category or '',
                        'url': str(post.url) if post.url else '',
                        'date': post.date.isoformat() if post.date else None,
                        'sentiment_score': post.sentiment_score,
                        'sentiment_label': post.sentiment_label,
                        'ai_summary': post.ai_summary,
                        'ai_category': post.ai_category,
                        'ai_key_points': safe_json_parse(post.ai_key_points, []),
                        'ai_action_required': post.ai_action_required,
                        'ai_hashtags': safe_json_parse(post.ai_hashtags, [])
                    }
                    enhanced_posts.append(enhanced_post)
                    logger.debug(f"Using cached AI summary for post {post.id}")
                else:
                    # Post needs AI analysis
                    post_dict = {
                        'id': post.id,
                        'title': post.title or '',
                        'content': post.content or '',
                        'author': post.author or '',
                        'category': post.category or '',
                        'url': str(post.url) if post.url else '',
                        'date': post.date.isoformat() if post.date else None,
                        'sentiment_score': post.sentiment_score,
                        'sentiment_label': post.sentiment_label
                    }
                    posts_needing_ai.append((post, post_dict))
                    
            except Exception as e:
                logger.error(f"Error processing post {post.id}: {e}")
                continue
        
        # Generate AI summaries only for posts that don't have them cached
        if posts_needing_ai:
            logger.info(f"🤖 Generating AI summaries for {len(posts_needing_ai)} posts (cached: {len(enhanced_posts)})")
            
            analyzer = AIAnalyzer()
            posts_data = [post_dict for _, post_dict in posts_needing_ai]
            ai_enhanced_posts = await analyzer.analyze_posts_with_summaries(posts_data)
            
            # Save AI summaries to database and add to response
            for (original_post, _), ai_post in zip(posts_needing_ai, ai_enhanced_posts):
                try:
                    # Update database with AI summary
                    original_post.ai_summary = ai_post.get('ai_summary')
                    original_post.ai_category = ai_post.get('ai_category') 
                    original_post.ai_key_points = json.dumps(ai_post.get('ai_key_points', []))
                    original_post.ai_action_required = ai_post.get('ai_action_required')
                    original_post.ai_hashtags = json.dumps(ai_post.get('ai_hashtags', []))
                    
                    db.commit()
                    enhanced_posts.append(ai_post)
                    logger.debug(f"Generated and cached AI summary for post {original_post.id}")
                    
                except Exception as e:
                    logger.error(f"Error saving AI summary for post {original_post.id}: {e}")
                    enhanced_posts.append(ai_post)  # Still return the data even if save fails
        else:
            logger.info(f"📋 All {len(enhanced_posts)} posts already have cached AI summaries")
        
        return enhanced_posts
        
    except Exception as e:
        logger.error(f"Error getting posts with AI summaries: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate AI summaries")

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
        return convert_db_post_to_response(db_post)
        
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
            
        return convert_db_post_to_response(updated_post)
        
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

@router.get("/debug/conversion-test")
async def debug_conversion_test(db: Session = Depends(get_db)):
    """Test post conversion to identify what's failing"""
    try:
        from database.models import PostDB
        
        # Get just one post to test conversion
        test_post = db.query(PostDB).first()
        if not test_post:
            return {"error": "No posts in database"}
            
        # Test the conversion step by step
        result = {
            "raw_post_fields": {
                "id": test_post.id,
                "title": test_post.title,
                "author": test_post.author,
                "category": test_post.category,
                "resolution_status": str(test_post.resolution_status),
                "has_accepted_solution": test_post.has_accepted_solution,
                "problem_severity": str(test_post.problem_severity),
                "business_impact": str(test_post.business_impact),
                "has_vision_analysis": bool(test_post.vision_analysis),
                "has_text_analysis": bool(test_post.text_analysis),
                "has_extracted_issues": bool(test_post.extracted_issues),
                "has_mentioned_products": bool(test_post.mentioned_products)
            }
        }
        
        # Try to convert the post
        try:
            converted_post = convert_db_post_to_response(test_post)
            result["conversion_success"] = True
            result["converted_post_sample"] = {
                "id": converted_post.id,
                "title": converted_post.title[:50] if converted_post.title else None,
                "author": converted_post.author,
                "resolution_status": converted_post.resolution_status
            }
        except Exception as conv_error:
            result["conversion_success"] = False
            result["conversion_error"] = str(conv_error)
            result["error_type"] = type(conv_error).__name__
            
        return result
        
    except Exception as e:
        return {"error": str(e), "error_type": type(e).__name__}

@router.get("/debug/resolution-status")
async def debug_resolution_status(db: Session = Depends(get_db)):
    """Debug endpoint to check resolution status distribution"""
    try:
        from database.models import PostDB
        from sqlalchemy import func
        
        # Get resolution status distribution
        resolution_stats = db.query(
            PostDB.resolution_status, 
            func.count(PostDB.id).label('count')
        ).group_by(PostDB.resolution_status).all()
        
        # Get has_accepted_solution distribution
        solution_stats = db.query(
            PostDB.has_accepted_solution,
            func.count(PostDB.id).label('count')
        ).group_by(PostDB.has_accepted_solution).all()
        
        # Get some sample posts with solutions
        sample_solved = db.query(PostDB).filter(
            (PostDB.resolution_status == 'resolved') | 
            (PostDB.has_accepted_solution == True)
        ).limit(5).all()
        
        return {
            "resolution_status_distribution": {str(stat[0]): stat[1] for stat in resolution_stats},
            "has_accepted_solution_distribution": {str(stat[0]): stat[1] for stat in solution_stats},
            "sample_solved_posts": [
                {
                    "id": post.id,
                    "title": post.title[:50] if post.title else "No title",
                    "resolution_status": post.resolution_status,
                    "has_accepted_solution": post.has_accepted_solution,
                    "category": post.category,
                    "url": post.url
                } for post in sample_solved
            ],
            "total_posts": db.query(func.count(PostDB.id)).scalar()
        }
        
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}")
        return {"error": str(e)}

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
        
        return [convert_db_post_to_response(post) for post in posts]
        
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

@router.get("/hashtag/{hashtag}")
async def get_posts_by_hashtag(
    hashtag: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get posts that contain a specific hashtag in their AI analysis"""
    try:
        from database.models import PostDB
        
        # Search for posts containing the hashtag in AI hashtags field
        posts = db.query(PostDB).filter(
            PostDB.ai_hashtags.contains(hashtag.lower())
        ).order_by(PostDB.date.desc())\
         .offset(skip)\
         .limit(limit)\
         .all()
        
        # Convert to response format
        response_posts = []
        for post in posts:
            try:
                response_post = convert_db_post_to_response(post)
                response_posts.append(response_post)
            except Exception as e:
                logger.error(f"Error converting post {post.id}: {e}")
                continue
        
        return response_posts
        
    except Exception as e:
        logger.error(f"Error getting posts by hashtag {hashtag}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get posts by hashtag")