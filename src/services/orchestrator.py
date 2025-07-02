"""
Orchestration service that coordinates the entire pipeline.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from loguru import logger

from src.crawlers.company_crawler import CompanyCrawlerManager
from src.ai.embeddings import embedding_service
from src.services.email_service import email_service
from src.database.mongodb import db_manager
from src.models.opportunity import OpportunityCreate, OpportunityInDB, OpportunityCategory
from src.config import settings, TARGET_DOMAINS


class OrchestrationService:
    """Main orchestration service for the opportunity aggregator pipeline."""
    
    def __init__(self):
        self.company_crawler_manager = CompanyCrawlerManager()
        self.stats = {
            "crawled_opportunities": 0,
            "processed_opportunities": 0,
            "relevant_opportunities": 0,
            "emails_sent": 0,
            "errors": []
        }
    
    async def run_daily_pipeline(self) -> Dict[str, Any]:
        """Run the complete daily pipeline: crawl -> process -> filter -> send emails."""
        start_time = datetime.now()
        logger.info("Starting daily pipeline")
        
        try:
            # Step 1: Crawl all sources
            crawl_result = await self.crawl_all_sources()
            
            # Step 2: Process and filter opportunities
            process_result = await self.process_opportunities()
            
            # Step 3: Send email digests
            email_result = await email_service.send_daily_digests()
            
            # Compile final results
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            final_result = {
                "status": "completed",
                "duration_seconds": duration,
                "timestamp": end_time.isoformat(),
                "crawl_stats": crawl_result,
                "process_stats": process_result,
                "email_stats": email_result,
                "summary": {
                    "total_opportunities_found": crawl_result.get("total_opportunities", 0),
                    "relevant_opportunities": process_result.get("relevant_count", 0),
                    "emails_sent": email_result.get("sent", 0),
                    "emails_failed": email_result.get("failed", 0)
                }
            }
            
            logger.info(f"Daily pipeline completed in {duration:.2f} seconds: {final_result['summary']}")
            return final_result
            
        except Exception as e:
            logger.error(f"Error in daily pipeline: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": (datetime.now() - start_time).total_seconds()
            }
    
    async def crawl_all_sources(self) -> Dict[str, Any]:
        """Crawl all configured sources for opportunities."""
        start_time = datetime.now()
        logger.info("Starting crawl of all sources")
        
        crawl_stats = {
            "companies": {},
            "universities": {},
            "errors": [],
            "total_opportunities": 0
        }
        
        try:
            # Crawl company career pages
            company_opportunities = await self._crawl_companies()
            crawl_stats["companies"] = {
                "count": len(company_opportunities),
                "opportunities": company_opportunities
            }
            crawl_stats["total_opportunities"] += len(company_opportunities)
            
            # TODO: Add university crawlers
            # university_opportunities = await self._crawl_universities()
            # crawl_stats["universities"] = {
            #     "count": len(university_opportunities),
            #     "opportunities": university_opportunities
            # }
            
            # TODO: Add social media crawlers
            # social_opportunities = await self._crawl_social_media()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            crawl_stats.update({
                "status": "completed",
                "duration_seconds": duration,
                "timestamp": end_time.isoformat()
            })
            
            logger.info(f"Crawling completed in {duration:.2f}s. Found {crawl_stats['total_opportunities']} opportunities")
            return crawl_stats
            
        except Exception as e:
            error_msg = f"Error crawling sources: {e}"
            logger.error(error_msg)
            crawl_stats["errors"].append(error_msg)
            crawl_stats["status"] = "failed"
            return crawl_stats
    
    async def _crawl_companies(self) -> List[OpportunityCreate]:
        """Crawl company career pages."""
        try:
            # Limit pages per domain to manage resources
            max_pages = min(50, settings.max_crawl_pages // len(TARGET_DOMAINS.get("companies", [])))
            
            opportunities = await self.company_crawler_manager.crawl_all(max_pages)
            logger.info(f"Company crawling found {len(opportunities)} opportunities")
            return opportunities
            
        except Exception as e:
            logger.error(f"Error crawling companies: {e}")
            return []
    
    async def process_opportunities(self) -> Dict[str, Any]:
        """Process raw opportunities: filter, score, and store in database."""
        start_time = datetime.now()
        logger.info("Starting opportunity processing")
        
        process_stats = {
            "total_processed": 0,
            "relevant_count": 0,
            "duplicates_filtered": 0,
            "errors": []
        }
        
        try:
            # Get unprocessed opportunities from recent crawls
            cutoff_time = datetime.utcnow() - timedelta(hours=2)  # Process opportunities from last 2 hours
            
            # For MVP, we'll process from a simple queue or re-crawl
            # In production, this would fetch from a queue or unprocessed collection
            logger.info("Re-crawling for processing (MVP approach)")
            raw_opportunities = await self._crawl_companies()
            
            if not raw_opportunities:
                logger.info("No opportunities to process")
                return process_stats
            
            process_stats["total_processed"] = len(raw_opportunities)
            
            # Filter for relevance and compute embeddings
            relevant_opportunities = await embedding_service.filter_relevant_opportunities(
                raw_opportunities,
                threshold=settings.relevance_threshold
            )
            
            process_stats["relevant_count"] = len(relevant_opportunities)
            
            # Store in database with deduplication
            stored_count = 0
            duplicate_count = 0
            
            for opportunity in relevant_opportunities:
                try:
                    # Check for duplicates
                    exists = await db_manager.check_opportunity_exists(opportunity.hash_key)
                    
                    if not exists:
                        await db_manager.insert_opportunity(opportunity)
                        stored_count += 1
                    else:
                        duplicate_count += 1
                        
                except Exception as e:
                    error_msg = f"Error storing opportunity '{opportunity.title}': {e}"
                    logger.error(error_msg)
                    process_stats["errors"].append(error_msg)
            
            process_stats["duplicates_filtered"] = duplicate_count
            process_stats["stored_count"] = stored_count
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            process_stats.update({
                "status": "completed",
                "duration_seconds": duration,
                "timestamp": end_time.isoformat()
            })
            
            logger.info(
                f"Processing completed in {duration:.2f}s. "
                f"Processed: {process_stats['total_processed']}, "
                f"Relevant: {process_stats['relevant_count']}, "
                f"Stored: {stored_count}, "
                f"Duplicates: {duplicate_count}"
            )
            
            return process_stats
            
        except Exception as e:
            error_msg = f"Error processing opportunities: {e}"
            logger.error(error_msg)
            process_stats["errors"].append(error_msg)
            process_stats["status"] = "failed"
            return process_stats
    
    async def get_pipeline_status(self) -> Dict[str, Any]:
        """Get current pipeline status and statistics."""
        try:
            # Get database stats
            crawl_stats = await db_manager.get_crawl_stats(24)
            
            # Get opportunity counts by category
            category_counts = {}
            for category in OpportunityCategory:
                opportunities = await db_manager.get_opportunities_by_category_and_score(
                    category=category,
                    min_score=settings.relevance_threshold,
                    limit=100,
                    hours_back=24
                )
                category_counts[category.value] = len(opportunities)
            
            status = {
                "timestamp": datetime.now().isoformat(),
                "crawl_stats_24h": crawl_stats,
                "opportunity_counts_24h": category_counts,
                "total_opportunities_24h": sum(category_counts.values()),
                "configuration": {
                    "relevance_threshold": settings.relevance_threshold,
                    "max_crawl_pages": settings.max_crawl_pages,
                    "email_schedule_time": settings.email_schedule_time,
                    "target_domains_count": len(TARGET_DOMAINS.get("companies", []))
                }
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting pipeline status: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def run_health_check(self) -> Dict[str, Any]:
        """Run health checks on all components."""
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "healthy",
            "components": {}
        }
        
        try:
            # Check database connection
            try:
                await db_manager.connect()
                health_status["components"]["database"] = "healthy"
            except Exception as e:
                health_status["components"]["database"] = f"unhealthy: {e}"
                health_status["overall_status"] = "unhealthy"
            
            # Check embedding service
            try:
                if embedding_service.openai_client or embedding_service.sbert_model:
                    health_status["components"]["embedding_service"] = "healthy"
                else:
                    health_status["components"]["embedding_service"] = "unhealthy: no models available"
                    health_status["overall_status"] = "unhealthy"
            except Exception as e:
                health_status["components"]["embedding_service"] = f"unhealthy: {e}"
                health_status["overall_status"] = "unhealthy"
            
            # Check email service
            try:
                if email_service.sendgrid_client:
                    health_status["components"]["email_service"] = "healthy"
                else:
                    health_status["components"]["email_service"] = "unhealthy: SendGrid not configured"
                    health_status["overall_status"] = "degraded"
            except Exception as e:
                health_status["components"]["email_service"] = f"unhealthy: {e}"
                health_status["overall_status"] = "degraded"
            
            # Check recent crawl activity
            try:
                recent_crawls = await db_manager.get_crawl_stats(2)  # Last 2 hours
                if recent_crawls:
                    health_status["components"]["crawl_activity"] = "healthy"
                else:
                    health_status["components"]["crawl_activity"] = "warning: no recent crawl activity"
            except Exception as e:
                health_status["components"]["crawl_activity"] = f"error: {e}"
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "overall_status": "error",
                "error": str(e)
            }
    
    async def cleanup_old_data(self, days: int = 7) -> Dict[str, Any]:
        """Clean up old data from database."""
        try:
            # MongoDB TTL indexes should handle most cleanup automatically
            # This is for manual cleanup if needed
            
            cleanup_stats = {
                "timestamp": datetime.now().isoformat(),
                "cleaned_collections": []
            }
            
            # Note: With TTL indexes, manual cleanup may not be necessary
            # But we can add specific cleanup logic here if needed
            
            logger.info("Data cleanup completed (TTL indexes handle automatic cleanup)")
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Error in data cleanup: {e}")
            return {"error": str(e)}


# Global orchestrator instance
orchestrator = OrchestrationService()


# Convenience functions for external use
async def run_daily_pipeline() -> Dict[str, Any]:
    """Run the daily pipeline using the global orchestrator."""
    return await orchestrator.run_daily_pipeline()


async def get_pipeline_status() -> Dict[str, Any]:
    """Get pipeline status using the global orchestrator."""
    return await orchestrator.get_pipeline_status()


async def run_health_check() -> Dict[str, Any]:
    """Run health check using the global orchestrator."""
    return await orchestrator.run_health_check()
