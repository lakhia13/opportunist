"""
Basic tests to verify core functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime

# Add src to path for testing
import sys
from pathlib import Path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from src.models.opportunity import OpportunityCreate, OpportunityCategory
from src.ai.embeddings import EmbeddingService
from src.crawlers.base_crawler import BaseCrawler


class TestOpportunityModels:
    """Test opportunity data models."""
    
    def test_opportunity_create(self):
        """Test creating an opportunity."""
        opportunity = OpportunityCreate(
            title="Software Engineer",
            description="Join our team as a software engineer.",
            category=OpportunityCategory.JOB,
            link="https://example.com/job",
            source="example.com"
        )
        
        assert opportunity.title == "Software Engineer"
        assert opportunity.category == OpportunityCategory.JOB
        assert str(opportunity.link) == "https://example.com/job"
    
    def test_opportunity_categories(self):
        """Test all opportunity categories are valid."""
        categories = [
            OpportunityCategory.JOB,
            OpportunityCategory.INTERNSHIP,
            OpportunityCategory.SCHOLARSHIP,
            OpportunityCategory.RESEARCH,
            OpportunityCategory.COMPETITION,
            OpportunityCategory.GRANT,
            OpportunityCategory.OTHER
        ]
        
        assert len(categories) == 7
        assert OpportunityCategory.JOB.value == "job"
        assert OpportunityCategory.INTERNSHIP.value == "internship"


class TestEmbeddingService:
    """Test embedding service functionality."""
    
    @pytest.mark.asyncio
    async def test_embedding_service_initialization(self):
        """Test that embedding service can be initialized."""
        with patch('src.ai.embeddings.SBERT_AVAILABLE', True), \
             patch('src.ai.embeddings.SentenceTransformer') as mock_sbert:
            
            # Mock the SentenceTransformer
            mock_model = Mock()
            mock_sbert.return_value = mock_model
            
            service = EmbeddingService()
            assert service.sbert_model is not None
    
    @pytest.mark.asyncio
    async def test_compute_relevance_score(self):
        """Test relevance score computation."""
        with patch('src.ai.embeddings.SBERT_AVAILABLE', True), \
             patch('src.ai.embeddings.SentenceTransformer') as mock_sbert:
            
            mock_model = Mock()
            mock_sbert.return_value = mock_model
            
            service = EmbeddingService()
            service.user_interest_vectors = [[1, 0, 0], [0, 1, 0]]  # Mock vectors
            
            # Test perfect match
            score = service.compute_relevance_score([1, 0, 0])
            assert isinstance(score, float)
            assert 0 <= score <= 1


class MockCrawler(BaseCrawler):
    """Mock crawler for testing."""
    
    def __init__(self):
        super().__init__("test_crawler", "example.com")
    
    async def get_entry_points(self):
        return ["https://example.com/careers"]
    
    async def extract_opportunities(self, html_content, source_url):
        # Return a mock opportunity
        return [
            OpportunityCreate(
                title="Test Job",
                description="This is a test job posting.",
                category=OpportunityCategory.JOB,
                link="https://example.com/job/1",
                source="example.com"
            )
        ]


class TestBaseCrawler:
    """Test base crawler functionality."""
    
    def test_crawler_initialization(self):
        """Test crawler can be initialized."""
        crawler = MockCrawler()
        assert crawler.name == "test_crawler"
        assert crawler.domain == "example.com"
    
    @pytest.mark.asyncio
    async def test_extract_opportunities(self):
        """Test opportunity extraction."""
        crawler = MockCrawler()
        html = "<html><body>Test content</body></html>"
        
        opportunities = await crawler.extract_opportunities(html, "https://example.com")
        
        assert len(opportunities) == 1
        assert opportunities[0].title == "Test Job"
        assert opportunities[0].source == "example.com"
    
    def test_create_hash_key(self):
        """Test hash key creation for deduplication."""
        crawler = MockCrawler()
        
        hash1 = crawler.create_hash_key("Software Engineer", "https://example.com/job")
        hash2 = crawler.create_hash_key("Software Engineer", "https://example.com/job")
        hash3 = crawler.create_hash_key("Data Scientist", "https://example.com/job")
        
        assert hash1 == hash2  # Same input should produce same hash
        assert hash1 != hash3  # Different input should produce different hash
        assert len(hash1) == 32  # MD5 hash length
    
    def test_is_relevant_link(self):
        """Test link relevance filtering."""
        crawler = MockCrawler()
        
        # Test relevant links
        assert crawler._is_relevant_link("https://example.com/careers", "careers")
        assert crawler._is_relevant_link("https://example.com/jobs", "view job")
        assert crawler._is_relevant_link("https://example.com/internship", "apply")
        
        # Test irrelevant links
        assert not crawler._is_relevant_link("https://other.com/careers", "careers")  # Different domain
        assert not crawler._is_relevant_link("https://example.com/privacy", "privacy")
        assert not crawler._is_relevant_link("mailto:contact@example.com", "contact")
        assert not crawler._is_relevant_link("https://example.com/file.pdf", "download")


class TestConfiguration:
    """Test configuration loading."""
    
    def test_config_import(self):
        """Test that configuration can be imported."""
        from src.config import settings, TARGET_DOMAINS, USER_INTERESTS
        
        assert hasattr(settings, 'environment')
        assert hasattr(settings, 'log_level')
        assert isinstance(TARGET_DOMAINS, dict)
        assert isinstance(USER_INTERESTS, list)
        assert len(USER_INTERESTS) > 0
    
    def test_target_domains(self):
        """Test target domains configuration."""
        from src.config import TARGET_DOMAINS
        
        assert "companies" in TARGET_DOMAINS
        assert isinstance(TARGET_DOMAINS["companies"], list)
        assert len(TARGET_DOMAINS["companies"]) > 0
    
    def test_user_interests(self):
        """Test user interests configuration."""
        from src.config import USER_INTERESTS
        
        assert len(USER_INTERESTS) > 0
        assert all(isinstance(interest, str) for interest in USER_INTERESTS)
        assert any("software" in interest.lower() for interest in USER_INTERESTS)


@pytest.mark.asyncio
async def test_database_models():
    """Test database model serialization."""
    from src.models.opportunity import OpportunityInDB
    
    opportunity = OpportunityInDB(
        title="Test Opportunity",
        description="A test opportunity for unit testing.",
        category=OpportunityCategory.JOB,
        link="https://example.com/test",
        source="test.com",
        vector=[0.1, 0.2, 0.3],
        score=0.85,
        hash_key="test123"
    )
    
    # Test serialization
    data = opportunity.dict()
    assert data["title"] == "Test Opportunity"
    assert data["score"] == 0.85
    assert data["vector"] == [0.1, 0.2, 0.3]
    
    # Test that required fields are present
    required_fields = ["title", "description", "category", "link", "source"]
    for field in required_fields:
        assert field in data


def test_imports():
    """Test that all main modules can be imported without errors."""
    try:
        from src import config
        from src.models import opportunity
        from src.database import mongodb
        from src.crawlers import base_crawler
        from src.ai import embeddings
        from src.services import email_service, scheduler, orchestrator
        
        # If we get here, all imports succeeded
        assert True
    except ImportError as e:
        pytest.fail(f"Import error: {e}")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
