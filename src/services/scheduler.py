"""
Task scheduler for automated crawling and email delivery.
"""

import asyncio
from datetime import datetime, time
from typing import Dict, Any, Optional
from loguru import logger

try:
    from celery import Celery
    from celery.schedules import crontab
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    logger.warning("Celery not available, using simple scheduler")

from src.config import settings
from src.services.orchestrator import OrchestrationService
from src.services.email_service import email_service
from src.database.mongodb import init_database, close_database
from src.ai.embeddings import initialize_embedding_service


class SimpleScheduler:
    """Simple scheduler for when Celery is not available."""
    
    def __init__(self):
        self.orchestrator = OrchestrationService()
        self.running = False
    
    async def start(self):
        """Start the scheduler."""
        logger.info("Starting simple scheduler")
        self.running = True
        
        # Initialize services
        await init_database()
        await initialize_embedding_service()
        
        # Run scheduler loop
        while self.running:
            try:
                await self._check_and_run_tasks()
                # Check every minute
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """Stop the scheduler."""
        logger.info("Stopping scheduler")
        self.running = False
        await close_database()
    
    async def _check_and_run_tasks(self):
        """Check if it's time to run scheduled tasks."""
        now = datetime.now()
        
        # Parse schedule time (default: 07:00)
        schedule_time_str = settings.email_schedule_time
        try:
            schedule_hour, schedule_minute = map(int, schedule_time_str.split(':'))
        except:
            schedule_hour, schedule_minute = 7, 0
        
        # Check if it's time for daily digest
        if (now.hour == schedule_hour and 
            now.minute == schedule_minute and 
            now.second < 60):  # Run within the first minute
            
            logger.info("Running daily digest task")
            await self._run_daily_digest_task()
    
    async def _run_daily_digest_task(self):
        """Run the complete daily digest pipeline."""
        try:
            # Run full orchestration pipeline
            result = await self.orchestrator.run_daily_pipeline()
            
            logger.info(f"Daily pipeline completed: {result}")
            
        except Exception as e:
            logger.error(f"Error in daily digest task: {e}")
    
    async def run_manual_task(self, task_name: str) -> Dict[str, Any]:
        """Run a task manually."""
        logger.info(f"Running manual task: {task_name}")
        
        try:
            if task_name == "crawl":
                return await self.orchestrator.crawl_all_sources()
            elif task_name == "process":
                return await self.orchestrator.process_opportunities()
            elif task_name == "send_emails":
                return await email_service.send_daily_digests()
            elif task_name == "full_pipeline":
                return await self.orchestrator.run_daily_pipeline()
            else:
                raise ValueError(f"Unknown task: {task_name}")
                
        except Exception as e:
            logger.error(f"Error running manual task {task_name}: {e}")
            return {"error": str(e)}


class CeleryScheduler:
    """Celery-based scheduler for production use."""
    
    def __init__(self):
        if not CELERY_AVAILABLE:
            raise RuntimeError("Celery not available")
        
        # Initialize Celery app
        self.app = Celery(
            'opportunist',
            broker=settings.redis_url,
            backend=settings.redis_url
        )
        
        # Configure Celery
        self.app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone=settings.timezone,
            enable_utc=True,
            result_expires=3600,  # 1 hour
        )
        
        # Parse schedule time
        try:
            schedule_hour, schedule_minute = map(int, settings.email_schedule_time.split(':'))
        except:
            schedule_hour, schedule_minute = 7, 0
        
        # Configure periodic tasks
        self.app.conf.beat_schedule = {
            'daily-digest': {
                'task': 'src.services.scheduler.run_daily_pipeline',
                'schedule': crontab(hour=schedule_hour, minute=schedule_minute),
            },
            'health-check': {
                'task': 'src.services.scheduler.health_check',
                'schedule': crontab(minute='*/30'),  # Every 30 minutes
            },
        }
    
    def get_app(self):
        """Get the Celery app instance."""
        return self.app


# Celery tasks (defined at module level for discovery)
if CELERY_AVAILABLE:
    # Create a Celery app instance for task definitions
    celery_app = Celery(
        'opportunist',
        broker=settings.redis_url,
        backend=settings.redis_url
    )
    
    @celery_app.task(bind=True)
    def run_daily_pipeline(self):
        """Celery task for daily pipeline."""
        async def _run():
            await init_database()
            await initialize_embedding_service()
            
            orchestrator = OrchestrationService()
            result = await orchestrator.run_daily_pipeline()
            
            await close_database()
            return result
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_run())
            return result
        finally:
            loop.close()
    
    @celery_app.task
    def crawl_sources():
        """Celery task for crawling sources."""
        async def _run():
            await init_database()
            await initialize_embedding_service()
            
            orchestrator = OrchestrationService()
            result = await orchestrator.crawl_all_sources()
            
            await close_database()
            return result
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    
    @celery_app.task
    def process_opportunities():
        """Celery task for processing opportunities."""
        async def _run():
            await init_database()
            await initialize_embedding_service()
            
            orchestrator = OrchestrationService()
            result = await orchestrator.process_opportunities()
            
            await close_database()
            return result
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    
    @celery_app.task
    def send_emails():
        """Celery task for sending emails."""
        async def _run():
            await init_database()
            return await email_service.send_daily_digests()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    
    @celery_app.task
    def health_check():
        """Health check task."""
        try:
            # Basic health checks
            async def _check():
                await init_database()
                # Test database connection
                from src.database.mongodb import db_manager
                await db_manager.connect()
                await db_manager.close()
                return {"status": "healthy", "timestamp": datetime.now().isoformat()}
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_check())
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}


class SchedulerManager:
    """Manager for choosing and running the appropriate scheduler."""
    
    def __init__(self, use_celery: bool = None):
        if use_celery is None:
            use_celery = CELERY_AVAILABLE and settings.environment == "production"
        
        self.use_celery = use_celery
        
        if self.use_celery:
            self.scheduler = CeleryScheduler()
            logger.info("Using Celery scheduler")
        else:
            self.scheduler = SimpleScheduler()
            logger.info("Using simple scheduler")
    
    async def start(self):
        """Start the scheduler."""
        if self.use_celery:
            # For Celery, we need to start both worker and beat
            logger.info("Celery scheduler configured. Start worker and beat separately:")
            logger.info("Worker: celery -A src.services.scheduler.celery_app worker --loglevel=info")
            logger.info("Beat: celery -A src.services.scheduler.celery_app beat --loglevel=info")
        else:
            await self.scheduler.start()
    
    async def stop(self):
        """Stop the scheduler."""
        if not self.use_celery:
            await self.scheduler.stop()
    
    async def run_manual_task(self, task_name: str) -> Dict[str, Any]:
        """Run a task manually."""
        if self.use_celery:
            # For Celery, trigger the task
            if task_name == "crawl":
                task = crawl_sources.delay()
            elif task_name == "process":
                task = process_opportunities.delay()
            elif task_name == "send_emails":
                task = send_emails.delay()
            elif task_name == "full_pipeline":
                task = run_daily_pipeline.delay()
            else:
                return {"error": f"Unknown task: {task_name}"}
            
            return {"task_id": task.id, "status": "submitted"}
        else:
            return await self.scheduler.run_manual_task(task_name)
    
    def get_celery_app(self):
        """Get Celery app if using Celery scheduler."""
        if self.use_celery:
            return self.scheduler.get_app()
        return None


# Global scheduler instance
scheduler_manager = SchedulerManager()


# Convenience functions
async def start_scheduler():
    """Start the global scheduler."""
    await scheduler_manager.start()


async def stop_scheduler():
    """Stop the global scheduler."""
    await scheduler_manager.stop()


async def run_task_manually(task_name: str) -> Dict[str, Any]:
    """Run a task manually using the global scheduler."""
    return await scheduler_manager.run_manual_task(task_name)


def get_celery_app():
    """Get the Celery app instance."""
    return scheduler_manager.get_celery_app()
