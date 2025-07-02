"""
Data models for opportunities and related entities.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum


class OpportunityCategory(str, Enum):
    """Enum for opportunity categories."""
    JOB = "job"
    INTERNSHIP = "internship"
    SCHOLARSHIP = "scholarship"
    RESEARCH = "research"
    COMPETITION = "competition"
    GRANT = "grant"
    OTHER = "other"


class OpportunityBase(BaseModel):
    """Base model for opportunities."""
    title: str = Field(..., description="Title of the opportunity")
    description: str = Field(..., description="Full description text")
    deadline: Optional[datetime] = Field(None, description="Application deadline")
    category: OpportunityCategory = Field(..., description="Type of opportunity")
    link: HttpUrl = Field(..., description="URL to the listing")
    source: str = Field(..., description="Domain or feed name")
    posted_at: Optional[datetime] = Field(None, description="Original posting timestamp")
    crawled_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when crawled")


class OpportunityCreate(OpportunityBase):
    """Model for creating new opportunities."""
    pass


class OpportunityInDB(OpportunityBase):
    """Model for opportunities stored in database."""
    id: Optional[str] = Field(None, alias="_id")
    vector: Optional[List[float]] = Field(None, description="Embedding vector")
    score: Optional[float] = Field(None, description="Relevance score")
    hash_key: Optional[str] = Field(None, description="Hash for deduplication")
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class RawPage(BaseModel):
    """Model for raw crawled pages before processing."""
    url: HttpUrl = Field(..., description="URL of the crawled page")
    html_content: str = Field(..., description="Raw HTML content")
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    status_code: int = Field(..., description="HTTP status code")
    source_domain: str = Field(..., description="Domain of the source")
    headers: Optional[dict] = Field(None, description="Response headers")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class CrawlLog(BaseModel):
    """Model for logging crawl operations."""
    url: HttpUrl = Field(..., description="URL attempted")
    status: str = Field(..., description="success, failed, or skipped")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    spider_name: str = Field(..., description="Name of the spider used")
    retry_count: int = Field(default=0, description="Number of retries attempted")
    response_time: Optional[float] = Field(None, description="Response time in seconds")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserProfile(BaseModel):
    """Model for user preferences and interests."""
    email: str = Field(..., description="User email address")
    interests: List[str] = Field(default_factory=list, description="User interest keywords")
    interest_vectors: Optional[List[List[float]]] = Field(None, description="Precomputed interest embeddings")
    category_limits: dict = Field(
        default_factory=lambda: {
            "job": 10,
            "internship": 5,
            "scholarship": 5,
            "research": 5,
            "competition": 5,
            "grant": 3,
            "other": 2
        },
        description="Max items per category in daily digest"
    )
    active: bool = Field(default=True, description="Whether user wants daily emails")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_email_sent: Optional[datetime] = Field(None, description="Last digest email timestamp")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class EmailDigest(BaseModel):
    """Model for daily email digest data."""
    user_email: str
    opportunities_by_category: dict = Field(default_factory=dict)
    total_count: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivery_status: str = Field(default="pending")  # pending, sent, failed
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
