"""
Diagnostic API endpoints to debug data issues
"""
from fastapi import APIRouter
from typing import Dict, Any, List
import logging
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/diagnostic", tags=["diagnostic"])
logger = logging.getLogger(__name__)

@router.get("/analyze-posts-sample")
async def get_analyzed_posts_sample():
    """Get a sample of analyzed posts to see what data we actually have"""
    try:
        from database.connection import get_session
        from database.models import PostDB
        
        with get_session() as db:
            # Get posts with enhanced analysis
            analyzed_posts = db.query(PostDB).filter(
                PostDB.enhanced_category.isnot(None)
            ).limit(10).all()
            
            sample_data = []
            for post in analyzed_posts:
                sample_data.append({
                    "id": post.id,
                    "title": post.title[:50] + "..." if len(post.title) > 50 else post.title,
                    "category": post.category,
                    "enhanced_category": post.enhanced_category,
                    "problem_severity": post.problem_severity,
                    "resolution_status": post.resolution_status,
                    "business_impact": post.business_impact,
                    "has_screenshots": post.has_screenshots,
                    "created_at": post.created_at.isoformat() if post.created_at else None
                })
            
            # Count by enhanced_category
            category_counts = {}
            severity_counts = {}
            
            for post in analyzed_posts:
                cat = post.enhanced_category or 'none'
                category_counts[cat] = category_counts.get(cat, 0) + 1
                
                sev = post.problem_severity or 'none'
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            
            return {
                "success": True,
                "sample_posts": sample_data,
                "category_distribution": category_counts,
                "severity_distribution": severity_counts,
                "total_analyzed": len(analyzed_posts),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting analyzed posts sample: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/forums-post-counts")
async def get_forums_post_counts():
    """Debug why Forums page shows 0 posts"""
    try:
        from database.connection import get_session
        from database.models import PostDB
        
        with get_session() as db:
            # Count posts by category
            total_posts = db.query(PostDB).count()
            
            category_counts = {}
            categories = ['jira', 'jsm', 'confluence', 'rovo', 'announcements']
            
            for cat in categories:
                count = db.query(PostDB).filter(PostDB.category == cat).count()
                category_counts[cat] = count
            
            # Get recent posts for each category
            recent_samples = {}
            for cat in categories:
                recent = db.query(PostDB).filter(PostDB.category == cat).limit(3).all()
                recent_samples[cat] = [
                    {
                        "id": post.id,
                        "title": post.title[:50] + "..." if len(post.title) > 50 else post.title,
                        "created_at": post.created_at.isoformat() if post.created_at else None
                    }
                    for post in recent
                ]
            
            return {
                "success": True,
                "total_posts": total_posts,
                "posts_by_category": category_counts,
                "recent_samples": recent_samples,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting forums post counts: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/bi-dashboard-debug")
async def debug_bi_dashboard():
    """Debug why BI Dashboard sections are empty"""
    try:
        from database.connection import get_session
        from database.models import PostDB
        from database.operations import PostOperations
        
        with get_session() as db:
            recent_posts = PostOperations.get_recent_posts(db, days=7, limit=100)
            
            # Check critical issues criteria
            critical_count = 0
            solution_count = 0
            discovery_count = 0
            problem_count = 0
            
            critical_samples = []
            solution_samples = []
            
            for post in recent_posts:
                # Critical Issues logic
                is_critical = (
                    post.enhanced_category == 'critical_issue' or
                    post.problem_severity in ['critical', 'high'] or
                    (post.business_impact in ['productivity_loss', 'workflow_broken', 'data_access_blocked'])
                )
                
                if is_critical:
                    critical_count += 1
                    if len(critical_samples) < 3:
                        critical_samples.append({
                            "id": post.id,
                            "title": post.title[:50] + "...",
                            "enhanced_category": post.enhanced_category,
                            "problem_severity": post.problem_severity,
                            "business_impact": post.business_impact
                        })
                
                # Solutions logic
                is_solution = (
                    post.enhanced_category == 'solution_sharing' or
                    post.resolution_status == 'resolved' or
                    (hasattr(post, 'has_accepted_solution') and post.has_accepted_solution)
                )
                
                if is_solution:
                    solution_count += 1
                    if len(solution_samples) < 3:
                        solution_samples.append({
                            "id": post.id,
                            "title": post.title[:50] + "...",
                            "enhanced_category": post.enhanced_category,
                            "resolution_status": post.resolution_status
                        })
            
            return {
                "success": True,
                "total_recent_posts": len(recent_posts),
                "critical_issues_count": critical_count,
                "solutions_count": solution_count,
                "critical_samples": critical_samples,
                "solution_samples": solution_samples,
                "debug_info": {
                    "posts_with_enhanced_category": len([p for p in recent_posts if p.enhanced_category]),
                    "posts_with_problem_severity": len([p for p in recent_posts if p.problem_severity]),
                    "posts_with_resolution_status": len([p for p in recent_posts if p.resolution_status])
                },
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error debugging BI dashboard: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.get("/mock-data-check")
async def check_for_mock_data():
    """Check where mock data might still be appearing"""
    try:
        from database.connection import get_session
        from database.models import PostDB
        
        with get_session() as db:
            # Check for any suspicious patterns that might indicate mock data
            posts = db.query(PostDB).limit(20).all()
            
            suspicious_patterns = []
            for post in posts:
                # Check for mock-like data
                if 'mock' in post.title.lower() or 'test' in post.title.lower():
                    suspicious_patterns.append(f"Post {post.id}: Suspicious title - {post.title}")
                
                if post.author and ('mock' in post.author.lower() or 'test' in post.author.lower()):
                    suspicious_patterns.append(f"Post {post.id}: Suspicious author - {post.author}")
            
            # Check if any endpoints are returning hardcoded data
            mock_indicators = {
                "suspicious_posts": suspicious_patterns,
                "total_posts_checked": len(posts),
                "note": "This checks database content for mock patterns. API mock data would need manual review."
            }
            
            return {
                "success": True,
                "mock_data_analysis": mock_indicators,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error checking for mock data: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }