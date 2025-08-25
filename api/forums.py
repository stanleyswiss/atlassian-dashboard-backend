"""
Forums API endpoints for forum-level statistics and information
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging
from collections import Counter

from database.connection import get_session
from database.models import PostDB
from database.operations import PostOperations

router = APIRouter(prefix="/api/forums", tags=["forums"])
logger = logging.getLogger(__name__)

# Forum configuration with proper URLs
FORUM_CONFIGS = {
    "jira": {
        "name": "Jira Questions",
        "description": "Get help with Jira configuration, workflows, and best practices",
        "url": "https://community.atlassian.com/t5/Jira-questions/bd-p/jira-questions",
        "icon": "🎯"
    },
    "jsm": {
        "name": "Jira Service Management", 
        "description": "Service desk setup, automation, and customer portal questions",
        "url": "https://community.atlassian.com/t5/Jira-Service-Management/ct-p/jira-service-desk",
        "icon": "🎧"
    },
    "confluence": {
        "name": "Confluence Questions",
        "description": "Page templates, spaces, permissions, and collaboration tips", 
        "url": "https://community.atlassian.com/t5/Confluence-questions/bd-p/confluence-questions",
        "icon": "📚"
    },
    "rovo": {
        "name": "Rovo (Atlassian Intelligence)",
        "description": "AI features, smart suggestions, and intelligent automation",
        "url": "https://community.atlassian.com/t5/Rovo/ct-p/rovo-atlassian-intelligence", 
        "icon": "🤖"
    },
    "announcements": {
        "name": "Community Announcements",
        "description": "Product updates, new features, and important community news",
        "url": "https://community.atlassian.com/t5/Community-Announcements/gh-p/community-announcements",
        "icon": "📢"
    }
}

@router.get("/overview")
async def get_forums_overview(days: int = 7):
    """
    Get overview statistics for all forums
    """
    try:
        with get_session() as db:
            # Get date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get all posts in time range
            posts = db.query(PostDB).filter(
                PostDB.created_at >= start_date
            ).all()
            
            # Debug: Log what categories we actually have in database
            all_categories = {}
            for post in posts:
                cat = post.category or 'none'
                all_categories[cat] = all_categories.get(cat, 0) + 1
            
            logger.info(f"🔍 Forums API Debug - Database categories found: {all_categories}")
            logger.info(f"🔍 Forums API Debug - Total posts retrieved: {len(posts)}")
            logger.info(f"🔍 Forums API Debug - Forum configs looking for: {list(FORUM_CONFIGS.keys())}")
            
            # Group by forum/category
            forum_stats = {}
            
            for forum_key, forum_config in FORUM_CONFIGS.items():
                # Get posts for this forum
                forum_posts = [p for p in posts if p.category and p.category.lower() == forum_key.lower()]
                
                # Debug: Log category distribution if no posts found
                if len(forum_posts) == 0 and forum_key in ['jira', 'jsm', 'confluence']:
                    logger.info(f"🔍 No posts for forum '{forum_key}' - checking first 10 post categories:")
                    sample_categories = [p.category for p in posts[:10] if p.category]
                    logger.info(f"   Sample categories: {sample_categories}")
                    unique_categories = set(p.category for p in posts if p.category)
                    logger.info(f"   All unique categories: {list(unique_categories)}")
                
                # Calculate statistics
                total_posts = len(forum_posts)
                
                # Posts with solutions/resolved status  
                solved_posts = len([p for p in forum_posts if 
                                  p.resolution_status == 'resolved' or
                                  (hasattr(p, 'has_accepted_solution') and p.has_accepted_solution)])
                
                # Critical issues
                critical_posts = len([p for p in forum_posts if 
                                    p.enhanced_category == 'critical_issue' or
                                    p.problem_severity in ['critical', 'high']])
                
                # Authors count
                authors = set(p.author for p in forum_posts if p.author)
                
                # Latest activity
                latest_post = None
                if forum_posts:
                    latest_post = max(forum_posts, key=lambda p: p.created_at or datetime.min)
                
                # Calculate health score
                health_score = 75  # Base score
                if total_posts > 0:
                    resolution_rate = solved_posts / total_posts
                    critical_rate = critical_posts / total_posts
                    
                    health_score += min(resolution_rate * 20, 20)  # +20 for good resolution rate
                    health_score -= min(critical_rate * 30, 30)    # -30 for high critical rate
                    health_score = max(0, min(100, health_score))
                
                forum_stats[forum_key] = {
                    **forum_config,
                    "post_count": total_posts,
                    "solved_count": solved_posts,
                    "critical_count": critical_posts,
                    "authors_count": len(authors),  # Match frontend interface
                    "health_score": round(health_score, 1),
                    "latest_activity": {
                        "title": latest_post.title if latest_post else None,
                        "author": latest_post.author if latest_post else None,
                        "date": latest_post.created_at.isoformat() if latest_post else None
                    } if latest_post else None,
                    "resolution_rate": round(resolution_rate * 100, 1) if total_posts > 0 else 0,
                }
            
            # Overall statistics
            total_posts_all = sum(stats['post_count'] for stats in forum_stats.values())
            total_solved_all = sum(stats['solved_count'] for stats in forum_stats.values())
            total_critical_all = sum(stats['critical_count'] for stats in forum_stats.values())
            
            # Most active forum
            most_active_forum = max(forum_stats.keys(), 
                                  key=lambda f: forum_stats[f]['post_count']) if forum_stats else None
            
            return {
                "success": True,
                "forums": forum_stats,
                "total_posts": total_posts_all,
                "total_solved": total_solved_all,
                "total_critical": total_critical_all,
                "generated_at": datetime.now().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Error getting forums overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{forum_name}/details")
async def get_forum_details(forum_name: str, days: int = 7):
    """
    Get detailed statistics for a specific forum
    """
    if forum_name not in FORUM_CONFIGS:
        raise HTTPException(
            status_code=404, 
            detail=f"Forum '{forum_name}' not found. Available forums: {list(FORUM_CONFIGS.keys())}"
        )
    
    try:
        with get_session() as db:
            # Get date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get posts for this forum
            forum_posts = db.query(PostDB).filter(
                PostDB.category == forum_name,
                PostDB.created_at >= start_date
            ).all()
            
            forum_config = FORUM_CONFIGS[forum_name]
            
            # Detailed statistics
            total_posts = len(forum_posts)
            
            # Enhanced category distribution
            category_distribution = Counter(p.enhanced_category for p in forum_posts if p.enhanced_category)
            
            # Problem severity distribution
            severity_distribution = Counter(p.problem_severity for p in forum_posts if p.problem_severity)
            
            # Resolution status distribution
            resolution_distribution = Counter(p.resolution_status for p in forum_posts if p.resolution_status)
            
            # Business impact distribution
            impact_distribution = Counter(p.business_impact for p in forum_posts if p.business_impact)
            
            # Recent posts (last 5)
            recent_posts = sorted(forum_posts, key=lambda p: p.created_at or datetime.min, reverse=True)[:5]
            
            return {
                "forum": {
                    **forum_config,
                    "key": forum_name
                },
                "time_period": f"Last {days} days", 
                "statistics": {
                    "total_posts": total_posts,
                    "unique_authors": len(set(p.author for p in forum_posts if p.author)),
                    "posts_with_screenshots": len([p for p in forum_posts if p.has_screenshots]),
                    "avg_posts_per_day": round(total_posts / days, 1) if days > 0 else 0
                },
                "distributions": {
                    "enhanced_categories": dict(category_distribution),
                    "problem_severity": dict(severity_distribution), 
                    "resolution_status": dict(resolution_distribution),
                    "business_impact": dict(impact_distribution)
                },
                "recent_posts": [
                    {
                        "title": p.title,
                        "author": p.author,
                        "created_at": p.created_at.isoformat() if p.created_at else None,
                        "enhanced_category": p.enhanced_category,
                        "problem_severity": p.problem_severity,
                        "url": p.url
                    }
                    for p in recent_posts
                ]
            }
            
    except Exception as e:
        logger.error(f"Error getting forum details for {forum_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health-comparison")
async def get_forum_health_comparison(days: int = 7):
    """
    Compare health metrics across all forums
    """
    try:
        with get_session() as db:
            # Get date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get posts for analysis
            posts = db.query(PostDB).filter(
                PostDB.created_at >= start_date
            ).all()
            
            health_comparison = {}
            
            for forum_key, forum_config in FORUM_CONFIGS.items():
                forum_posts = [p for p in posts if p.category and p.category.lower() == forum_key.lower()]
                
                # Debug: Log category distribution if no posts found
                if len(forum_posts) == 0 and forum_key in ['jira', 'jsm', 'confluence']:
                    logger.info(f"🔍 No posts for forum '{forum_key}' - checking first 10 post categories:")
                    sample_categories = [p.category for p in posts[:10] if p.category]
                    logger.info(f"   Sample categories: {sample_categories}")
                    unique_categories = set(p.category for p in posts if p.category)
                    logger.info(f"   All unique categories: {list(unique_categories)}")
                
                if not forum_posts:
                    health_comparison[forum_key] = {
                        "name": forum_config["name"],
                        "health_metrics": {
                            "total_posts": 0,
                            "health_score": 50,
                            "critical_issues": 0,
                            "resolved_posts": 0,
                            "community_engagement": "low"
                        }
                    }
                    continue
                
                # Calculate detailed health metrics
                total_posts = len(forum_posts)
                critical_issues = len([p for p in forum_posts if 
                                     p.enhanced_category == 'critical_issue' or
                                     p.problem_severity in ['critical', 'high']])
                resolved_posts = len([p for p in forum_posts if 
                                    p.resolution_status == 'resolved'])
                posts_with_help = len([p for p in forum_posts if
                                     p.enhanced_category in ['solution_sharing', 'configuration_help']])
                
                # Health score calculation
                health_score = 70  # Base score
                
                if total_posts > 0:
                    critical_rate = critical_issues / total_posts
                    resolution_rate = resolved_posts / total_posts
                    help_rate = posts_with_help / total_posts
                    
                    # Adjust score based on metrics
                    health_score -= critical_rate * 40    # Penalty for critical issues
                    health_score += resolution_rate * 20  # Bonus for solutions
                    health_score += help_rate * 10        # Bonus for helpful content
                
                health_score = max(0, min(100, health_score))
                
                # Engagement level
                engagement = "high" if total_posts > 20 else "medium" if total_posts > 5 else "low"
                
                health_comparison[forum_key] = {
                    "name": forum_config["name"],
                    "health_metrics": {
                        "total_posts": total_posts,
                        "health_score": round(health_score, 1),
                        "critical_issues": critical_issues,
                        "resolved_posts": resolved_posts,
                        "community_engagement": engagement,
                        "resolution_rate": round(resolution_rate * 100, 1) if total_posts > 0 else 0,
                        "critical_rate": round(critical_rate * 100, 1) if total_posts > 0 else 0
                    }
                }
            
            # Sort by health score
            sorted_forums = sorted(health_comparison.items(), 
                                 key=lambda x: x[1]['health_metrics']['health_score'], 
                                 reverse=True)
            
            return {
                "time_period": f"Last {days} days",
                "forum_health_comparison": dict(sorted_forums),
                "summary": {
                    "healthiest_forum": sorted_forums[0][0] if sorted_forums else None,
                    "most_active_forum": max(health_comparison.keys(), 
                                           key=lambda f: health_comparison[f]['health_metrics']['total_posts']) if health_comparison else None,
                    "total_forums_analyzed": len(health_comparison),
                    "average_health_score": round(sum(f['health_metrics']['health_score'] for f in health_comparison.values()) / len(health_comparison), 1) if health_comparison else 0
                }
            }
        
    except Exception as e:
        logger.error(f"Error getting forum health comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))