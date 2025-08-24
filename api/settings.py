from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any
import logging
import os
import json
from datetime import datetime
import openai
from pydantic import BaseModel

from database import get_db
from database.connection import get_session
from database.models import SettingsDB
from config import settings as app_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

# Default settings - will be stored in database
DEFAULT_SETTINGS = {
    "scraping_enabled": False,
    "scraping_interval": 6,
    "vision_analysis_enabled": True,
    "max_posts_per_scrape": 50,
    "auto_cleanup_enabled": True,
    "data_retention_days": 30,
    "max_pages_per_forum": 3
}

class SettingsConfig(BaseModel):
    scraping_enabled: bool
    scraping_interval: int
    vision_analysis_enabled: bool
    max_posts_per_scrape: int
    auto_cleanup_enabled: bool
    data_retention_days: int
    max_pages_per_forum: int

class OpenAITestRequest(BaseModel):
    api_key: str
    test_text: str = "This is a test message for sentiment analysis."

def get_setting_from_db(key: str, default_value=None):
    """Get a setting from database"""
    try:
        with get_session() as db:
            setting = db.query(SettingsDB).filter(SettingsDB.key == key).first()
            if setting:
                # Parse the value based on type
                if setting.value_type == 'boolean':
                    return setting.value.lower() == 'true'
                elif setting.value_type == 'integer':
                    return int(setting.value)
                elif setting.value_type == 'json':
                    return json.loads(setting.value)
                else:
                    return setting.value
            return default_value
    except Exception as e:
        logger.error(f"Error getting setting {key}: {e}")
        return default_value

def set_setting_in_db(key: str, value, value_type: str = None):
    """Set a setting in database"""
    try:
        with get_session() as db:
            # Auto-detect type if not provided
            if value_type is None:
                if isinstance(value, bool):
                    value_type = 'boolean'
                elif isinstance(value, int):
                    value_type = 'integer'
                elif isinstance(value, (dict, list)):
                    value_type = 'json'
                else:
                    value_type = 'string'
            
            # Convert value to string for storage
            if value_type == 'json':
                str_value = json.dumps(value)
            else:
                str_value = str(value)
            
            # Check if setting exists
            setting = db.query(SettingsDB).filter(SettingsDB.key == key).first()
            if setting:
                # Update existing
                setting.value = str_value
                setting.value_type = value_type
                setting.updated_at = datetime.now()
            else:
                # Create new
                setting = SettingsDB(
                    key=key,
                    value=str_value,
                    value_type=value_type
                )
                db.add(setting)
            
            db.commit()
            return True
    except Exception as e:
        logger.error(f"Error setting {key}: {e}")
        return False

def get_all_settings():
    """Get all settings from database with defaults"""
    settings = DEFAULT_SETTINGS.copy()
    
    try:
        with get_session() as db:
            db_settings = db.query(SettingsDB).all()
            for setting in db_settings:
                # Parse the value based on type
                if setting.value_type == 'boolean':
                    settings[setting.key] = setting.value.lower() == 'true'
                elif setting.value_type == 'integer':
                    settings[setting.key] = int(setting.value)
                elif setting.value_type == 'json':
                    settings[setting.key] = json.loads(setting.value)
                else:
                    settings[setting.key] = setting.value
    except Exception as e:
        logger.error(f"Error getting all settings: {e}")
    
    return settings

@router.get("/config")
async def get_settings_config():
    """Get current application settings configuration"""
    try:
        return get_all_settings()
    except Exception as e:
        logger.error(f"Error getting settings config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get settings config")

@router.get("")
async def get_settings():
    """Get current application settings (legacy endpoint)"""
    try:
        return get_all_settings()
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get settings")

@router.post("/config")
async def save_settings_config(config: SettingsConfig):
    """Save application settings configuration"""
    try:
        # Validate settings
        if config.scraping_interval < 1 or config.scraping_interval > 24:
            raise HTTPException(status_code=400, detail="Scraping interval must be between 1 and 24 hours")
        
        if config.max_posts_per_scrape < 10 or config.max_posts_per_scrape > 200:
            raise HTTPException(status_code=400, detail="Max posts per scrape must be between 10 and 200")
        
        if config.data_retention_days < 1 or config.data_retention_days > 365:
            raise HTTPException(status_code=400, detail="Data retention must be between 1 and 365 days")
        
        if config.max_pages_per_forum < 1 or config.max_pages_per_forum > 10:
            raise HTTPException(status_code=400, detail="Max pages per forum must be between 1 and 10")
        
        # Save each setting to database
        config_dict = config.model_dump()
        saved_count = 0
        
        for key, value in config_dict.items():
            if set_setting_in_db(key, value):
                saved_count += 1
            else:
                logger.warning(f"Failed to save setting: {key}")
        
        if saved_count == len(config_dict):
            logger.info(f"Settings configuration updated successfully - {saved_count} settings saved")
            return {
                "message": "Settings saved successfully",
                "settings_saved": saved_count,
                "timestamp": datetime.now().isoformat()
            }
        else:
            logger.error(f"Partial save: {saved_count}/{len(config_dict)} settings saved")
            raise HTTPException(status_code=500, detail=f"Only {saved_count}/{len(config_dict)} settings were saved")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving settings config: {e}")
        raise HTTPException(status_code=500, detail="Failed to save settings config")

@router.post("")
async def save_settings_legacy(config: SettingsConfig):
    """Save application settings (legacy endpoint)"""
    return await save_settings_config(config)

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
    return get_all_settings()

@router.post("/reset")
async def reset_settings():
    """Reset settings to defaults"""
    try:
        # Clear all settings from database and reset to defaults
        reset_count = 0
        
        for key, value in DEFAULT_SETTINGS.items():
            if set_setting_in_db(key, value):
                reset_count += 1
        
        return {
            "message": "Settings reset to defaults",
            "settings_reset": reset_count,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error resetting settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset settings")

@router.get("/status")
async def get_system_status():
    """Get system status for all services"""
    try:
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
        
        # Test OpenAI (check environment variable instead of settings storage)
        import os
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key and openai_key.strip():
            try:
                # Just check if key exists - don't actually call API to avoid costs
                status["openai"] = {"status": "connected", "message": "OpenAI API key configured"}
            except Exception as e:
                status["openai"] = {"status": "error", "message": f"OpenAI error: {str(e)}"}
        else:
            status["openai"] = {"status": "not_configured", "message": "OpenAI API key not set in environment"}
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")

# Helper function to get current OpenAI API key
def get_openai_api_key() -> str:
    """Get the current OpenAI API key from environment"""
    return os.environ.get("OPENAI_API_KEY", "")

# Helper function to check if vision analysis is enabled
def is_vision_analysis_enabled() -> bool:
    """Check if vision analysis is enabled"""
    settings = get_all_settings()
    return settings.get("vision_analysis_enabled", True) and bool(os.environ.get("OPENAI_API_KEY", ""))

# Helper function to get scraping configuration
def get_scraping_config() -> Dict[str, Any]:
    """Get current scraping configuration"""
    settings = get_all_settings()
    return {
        "enabled": settings.get("scraping_enabled", False),
        "interval": settings.get("scraping_interval", 6),
        "max_posts": settings.get("max_posts_per_scrape", 50)
    }