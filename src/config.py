"""
Configuration module for the Opportunist application.
Loads settings from environment variables with defaults.
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    timezone: str = Field(default="America/New_York", env="TIMEZONE")
    
    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="text-embedding-ada-002", env="OPENAI_MODEL")
    
    # MongoDB Configuration
    mongodb_uri: str = Field(..., env="MONGODB_URI")
    mongodb_database: str = Field(default="opportunist", env="MONGODB_DATABASE")
    
    # SendGrid Configuration
    sendgrid_api_key: str = Field(..., env="SENDGRID_API_KEY")
    sendgrid_from_email: str = Field(..., env="SENDGRID_FROM_EMAIL")
    sendgrid_to_email: str = Field(..., env="SENDGRID_TO_EMAIL")
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    
    # Crawling Configuration
    max_crawl_pages: int = Field(default=500, env="MAX_CRAWL_PAGES")
    crawl_delay: float = Field(default=1.0, env="CRAWL_DELAY")
    max_retries: int = Field(default=3, env="MAX_RETRIES")
    concurrent_requests: int = Field(default=16, env="CONCURRENT_REQUESTS")
    
    # AI Filtering
    relevance_threshold: float = Field(default=0.7, env="RELEVANCE_THRESHOLD")
    
    # Email Scheduling
    email_schedule_time: str = Field(default="07:00", env="EMAIL_SCHEDULE_TIME")
    
    # Social Media APIs
    twitter_bearer_token: Optional[str] = Field(default=None, env="TWITTER_BEARER_TOKEN")
    linkedin_client_id: Optional[str] = Field(default=None, env="LINKEDIN_CLIENT_ID")
    linkedin_client_secret: Optional[str] = Field(default=None, env="LINKEDIN_CLIENT_SECRET")
    
    # Batch Limits for Email Digest
    max_jobs: int = Field(default=10, env="MAX_JOBS")
    max_internships: int = Field(default=5, env="MAX_INTERNSHIPS")
    max_scholarships: int = Field(default=5, env="MAX_SCHOLARSHIPS")
    max_research: int = Field(default=5, env="MAX_RESEARCH")
    max_competitions: int = Field(default=5, env="MAX_COMPETITIONS")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


# Target domains configuration
TARGET_DOMAINS = {
    "companies": [
        "careers.google.com",
        "jobs.netflix.com", 
        "careers.microsoft.com",
        "careers.apple.com",
        "careers.amazon.com",
        "careers.meta.com",
        "jobs.lever.co",
        "greenhouse.io"
    ],
    "universities": [
        "mit.edu",
        "stanford.edu",
        "berkeley.edu",
        "cmu.edu",
        "caltech.edu"
    ],
    "scholarship_boards": [
        "fastweb.com",
        "scholarships.com",
        "cappex.com",
        "niche.com"
    ]
}


# User interests for AI filtering
USER_INTERESTS = [
    "computer science internships",
    "software engineering jobs",
    "machine learning research",
    "PhD funding opportunities",
    "data science positions",
    "AI research fellowships",
    "technology scholarships",
    "programming competitions",
    "startup opportunities",
    "remote software development"
]


def get_db_collections():
    """Returns the database collection names."""
    return {
        "raw_pages": "raw_pages",
        "opportunities": "opportunities", 
        "users": "users",
        "crawl_logs": "crawl_logs"
    }
