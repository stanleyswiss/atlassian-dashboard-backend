import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Simple settings class without Pydantic validation issues"""
    
    def __init__(self):
        # App settings
        self.app_name = "Atlassian Community Dashboard"
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.debug = self.environment.lower() != "production"
        
        # Server settings
        self.port = int(os.getenv("PORT", 8000))
        self.host = os.getenv("HOST", "0.0.0.0")
        
        # Database
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./data/atlassian_dashboard.db")
        
        # OpenAI
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # CORS - parse from environment variable
        cors_env = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
        self.cors_origins = [url.strip() for url in cors_env.split(",") if url.strip()]
        
        # Scraper settings
        self.scraper_user_agent = os.getenv("SCRAPER_USER_AGENT", "Mozilla/5.0 (compatible; AtlassianDashboard/1.0)")
        self.scraper_timeout = int(os.getenv("SCRAPER_TIMEOUT", 30))
        self.scraper_delay = float(os.getenv("SCRAPER_DELAY", 2.0))
        
        # Background tasks
        self.data_collection_interval = int(os.getenv("DATA_COLLECTION_INTERVAL", 3600))
        self.sentiment_batch_size = int(os.getenv("SENTIMENT_BATCH_SIZE", 10))
        
        # Vision Analysis settings
        self.enable_vision_analysis = os.getenv("ENABLE_VISION_ANALYSIS", "true").lower() == "true"
        self.vision_analysis_batch_size = int(os.getenv("VISION_ANALYSIS_BATCH_SIZE", 5))
        self.max_images_per_post = int(os.getenv("MAX_IMAGES_PER_POST", 5))
        self.vision_analysis_cache_ttl = int(os.getenv("VISION_ANALYSIS_CACHE_TTL", 86400))
        
        # Enhanced Analytics settings
        self.enable_problem_tracking = os.getenv("ENABLE_PROBLEM_TRACKING", "true").lower() == "true"
        self.business_insights_update_interval = int(os.getenv("BUSINESS_INSIGHTS_UPDATE_INTERVAL", 3600))
    
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

# Create settings instance
settings = Settings()