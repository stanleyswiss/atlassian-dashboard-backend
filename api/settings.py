from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any
import logging
import os
from datetime import datetime
import openai
from pydantic import BaseModel

from database import get_db
from database.connection import get_session
from config import settings as app_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

# Global settings storage (in production, this should be in a database)
_settings_storage = {
    "openai_api_key": "",
    "scraping_enabled": False,
    "scraping_interval": 6,
    "sentiment_analysis_enabled": False,
    "max_posts_per_scrape": 50,
    "auto_cleanup_enabled": True,
    "data_retention_days": 30
}

class SettingsConfig(BaseModel):
    openai_api_key: str
    scraping_enabled: bool
    scraping_interval: int
    sentiment_analysis_enabled: bool
    max_posts_per_scrape: int
    auto_cleanup_enabled: bool
    data_retention_days: int

class OpenAITestRequest(BaseModel):
    api_key: str
    test_text: str = "This is a test message for sentiment analysis."

@router.get("")
async def get_settings():
    """Get current application settings"""
    try:
        # In production, load from database or config file
        # For now, return from memory with API key masked
        settings = _settings_storage.copy()
        
        # Mask API key for security
        if settings["openai_api_key"]:
            key = settings["openai_api_key"]
            if len(key) > 8:
                settings["openai_api_key"] = key[:4] + "*" * (len(key) - 8) + key[-4:]
            else:
                settings["openai_api_key"] = "*" * len(key)
        
        return settings
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get settings")

@router.post("")
async def save_settings(config: SettingsConfig):
    """Save application settings"""
    try:
        # Validate settings
        if config.scraping_interval < 1 or config.scraping_interval > 24:
            raise HTTPException(status_code=400, detail="Scraping interval must be between 1 and 24 hours")
        
        if config.max_posts_per_scrape < 10 or config.max_posts_per_scrape > 200:
            raise HTTPException(status_code=400, detail="Max posts per scrape must be between 10 and 200")
        
        if config.data_retention_days < 1 or config.data_retention_days > 365:
            raise HTTPException(status_code=400, detail="Data retention must be between 1 and 365 days")
        
        # Update global settings
        _settings_storage.update(config.model_dump())
        
        # Set environment variable for OpenAI key if provided
        if config.openai_api_key and not config.openai_api_key.startswith("*"):
            os.environ["OPENAI_API_KEY"] = config.openai_api_key
            # Also update the openai client
            openai.api_key = config.openai_api_key
        
        logger.info("Settings updated successfully")
        
        return {
            "message": "Settings saved successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save settings")

@router.post("/test-openai")
async def test_openai_connection(request: OpenAITestRequest):
    """Test OpenAI API connection and sentiment analysis"""
    try:
        # Temporarily set the API key for testing
        original_key = os.environ.get("OPENAI_API_KEY")
        
        # Set test API key
        os.environ["OPENAI_API_KEY"] = request.api_key
        openai.api_key = request.api_key
        
        try:
            # Import our AI analyzer
            from services.ai_analyzer import AIAnalyzer
            
            # Test sentiment analysis
            analyzer = AIAnalyzer()
            result = await analyzer.analyze_sentiment(request.test_text)
            
            return {
                "success": True,
                "message": "OpenAI API connection successful",
                "test_result": {
                    "text": request.test_text,
                    "sentiment_score": result.get("sentiment_score"),
                    "sentiment_label": result.get("sentiment_label"),
                    "confidence": result.get("confidence")
                },
                "model_used": "gpt-4o-mini",
                "timestamp": datetime.now().isoformat()
            }
            
        finally:
            # Restore original API key
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key
                openai.api_key = original_key
            elif "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
                
    except Exception as e:
        error_msg = str(e)
        
        # Handle specific OpenAI errors
        if "invalid api key" in error_msg.lower():
            raise HTTPException(status_code=400, detail="Invalid OpenAI API key")
        elif "quota" in error_msg.lower():
            raise HTTPException(status_code=400, detail="OpenAI API quota exceeded")
        elif "rate limit" in error_msg.lower():
            raise HTTPException(status_code=400, detail="OpenAI API rate limit reached")
        else:
            logger.error(f"OpenAI test error: {e}")
            raise HTTPException(status_code=500, detail=f"OpenAI API test failed: {error_msg}")

@router.get("/current")
async def get_current_settings():
    """Get current settings without masking (for internal use)"""
    return _settings_storage

@router.post("/reset")
async def reset_settings():
    """Reset settings to defaults"""
    try:
        global _settings_storage
        _settings_storage = {
            "openai_api_key": "",
            "scraping_enabled": False,
            "scraping_interval": 6,
            "sentiment_analysis_enabled": False,
            "max_posts_per_scrape": 50,
            "auto_cleanup_enabled": True,
            "data_retention_days": 30
        }
        
        # Clear OpenAI API key from environment
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        
        return {
            "message": "Settings reset to defaults",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error resetting settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset settings")

@router.get("/status")
async def get_system_status(db: Session = Depends(get_db)):
    """Get system status for all services"""
    try:
        from database.operations import DatabaseOperations
        
        status = {
            "database": {"status": "unknown", "message": "Not tested"},
            "openai": {"status": "unknown", "message": "Not tested"},
            "scraping": {"status": "unknown", "message": "Not tested"},
            "settings": _settings_storage
        }
        
        # Test database
        try:
            # Simple database health check
            with get_session() as test_db:
                test_db.execute(text("SELECT 1"))
            status["database"] = {
                "status": "connected", 
                "message": "Database connection successful"
            }
        except Exception as e:
            status["database"] = {"status": "error", "message": f"Database error: {str(e)}"}
        
        # Test OpenAI (only if API key is set)
        if _settings_storage.get("openai_api_key") and not _settings_storage["openai_api_key"].startswith("*"):
            try:
                from services.ai_analyzer import AIAnalyzer
                analyzer = AIAnalyzer()
                # Quick test without full analysis
                status["openai"] = {"status": "connected", "message": "OpenAI API key configured"}
            except Exception as e:
                status["openai"] = {"status": "error", "message": f"OpenAI error: {str(e)}"}
        else:
            status["openai"] = {"status": "not_configured", "message": "OpenAI API key not set"}
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")

# Helper function to get current OpenAI API key
def get_openai_api_key() -> str:
    """Get the current OpenAI API key"""
    return _settings_storage.get("openai_api_key", "")

# Helper function to check if sentiment analysis is enabled
def is_sentiment_analysis_enabled() -> bool:
    """Check if sentiment analysis is enabled"""
    return _settings_storage.get("sentiment_analysis_enabled", False) and bool(_settings_storage.get("openai_api_key", ""))

# Helper function to get scraping configuration
def get_scraping_config() -> Dict[str, Any]:
    """Get current scraping configuration"""
    return {
        "enabled": _settings_storage.get("scraping_enabled", False),
        "interval": _settings_storage.get("scraping_interval", 6),
        "max_posts": _settings_storage.get("max_posts_per_scrape", 50)
    }