"""
MongoDB database connection and operations.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel, ASCENDING, DESCENDING
from loguru import logger

from src.config import settings, get_db_collections
from src.models.opportunity import (
    OpportunityInDB, 
    RawPage, 
    CrawlLog, 
    UserProfile, 
    EmailDigest,
    OpportunityCategory
)


class MongoDBManager:
    """MongoDB connection and operations manager."""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self.collections = get_db_collections()
        
    async def connect(self):
        """Establish MongoDB connection."""
        try:
            self.client = AsyncIOMotorClient(settings.mongodb_uri)
            self.database = self.client[settings.mongodb_database]
            
            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB database: {settings.mongodb_database}")
            
            # Create indexes
            await self._create_indexes()
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    async def _create_indexes(self):
        """Create necessary database indexes."""
        try:
            # Opportunities collection indexes
            opportunities_indexes = [
                IndexModel([("posted_at", DESCENDING)]),
                IndexModel([("category", ASCENDING), ("score", DESCENDING)]),
                IndexModel([("hash_key", ASCENDING)], unique=True),
                IndexModel([("crawled_at", ASCENDING)], expireAfterSeconds=30*24*3600)  # 30 days TTL
            ]
            await self.database[self.collections["opportunities"]].create_indexes(opportunities_indexes)
            
            # Raw pages collection with TTL index (7 days)
            raw_pages_indexes = [
                IndexModel([("crawled_at", ASCENDING)], expireAfterSeconds=7*24*3600),
                IndexModel([("url", ASCENDING)]),
                IndexModel([("source_domain", ASCENDING)])
            ]
            await self.database[self.collections["raw_pages"]].create_indexes(raw_pages_indexes)
            
            # Users collection
            users_indexes = [
                IndexModel([("email", ASCENDING)], unique=True),
                IndexModel([("active", ASCENDING)])
            ]
            await self.database[self.collections["users"]].create_indexes(users_indexes)
            
            # Crawl logs with TTL (30 days)
            crawl_logs_indexes = [
                IndexModel([("crawled_at", ASCENDING)], expireAfterSeconds=30*24*3600),
                IndexModel([("status", ASCENDING), ("crawled_at", DESCENDING)])
            ]
            await self.database[self.collections["crawl_logs"]].create_indexes(crawl_logs_indexes)
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")
    
    # Opportunity operations
    async def insert_opportunity(self, opportunity: OpportunityInDB) -> str:
        """Insert a new opportunity."""
        try:
            result = await self.database[self.collections["opportunities"]].insert_one(
                opportunity.dict(by_alias=True, exclude={"id"})
            )
            logger.debug(f"Inserted opportunity: {opportunity.title}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error inserting opportunity: {e}")
            raise
    
    async def get_opportunities_by_date(self, hours_back: int = 24) -> List[OpportunityInDB]:
        """Get opportunities posted within the specified hours."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            cursor = self.database[self.collections["opportunities"]].find({
                "posted_at": {"$gte": cutoff_time}
            }).sort("score", DESCENDING)
            
            opportunities = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                opportunities.append(OpportunityInDB(**doc))
            
            return opportunities
        except Exception as e:
            logger.error(f"Error fetching opportunities: {e}")
            return []
    
    async def get_opportunities_by_category_and_score(
        self, 
        category: OpportunityCategory, 
        min_score: float, 
        limit: int,
        hours_back: int = 24
    ) -> List[OpportunityInDB]:
        """Get top opportunities by category and minimum score."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            cursor = self.database[self.collections["opportunities"]].find({
                "category": category.value,
                "score": {"$gte": min_score},
                "posted_at": {"$gte": cutoff_time}
            }).sort("score", DESCENDING).limit(limit)
            
            opportunities = []
            async for doc in cursor:
                doc["id"] = str(doc["_id"])
                opportunities.append(OpportunityInDB(**doc))
            
            return opportunities
        except Exception as e:
            logger.error(f"Error fetching opportunities by category: {e}")
            return []
    
    async def update_opportunity_score(self, opportunity_id: str, score: float, vector: List[float]):
        """Update opportunity with AI score and vector."""
        try:
            await self.database[self.collections["opportunities"]].update_one(
                {"_id": opportunity_id},
                {"$set": {"score": score, "vector": vector}}
            )
        except Exception as e:
            logger.error(f"Error updating opportunity score: {e}")
            raise
    
    # Raw pages operations
    async def insert_raw_page(self, raw_page: RawPage) -> str:
        """Insert raw page data."""
        try:
            result = await self.database[self.collections["raw_pages"]].insert_one(
                raw_page.dict()
            )
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error inserting raw page: {e}")
            raise
    
    # User operations
    async def create_user(self, user: UserProfile) -> str:
        """Create a new user profile."""
        try:
            result = await self.database[self.collections["users"]].insert_one(
                user.dict()
            )
            logger.info(f"Created user profile: {user.email}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise
    
    async def get_active_users(self) -> List[UserProfile]:
        """Get all active users."""
        try:
            cursor = self.database[self.collections["users"]].find({"active": True})
            users = []
            async for doc in cursor:
                users.append(UserProfile(**doc))
            return users
        except Exception as e:
            logger.error(f"Error fetching active users: {e}")
            return []
    
    # Crawl log operations
    async def log_crawl(self, crawl_log: CrawlLog):
        """Log crawl operation."""
        try:
            await self.database[self.collections["crawl_logs"]].insert_one(
                crawl_log.dict()
            )
        except Exception as e:
            logger.error(f"Error logging crawl: {e}")
    
    async def get_crawl_stats(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get crawling statistics."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            pipeline = [
                {"$match": {"crawled_at": {"$gte": cutoff_time}}},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_response_time": {"$avg": "$response_time"}
                }}
            ]
            
            stats = {}
            async for doc in self.database[self.collections["crawl_logs"]].aggregate(pipeline):
                stats[doc["_id"]] = {
                    "count": doc["count"],
                    "avg_response_time": doc.get("avg_response_time", 0)
                }
            
            return stats
        except Exception as e:
            logger.error(f"Error getting crawl stats: {e}")
            return {}
    
    # Deduplication
    async def check_opportunity_exists(self, hash_key: str) -> bool:
        """Check if opportunity already exists by hash."""
        try:
            count = await self.database[self.collections["opportunities"]].count_documents(
                {"hash_key": hash_key}
            )
            return count > 0
        except Exception as e:
            logger.error(f"Error checking opportunity existence: {e}")
            return False


# Global database manager instance
db_manager = MongoDBManager()


# Convenience functions
async def get_database() -> AsyncIOMotorDatabase:
    """Get database instance."""
    if not db_manager.database:
        await db_manager.connect()
    return db_manager.database


async def init_database():
    """Initialize database connection."""
    await db_manager.connect()


async def close_database():
    """Close database connection."""
    await db_manager.close()
