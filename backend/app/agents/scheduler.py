"""
Scheduler for Automated Organization Updates

Implements weekly automated jobs using APScheduler:
- Update existing organizations with fresh web data
- Validate and refresh organization information
- Generate reports on data quality

Can be run as:
1. Background thread in FastAPI
2. Standalone service
3. Celery Beat tasks
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.base import async_session_maker
from ..models.db_models import Organization, ScrapedData, ScrapingSession
from .graph import run_agent_pipeline
from .scraper import ScraperAgent
from .evaluator import EvaluatorAgent
from .langsmith_config import configure_langsmith

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure LangSmith
configure_langsmith()

# Global scheduler instance
scheduler: Optional[AsyncIOScheduler] = None


async def update_organization(organization: Organization, db: AsyncSession) -> dict:
    """
    Update a single organization with fresh web data.
    
    Args:
        organization: Organization to update
        db: Database session
        
    Returns:
        Update result dictionary
    """
    logger.info(f"Updating organization: {organization.name}")
    
    try:
        # Use scraper agent to find updated information
        scraper = ScraperAgent()
        result = await scraper.search_specific_organization(
            name=organization.name,
            location=organization.department
        )
        
        organizations_found = result.get("organizations_found", [])
        
        if organizations_found:
            # Validate the new data
            evaluator = EvaluatorAgent()
            validation = evaluator.quick_validate(organizations_found)
            
            if validation.get("evaluation_passed", False):
                # Update organization with new data
                new_data = organizations_found[0]
                
                if new_data.get("description"):
                    organization.description = new_data["description"]
                if new_data.get("latitude"):
                    organization.latitude = new_data["latitude"]
                if new_data.get("longitude"):
                    organization.longitude = new_data["longitude"]
                
                organization.updated_at = datetime.utcnow()
                
                # Log the update
                logger.info(f"Updated organization {organization.name} with fresh data")
                
                return {
                    "organization_id": organization.id,
                    "name": organization.name,
                    "status": "updated",
                    "changes": True,
                }
        
        return {
            "organization_id": organization.id,
            "name": organization.name,
            "status": "no_updates",
            "changes": False,
        }
        
    except Exception as e:
        logger.error(f"Error updating {organization.name}: {e}")
        return {
            "organization_id": organization.id,
            "name": organization.name,
            "status": "error",
            "error": str(e),
        }


async def weekly_organization_update():
    """
    Weekly job to update all organizations.
    Runs every Sunday at 2:00 AM.
    """
    logger.info("Starting weekly organization update job")
    
    async with async_session_maker() as db:
        try:
            # Get all active organizations
            result = await db.execute(
                select(Organization).where(Organization.status == "active")
            )
            organizations = result.scalars().all()
            
            logger.info(f"Found {len(organizations)} organizations to update")
            
            # Create scraping session for tracking
            session = ScrapingSession(
                status="running",
                started_at=datetime.utcnow(),
                total_urls=len(organizations),
            )
            db.add(session)
            await db.commit()
            
            # Update each organization
            results = []
            updated_count = 0
            error_count = 0
            
            for organization in organizations:
                result = await update_organization(organization, db)
                results.append(result)
                
                if result.get("status") == "updated":
                    updated_count += 1
                elif result.get("status") == "error":
                    error_count += 1
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(2)
            
            # Update session status
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            session.urls_processed = len(organizations)
            session.urls_successful = updated_count
            session.urls_failed = error_count
            
            await db.commit()
            
            logger.info(f"Weekly update completed: {updated_count} updated, {error_count} errors")
            
            return {
                "job": "weekly_organization_update",
                "timestamp": datetime.utcnow().isoformat(),
                "total": len(organizations),
                "updated": updated_count,
                "errors": error_count,
            }
            
        except Exception as e:
            logger.error(f"Weekly update job failed: {e}")
            raise


async def daily_health_check():
    """
    Daily health check job.
    Validates system components and reports status.
    """
    logger.info("Running daily health check")
    
    checks = {
        "database": False,
        "agents": False,
        "api_keys": False,
    }
    
    # Check database
    try:
        async with async_session_maker() as db:
            await db.execute(select(1))
            checks["database"] = True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
    
    # Check API keys
    checks["api_keys"] = all([
        os.getenv("OPENAI_API_KEY"),
        os.getenv("TAVILY_API_KEY"),
    ])
    
    # Check agents can be imported
    try:
        from ..agents import OrchestratorAgent, ScraperAgent
        checks["agents"] = True
    except Exception as e:
        logger.error(f"Agent import check failed: {e}")
    
    all_healthy = all(checks.values())
    
    logger.info(f"Health check: {'PASS' if all_healthy else 'FAIL'} - {checks}")
    
    return {
        "job": "daily_health_check",
        "timestamp": datetime.utcnow().isoformat(),
        "healthy": all_healthy,
        "checks": checks,
    }


async def search_new_organizations(department: Optional[str] = None):
    """
    Job to search for new organizations that aren't in the database.
    
    Args:
        department: Optional department to focus search on
    """
    logger.info(f"Searching for new organizations in {department or 'all departments'}")
    
    query = f"organizaciones mujeres constructoras paz {department or 'Colombia'}"
    session_id = f"scheduler_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        result = await run_agent_pipeline(query, session_id)
        
        logger.info(f"New organizations search completed: {result.get('success')}")
        
        return {
            "job": "search_new_organizations",
            "department": department,
            "timestamp": datetime.utcnow().isoformat(),
            "result": result,
        }
        
    except Exception as e:
        logger.error(f"New organizations search failed: {e}")
        raise


def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure the scheduler.
    
    Returns:
        Configured AsyncIOScheduler
    """
    sched = AsyncIOScheduler(timezone="America/Bogota")
    
    # Weekly organization update - Sundays at 2:00 AM
    sched.add_job(
        weekly_organization_update,
        CronTrigger(day_of_week="sun", hour=2, minute=0),
        id="weekly_organization_update",
        name="Weekly Organization Update",
        replace_existing=True,
    )
    
    # Daily health check - Every day at 6:00 AM
    sched.add_job(
        daily_health_check,
        CronTrigger(hour=6, minute=0),
        id="daily_health_check",
        name="Daily Health Check",
        replace_existing=True,
    )
    
    # Monthly new organization search - First Sunday of each month
    sched.add_job(
        search_new_organizations,
        CronTrigger(day="1-7", day_of_week="sun", hour=3, minute=0),
        id="monthly_new_organizations",
        name="Monthly New Organizations Search",
        replace_existing=True,
    )
    
    return sched


def start_scheduler():
    """Start the global scheduler."""
    global scheduler
    
    if scheduler is None:
        scheduler = create_scheduler()
    
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Stop the global scheduler."""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def get_scheduler_jobs() -> List[dict]:
    """
    Get list of scheduled jobs.
    
    Returns:
        List of job information dictionaries
    """
    global scheduler
    
    if scheduler is None:
        return []
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    
    return jobs


async def run_job_now(job_id: str) -> dict:
    """
    Manually trigger a scheduled job.
    
    Args:
        job_id: ID of the job to run
        
    Returns:
        Job result
    """
    global scheduler
    
    if scheduler is None:
        raise ValueError("Scheduler not initialized")
    
    job = scheduler.get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")
    
    logger.info(f"Manually triggering job: {job_id}")
    
    # Run the job function
    result = await job.func()
    
    return result


# Celery tasks (alternative to APScheduler)
try:
    from celery import Celery
    
    celery_app = Celery(
        "organization_tasks",
        broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
        backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    )
    
    @celery_app.task
    def celery_weekly_update():
        """Celery task for weekly update."""
        return asyncio.run(weekly_organization_update())
    
    @celery_app.task
    def celery_health_check():
        """Celery task for health check."""
        return asyncio.run(daily_health_check())
    
    @celery_app.task
    def celery_search_new(department: str = None):
        """Celery task for new organization search."""
        return asyncio.run(search_new_organizations(department))
    
    # Celery Beat schedule
    celery_app.conf.beat_schedule = {
        "weekly-organization-update": {
            "task": "app.agents.scheduler.celery_weekly_update",
            "schedule": timedelta(weeks=1),
        },
        "daily-health-check": {
            "task": "app.agents.scheduler.celery_health_check",
            "schedule": timedelta(days=1),
        },
    }
    
except ImportError:
    celery_app = None
    logger.info("Celery not available, using APScheduler only")
