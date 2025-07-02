"""
AI-powered embeddings and relevance scoring for opportunities.
"""

import asyncio
from typing import List, Dict, Tuple, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from loguru import logger

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI not available, falling back to sentence transformers")

try:
    from sentence_transformers import SentenceTransformer
    SBERT_AVAILABLE = True
except ImportError:
    SBERT_AVAILABLE = False
    logger.warning("Sentence transformers not available")

from src.config import settings, USER_INTERESTS
from src.models.opportunity import OpportunityCreate, OpportunityInDB


class EmbeddingService:
    """Service for generating embeddings and computing relevance scores."""
    
    def __init__(self):
        self.openai_client = None
        self.sbert_model = None
        self.user_interest_vectors = None
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize embedding models."""
        # Try OpenAI first
        if OPENAI_AVAILABLE and settings.openai_api_key:
            try:
                self.openai_client = OpenAI(api_key=settings.openai_api_key)
                logger.info("Initialized OpenAI embeddings client")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")
        
        # Fallback to sentence transformers
        if SBERT_AVAILABLE:
            try:
                self.sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Initialized SentenceTransformer model")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize SentenceTransformer: {e}")
        
        logger.error("No embedding model available!")
        raise RuntimeError("Cannot initialize any embedding model")
    
    async def initialize_user_interests(self, interests: List[str] = None) -> None:
        """Pre-compute embeddings for user interests."""
        if interests is None:
            interests = USER_INTERESTS
        
        try:
            logger.info(f"Computing embeddings for {len(interests)} user interests")
            
            if self.openai_client:
                self.user_interest_vectors = await self._get_openai_embeddings(interests)
            elif self.sbert_model:
                self.user_interest_vectors = self._get_sbert_embeddings(interests)
            else:
                raise RuntimeError("No embedding model available")
            
            logger.info("User interest embeddings computed successfully")
            
        except Exception as e:
            logger.error(f"Failed to compute user interest embeddings: {e}")
            raise
    
    async def _get_openai_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings using OpenAI API."""
        embeddings = []
        
        # Process in batches to respect rate limits
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = self.openai_client.embeddings.create(
                    input=batch,
                    model=settings.openai_model
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
                
                # Rate limiting
                if i + batch_size < len(texts):
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"OpenAI API error for batch {i//batch_size + 1}: {e}")
                # Fallback to zero vectors for failed batches
                embeddings.extend([[0.0] * 1536] * len(batch))
        
        return embeddings
    
    def _get_sbert_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings using SentenceTransformers."""
        try:
            embeddings = self.sbert_model.encode(texts, convert_to_tensor=False)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"SentenceTransformer error: {e}")
            # Return zero vectors as fallback
            return [[0.0] * 384] * len(texts)
    
    async def compute_opportunity_embedding(self, opportunity: OpportunityCreate) -> List[float]:
        """Compute embedding for a single opportunity."""
        # Combine title and description for embedding
        text = f"{opportunity.title} {opportunity.description}"
        
        try:
            if self.openai_client:
                embeddings = await self._get_openai_embeddings([text])
                return embeddings[0]
            elif self.sbert_model:
                embeddings = self._get_sbert_embeddings([text])
                return embeddings[0]
            else:
                raise RuntimeError("No embedding model available")
                
        except Exception as e:
            logger.error(f"Failed to compute embedding for opportunity '{opportunity.title}': {e}")
            # Return zero vector as fallback
            dimension = 1536 if self.openai_client else 384
            return [0.0] * dimension
    
    async def compute_batch_embeddings(self, opportunities: List[OpportunityCreate]) -> List[List[float]]:
        """Compute embeddings for multiple opportunities efficiently."""
        texts = [f"{opp.title} {opp.description}" for opp in opportunities]
        
        try:
            if self.openai_client:
                return await self._get_openai_embeddings(texts)
            elif self.sbert_model:
                return self._get_sbert_embeddings(texts)
            else:
                raise RuntimeError("No embedding model available")
                
        except Exception as e:
            logger.error(f"Failed to compute batch embeddings: {e}")
            # Return zero vectors as fallback
            dimension = 1536 if self.openai_client else 384
            return [[0.0] * dimension] * len(opportunities)
    
    def compute_relevance_score(self, opportunity_vector: List[float]) -> float:
        """Compute relevance score against user interests."""
        if not self.user_interest_vectors:
            logger.warning("User interest vectors not initialized")
            return 0.0
        
        try:
            # Convert to numpy arrays
            opp_vector = np.array(opportunity_vector).reshape(1, -1)
            interest_vectors = np.array(self.user_interest_vectors)
            
            # Compute cosine similarities
            similarities = cosine_similarity(opp_vector, interest_vectors)[0]
            
            # Return maximum similarity (best match)
            max_similarity = float(np.max(similarities))
            return max(0.0, min(1.0, max_similarity))  # Clamp to [0, 1]
            
        except Exception as e:
            logger.error(f"Error computing relevance score: {e}")
            return 0.0
    
    async def score_opportunities(self, opportunities: List[OpportunityCreate]) -> List[Tuple[OpportunityCreate, float, List[float]]]:
        """Score multiple opportunities and return with embeddings."""
        if not opportunities:
            return []
        
        logger.info(f"Scoring {len(opportunities)} opportunities")
        
        try:
            # Compute embeddings in batch
            embeddings = await self.compute_batch_embeddings(opportunities)
            
            # Compute relevance scores
            results = []
            for opp, embedding in zip(opportunities, embeddings):
                score = self.compute_relevance_score(embedding)
                results.append((opp, score, embedding))
            
            # Sort by score descending
            results.sort(key=lambda x: x[1], reverse=True)
            
            logger.info(f"Scored opportunities. Average score: {np.mean([r[1] for r in results]):.3f}")
            return results
            
        except Exception as e:
            logger.error(f"Error scoring opportunities: {e}")
            return [(opp, 0.0, []) for opp in opportunities]
    
    async def filter_relevant_opportunities(
        self, 
        opportunities: List[OpportunityCreate], 
        threshold: float = None
    ) -> List[OpportunityInDB]:
        """Filter opportunities above relevance threshold and convert to DB format."""
        if threshold is None:
            threshold = settings.relevance_threshold
        
        scored_opportunities = await self.score_opportunities(opportunities)
        filtered_opportunities = []
        
        for opp, score, embedding in scored_opportunities:
            if score >= threshold:
                # Convert to DB format with score and embedding
                db_opp = OpportunityInDB(
                    **opp.dict(),
                    vector=embedding,
                    score=score,
                    hash_key=self._create_hash_key(opp.title, str(opp.link))
                )
                filtered_opportunities.append(db_opp)
        
        logger.info(f"Filtered {len(filtered_opportunities)} relevant opportunities from {len(opportunities)} (threshold: {threshold})")
        return filtered_opportunities
    
    def _create_hash_key(self, title: str, link: str) -> str:
        """Create hash key for deduplication."""
        import hashlib
        content = f"{title.strip().lower()}{link.strip()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def close(self):
        """Clean up resources."""
        # No explicit cleanup needed for current models
        pass


# Global embedding service instance
embedding_service = EmbeddingService()


class CategoryClassifier:
    """Simple rule-based classifier for opportunity categories."""
    
    @staticmethod
    def classify(title: str, description: str) -> str:
        """Classify opportunity based on title and description."""
        text = f"{title} {description}".lower()
        
        # Define keyword patterns for each category
        category_patterns = {
            "internship": [
                "intern", "internship", "summer program", "co-op", "coop",
                "student", "trainee", "apprentice"
            ],
            "scholarship": [
                "scholarship", "fellowship", "grant", "funding", "award",
                "financial aid", "stipend", "bursary"
            ],
            "research": [
                "research", "phd", "postdoc", "researcher", "scientist",
                "investigation", "study", "academic", "faculty"
            ],
            "competition": [
                "competition", "contest", "challenge", "hackathon",
                "tournament", "prize", "coding contest"
            ],
            "grant": [
                "grant", "funding", "sponsored", "financial", "investment",
                "seed", "venture"
            ]
        }
        
        # Check each category
        for category, keywords in category_patterns.items():
            if any(keyword in text for keyword in keywords):
                return category
        
        # Default to job if no specific category matched
        return "job"


async def initialize_embedding_service():
    """Initialize the global embedding service."""
    await embedding_service.initialize_user_interests()


async def close_embedding_service():
    """Close the global embedding service."""
    await embedding_service.close()
