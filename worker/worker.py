"""
Celery worker for background tasks.
Handles scraping and other async operations.
"""
import os
import asyncio
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Create Celery app
celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["worker.worker"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # Soft limit 9 minutes
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
    result_expires=3600,  # Results expire after 1 hour
)


def run_async(coro):
    """
    Helper to run async functions in sync context.
    Creates a new event loop for each task.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="worker.worker.scrape_task")
def scrape_task(self, association_id: int):
    """
    Celery task to scrape a single association.
    
    Args:
        association_id: ID of the association to scrape
        
    Returns:
        Dictionary with scraping results
    """
    from app.services.scraper import scrape_association
    
    # Update task state to started
    self.update_state(state="STARTED", meta={
        "association_id": association_id,
        "status": "scraping"
    })
    
    try:
        # Run the async scraper
        result = run_async(scrape_association(association_id))
        
        return {
            "status": result.get("status", "completed"),
            "association_id": association_id,
            "variables_found": result.get("variables_found", 0),
            "message": result.get("message", "Scraping completed")
        }
    except Exception as e:
        return {
            "status": "error",
            "association_id": association_id,
            "message": str(e)
        }


@celery_app.task(bind=True, name="worker.worker.scrape_all_task")
def scrape_all_task(self):
    """
    Celery task to scrape all associations.
    
    Returns:
        Dictionary with overall scraping results
    """
    from app.services.scraper import scrape_all_associations
    
    self.update_state(state="STARTED", meta={
        "status": "scraping all associations"
    })
    
    try:
        results = run_async(scrape_all_associations())
        
        success_count = sum(1 for r in results if r.get("status") == "success")
        error_count = sum(1 for r in results if r.get("status") == "error")
        
        return {
            "status": "completed",
            "total_associations": len(results),
            "successful": success_count,
            "failed": error_count,
            "results": results
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@celery_app.task(name="worker.worker.health_check")
def health_check():
    """
    Simple health check task.
    
    Returns:
        Dictionary confirming worker is healthy
    """
    return {
        "status": "healthy",
        "worker": "celery"
    }


# Periodic tasks (optional - using Celery Beat)
celery_app.conf.beat_schedule = {
    # Example: Run health check every 5 minutes
    "health-check-every-5-minutes": {
        "task": "worker.worker.health_check",
        "schedule": 300.0,  # 5 minutes
    },
    # Example: Scrape all associations daily at midnight
    # "scrape-all-daily": {
    #     "task": "worker.worker.scrape_all_task",
    #     "schedule": crontab(hour=0, minute=0),
    # },
}


if __name__ == "__main__":
    celery_app.start()
