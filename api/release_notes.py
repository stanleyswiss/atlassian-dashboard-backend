"""
Release Notes API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import json

from database import get_db, ReleaseNoteOperations
from models import (
    ReleaseNoteResponse, ReleaseNoteSummary, ReleaseNoteFilters, 
    ProductType, ImpactLevel, ReleaseCategory
)
from services.release_notes_scraper import ReleaseNotesScraper

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/release-notes", tags=["release-notes"])

def convert_db_release_to_response(release) -> ReleaseNoteResponse:
    """Convert database release model to response model, parsing JSON fields"""
    
    def safe_json_parse(value, default):
        """Safely parse JSON string, return default on error"""
        if value is None:
            return default
        if not value:
            return default
        if not isinstance(value, str):
            return value if value is not None else default
        try:
            parsed = json.loads(value)
            return parsed if parsed is not None else default
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"JSON parse error for value '{value}': {e}")
            return default
    
    # Parse JSON fields safely
    ai_key_changes = safe_json_parse(release.ai_key_changes, [])
    ai_categories = safe_json_parse(release.ai_categories, [])
    
    # Create response model
    release_dict = {
        "id": release.id,
        "product_name": release.product_name,
        "product_type": release.product_type,
        "product_id": release.product_id,
        "version": release.version,
        "build_number": release.build_number,
        "release_date": release.release_date,
        "release_summary": release.release_summary,
        "release_notes": release.release_notes,
        "release_notes_url": release.release_notes_url,
        "download_url": release.download_url,
        "is_major_release": release.is_major_release or False,
        "is_security_release": release.is_security_release or False,
        "ai_summary": release.ai_summary,
        "ai_key_changes": ai_key_changes,
        "ai_impact_level": release.ai_impact_level,
        "ai_categories": ai_categories,
        "created_at": release.created_at,
        "updated_at": release.updated_at,
    }
    
    return ReleaseNoteResponse(**release_dict)

@router.get("/", response_model=List[ReleaseNoteResponse])
async def get_release_notes(
    skip: int = Query(0, ge=0, description="Number of release notes to skip"),
    limit: int = Query(50, ge=1, le=200, description="Number of release notes to return"),
    product_type: Optional[ProductType] = Query(None, description="Filter by product type"),
    product_name: Optional[str] = Query(None, description="Filter by product name (partial match)"),
    days_back: int = Query(7, ge=1, le=365, description="Number of days to look back"),
    major_releases_only: bool = Query(False, description="Only show major releases"),
    security_releases_only: bool = Query(False, description="Only show security releases"),
    impact_level: Optional[ImpactLevel] = Query(None, description="Filter by AI impact level"),
    db: Session = Depends(get_db)
):
    """Get release notes with filtering and pagination"""
    try:
        logger.info(f"Getting release notes: skip={skip}, limit={limit}, product_type={product_type}")
        
        releases = ReleaseNoteOperations.get_release_notes(
            db=db,
            skip=skip,
            limit=limit,
            product_type=product_type.value if product_type else None,
            product_name=product_name,
            days_back=days_back,
            major_releases_only=major_releases_only,
            security_releases_only=security_releases_only
        )
        
        logger.info(f"Retrieved {len(releases)} release notes from database")
        
        # Convert releases with error handling
        response_releases = []
        for release in releases:
            try:
                response_release = convert_db_release_to_response(release)
                
                # Apply impact level filter if specified
                if impact_level and response_release.ai_impact_level != impact_level:
                    continue
                    
                response_releases.append(response_release)
            except Exception as conv_error:
                logger.error(f"Error converting release {release.id}: {conv_error}")
                continue
        
        return response_releases
        
    except Exception as e:
        logger.error(f"Error getting release notes: {e}")
        raise HTTPException(status_code=500, detail="Failed to get release notes")

@router.get("/summary", response_model=List[ReleaseNoteSummary])
async def get_release_notes_summary(
    days_back: int = Query(7, ge=1, le=365, description="Number of days to look back"),
    limit: int = Query(20, ge=1, le=100, description="Number of releases to return"),
    product_type: Optional[ProductType] = Query(None, description="Filter by product type"),
    db: Session = Depends(get_db)
):
    """Get summarized release notes for dashboard display"""
    try:
        releases = ReleaseNoteOperations.get_release_notes(
            db=db,
            skip=0,
            limit=limit,
            product_type=product_type.value if product_type else None,
            days_back=days_back
        )
        
        # Convert to summary format
        summaries = []
        for release in releases:
            try:
                summary = ReleaseNoteSummary(
                    id=release.id,
                    product_name=release.product_name,
                    product_type=release.product_type,
                    version=release.version,
                    release_date=release.release_date,
                    ai_summary=release.ai_summary,
                    ai_impact_level=release.ai_impact_level,
                    is_major_release=release.is_major_release or False,
                    is_security_release=release.is_security_release or False
                )
                summaries.append(summary)
            except Exception as e:
                logger.error(f"Error converting release {release.id} to summary: {e}")
                continue
        
        return summaries
        
    except Exception as e:
        logger.error(f"Error getting release notes summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get release notes summary")

@router.get("/{release_id}", response_model=ReleaseNoteResponse)
async def get_release_note(release_id: int, db: Session = Depends(get_db)):
    """Get a single release note by ID"""
    try:
        release = ReleaseNoteOperations.get_release_note(db, release_id)
        if not release:
            raise HTTPException(status_code=404, detail="Release note not found")
            
        return convert_db_release_to_response(release)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting release note {release_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get release note")

@router.post("/scrape")
async def trigger_release_notes_scrape(
    background_tasks: BackgroundTasks,
    days_back: int = Query(7, ge=1, le=365, description="Number of days to look back for releases")
):
    """Trigger release notes scraping in the background"""
    try:
        async def run_scrape():
            try:
                scraper = ReleaseNotesScraper(days_to_look_back=days_back)
                result = await scraper.run_full_scrape()
                logger.info(f"Background release notes scrape completed: {result}")
            except Exception as e:
                logger.error(f"Background release notes scrape failed: {e}")
        
        background_tasks.add_task(run_scrape)
        
        return {
            "message": "Release notes scraping started in background",
            "days_back": days_back,
            "status": "started"
        }
        
    except Exception as e:
        logger.error(f"Error starting release notes scrape: {e}")
        raise HTTPException(status_code=500, detail="Failed to start release notes scraping")

@router.get("/stats/overview")
async def get_release_notes_stats(
    days_back: int = Query(7, ge=1, le=365, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """Get release notes statistics"""
    try:
        from database.models import ReleaseNoteDB
        from sqlalchemy import func, and_
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # Total counts
        total_releases = db.query(ReleaseNoteDB).filter(
            ReleaseNoteDB.release_date >= cutoff_date
        ).count()
        
        # Product type breakdown
        product_type_counts = db.query(
            ReleaseNoteDB.product_type,
            func.count(ReleaseNoteDB.id).label('count')
        ).filter(
            ReleaseNoteDB.release_date >= cutoff_date
        ).group_by(ReleaseNoteDB.product_type).all()
        
        product_type_breakdown = {ptype: count for ptype, count in product_type_counts}
        
        # Major and security releases
        major_releases = db.query(ReleaseNoteDB).filter(
            and_(
                ReleaseNoteDB.release_date >= cutoff_date,
                ReleaseNoteDB.is_major_release == True
            )
        ).count()
        
        security_releases = db.query(ReleaseNoteDB).filter(
            and_(
                ReleaseNoteDB.release_date >= cutoff_date,
                ReleaseNoteDB.is_security_release == True
            )
        ).count()
        
        # Top products by release count
        top_products = db.query(
            ReleaseNoteDB.product_name,
            func.count(ReleaseNoteDB.id).label('count')
        ).filter(
            ReleaseNoteDB.release_date >= cutoff_date
        ).group_by(ReleaseNoteDB.product_name).order_by(
            func.count(ReleaseNoteDB.id).desc()
        ).limit(10).all()
        
        # Recent releases
        recent_releases = db.query(ReleaseNoteDB).filter(
            ReleaseNoteDB.release_date >= cutoff_date
        ).order_by(ReleaseNoteDB.release_date.desc()).limit(5).all()
        
        return {
            "total_releases": total_releases,
            "product_type_breakdown": product_type_breakdown,
            "major_releases": major_releases,
            "security_releases": security_releases,
            "top_products": [{"product": product, "count": count} for product, count in top_products],
            "recent_releases": [
                {
                    "id": release.id,
                    "product_name": release.product_name,
                    "version": release.version,
                    "release_date": release.release_date.isoformat(),
                    "is_major": release.is_major_release or False,
                    "is_security": release.is_security_release or False
                } for release in recent_releases
            ],
            "days_back": days_back
        }
        
    except Exception as e:
        logger.error(f"Error getting release notes stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get release notes statistics")

@router.get("/products/list")
async def get_available_products(db: Session = Depends(get_db)):
    """Get list of products that have release notes"""
    try:
        from database.models import ReleaseNoteDB
        from sqlalchemy import func, distinct
        
        # Get unique product names with counts
        products = db.query(
            ReleaseNoteDB.product_name,
            ReleaseNoteDB.product_type,
            func.count(ReleaseNoteDB.id).label('release_count')
        ).group_by(
            ReleaseNoteDB.product_name,
            ReleaseNoteDB.product_type
        ).order_by(ReleaseNoteDB.product_name).all()
        
        return [
            {
                "name": product.product_name,
                "type": product.product_type,
                "release_count": product.release_count
            } for product in products
        ]
        
    except Exception as e:
        logger.error(f"Error getting available products: {e}")
        raise HTTPException(status_code=500, detail="Failed to get available products")

@router.post("/{release_id}/analyze")
async def analyze_release_note(
    release_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger AI analysis for a specific release note"""
    try:
        release = ReleaseNoteOperations.get_release_note(db, release_id)
        if not release:
            raise HTTPException(status_code=404, detail="Release note not found")
        
        async def run_analysis():
            try:
                from services.ai_analyzer import AIAnalyzer
                analyzer = AIAnalyzer()
                
                # Prepare release data for AI analysis
                release_data = {
                    'product_name': release.product_name,
                    'version': release.version,
                    'release_summary': release.release_summary or '',
                    'release_notes': release.release_notes or ''
                }
                
                # Run AI analysis (implement this method in AIAnalyzer)
                # ai_result = await analyzer.analyze_release_note(release_data)
                
                # For now, just log that analysis would run
                logger.info(f"Would analyze release note {release_id}: {release.product_name} {release.version}")
                
            except Exception as e:
                logger.error(f"Error analyzing release note {release_id}: {e}")
        
        background_tasks.add_task(run_analysis)
        
        return {
            "message": f"AI analysis started for release note {release_id}",
            "release": {
                "id": release.id,
                "product_name": release.product_name,
                "version": release.version
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting analysis for release note {release_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start release note analysis")