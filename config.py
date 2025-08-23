import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    app_name: str = "Atlassian Community Dashboard"
    environment: str = "development"
    debug: bool = True
    
    # Server settings
    port: int = 8000
    host: str = "0.0.0.0"
    
    # Database
    database_url: str = "sqlite:///./data/atlassian_dashboard.db"
    
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    
    # CORS - will be parsed from environment variable
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    
    # Scraper settings
    scraper_user_agent: str = "Mozilla/5.0 (compatible; AtlassianDashboard/1.0)"
    scraper_timeout: int = 30
    scraper_delay: float = 2.0
    
    # Background tasks
    data_collection_interval: int = 3600  # 1 hour in seconds
    sentiment_batch_size: int = 10
    
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"
    
    @property 
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into list"""
        if isinstance(self.cors_origins, str):
            return [url.strip() for url in self.cors_origins.split(",")]
        return self.cors_origins
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Override debug based on environment
        if self.is_production:
            self.debug = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()