"""
Main application entry point for the Opportunist AI-driven opportunity aggregator.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click
from loguru import logger

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.config import settings
from src.database.mongodb import init_database, close_database, db_manager
from src.ai.embeddings import initialize_embedding_service, close_embedding_service
from src.services.scheduler import start_scheduler, stop_scheduler, run_task_manually
from src.services.orchestrator import orchestrator
from src.services.email_service import send_test_email
from src.models.opportunity import UserProfile


# Configure logging
def setup_logging():
    """Setup logging configuration."""
    log_level = settings.log_level
    
    # Remove default logger
    logger.remove()
    
    # Add console logger
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add file logger
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / "opportunist.log",
        level=log_level,
        rotation="1 day",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug mode')
def cli(debug):
    """Opportunist - AI-driven opportunity aggregator."""
    if debug:
        os.environ["LOG_LEVEL"] = "DEBUG"
    
    setup_logging()
    logger.info(f"Starting Opportunist in {settings.environment} mode")


@cli.command()
@click.option('--daemon', is_flag=True, help='Run as daemon (background process)')
async def start(daemon):
    """Start the Opportunist scheduler."""
    logger.info("Starting Opportunist scheduler")
    
    try:
        # Initialize services
        await init_database()
        await initialize_embedding_service()
        
        if daemon:
            logger.info("Running in daemon mode")
            # For production, this would use proper daemonization
            await start_scheduler()
        else:
            logger.info("Running in foreground mode")
            await start_scheduler()
            
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        raise
    finally:
        await stop_scheduler()
        await close_embedding_service()
        await close_database()


@cli.command()
@click.argument('task', type=click.Choice(['crawl', 'process', 'send_emails', 'full_pipeline']))
async def run(task):
    """Run a specific task manually."""
    logger.info(f"Running task: {task}")
    
    try:
        # Initialize services
        await init_database()
        await initialize_embedding_service()
        
        # Run the task
        result = await run_task_manually(task)
        
        logger.info(f"Task completed: {result}")
        click.echo(f"Task '{task}' completed successfully")
        
        if result.get('error'):
            click.echo(f"Error: {result['error']}", err=True)
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Error running task {task}: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        await close_embedding_service()
        await close_database()


@cli.command()
async def status():
    """Get pipeline status and health information."""
    try:
        await init_database()
        
        # Get pipeline status
        status_info = await orchestrator.get_pipeline_status()
        
        # Get health check
        health_info = await orchestrator.run_health_check()
        
        click.echo("\n=== Pipeline Status ===")
        click.echo(f"Timestamp: {status_info.get('timestamp')}")
        click.echo(f"Total opportunities (24h): {status_info.get('total_opportunities_24h', 0)}")
        
        click.echo("\nOpportunities by category:")
        for category, count in status_info.get('opportunity_counts_24h', {}).items():
            click.echo(f"  {category}: {count}")
        
        click.echo("\n=== Health Status ===")
        click.echo(f"Overall status: {health_info.get('overall_status')}")
        
        for component, status in health_info.get('components', {}).items():
            status_emoji = "✅" if status == "healthy" else "❌"
            click.echo(f"  {status_emoji} {component}: {status}")
        
        click.echo("\n=== Configuration ===")
        config = status_info.get('configuration', {})
        click.echo(f"  Relevance threshold: {config.get('relevance_threshold')}")
        click.echo(f"  Max crawl pages: {config.get('max_crawl_pages')}")
        click.echo(f"  Email schedule: {config.get('email_schedule_time')}")
        click.echo(f"  Target domains: {config.get('target_domains_count')}")
    
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        await close_database()


@cli.command()
@click.argument('email')
async def add_user(email):
    """Add a new user for daily digests."""
    try:
        await init_database()
        
        # Create user profile
        user = UserProfile(email=email)
        
        # Save to database
        user_id = await db_manager.create_user(user)
        
        click.echo(f"✅ User '{email}' added successfully (ID: {user_id})")
        logger.info(f"Added user: {email}")
    
    except Exception as e:
        logger.error(f"Error adding user {email}: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        await close_database()


@cli.command()
@click.argument('email')
async def test_email(email):
    """Send a test email to verify configuration."""
    try:
        await init_database()
        await initialize_embedding_service()
        
        click.echo(f"Sending test email to {email}...")
        success = await send_test_email(email)
        
        if success:
            click.echo("✅ Test email sent successfully!")
        else:
            click.echo("❌ Failed to send test email", err=True)
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        await close_embedding_service()
        await close_database()


@cli.command()
async def init():
    """Initialize the application (database, indexes, etc.)."""
    try:
        click.echo("Initializing Opportunist...")
        
        # Initialize database
        click.echo("Setting up database connection and indexes...")
        await init_database()
        
        # Initialize embedding service
        click.echo("Initializing AI embedding service...")
        await initialize_embedding_service()
        
        # Create default user if configured
        if settings.sendgrid_to_email:
            try:
                user = UserProfile(email=settings.sendgrid_to_email)
                await db_manager.create_user(user)
                click.echo(f"Created default user: {settings.sendgrid_to_email}")
            except Exception as e:
                if "duplicate" in str(e).lower():
                    click.echo(f"User {settings.sendgrid_to_email} already exists")
                else:
                    raise e
        
        click.echo("✅ Initialization completed successfully!")
        
        # Show next steps
        click.echo("\nNext steps:")
        click.echo("1. Configure your .env file with API keys")
        click.echo("2. Run 'python main.py test-email <your-email>' to test email configuration")
        click.echo("3. Run 'python main.py run full_pipeline' to test the complete pipeline")
        click.echo("4. Run 'python main.py start' to begin scheduled operations")
    
    except Exception as e:
        logger.error(f"Error during initialization: {e}")
        click.echo(f"❌ Initialization failed: {e}", err=True)
        sys.exit(1)
    finally:
        await close_embedding_service()
        await close_database()


@cli.command()
@click.option('--days', default=7, help='Number of days of data to clean up')
async def cleanup(days):
    """Clean up old data from the database."""
    try:
        await init_database()
        
        click.echo(f"Cleaning up data older than {days} days...")
        result = await orchestrator.cleanup_old_data(days)
        
        click.echo("✅ Cleanup completed")
        logger.info(f"Cleanup result: {result}")
    
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        await close_database()


# Async click support
def async_command(f):
    """Decorator to support async click commands."""
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


# Apply async decorator to all async commands
for command_name in ['start', 'run', 'status', 'add_user', 'test_email', 'init', 'cleanup']:
    command = cli.commands[command_name]
    command.callback = async_command(command.callback)


if __name__ == '__main__':
    cli()
