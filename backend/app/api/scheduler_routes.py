"""
Scheduler API Routes

Provides endpoints for monitoring and managing scheduled jobs.
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..agents.scheduler import (
    start_scheduler,
    stop_scheduler,
    get_scheduler_jobs,
    run_job_now,
    weekly_organization_update,
    daily_health_check,
    search_new_organizations,
)

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


class JobInfo(BaseModel):
    """Job information model."""
    id: str
    name: str
    next_run: Optional[str]
    trigger: str


class JobRunResult(BaseModel):
    """Result of a job run."""
    job: str
    timestamp: str
    success: bool
    result: dict


class SchedulerStatus(BaseModel):
    """Scheduler status model."""
    running: bool
    jobs: List[JobInfo]


@router.get("/status", response_model=SchedulerStatus)
async def get_scheduler_status() -> SchedulerStatus:
    """
    Get the current scheduler status and list of jobs.
    """
    jobs = get_scheduler_jobs()
    return SchedulerStatus(
        running=len(jobs) > 0,
        jobs=[JobInfo(**job) for job in jobs]
    )


@router.post("/start")
async def start_scheduler_endpoint() -> dict:
    """
    Start the scheduler if not already running.
    """
    try:
        start_scheduler()
        return {
            "message": "Scheduler started",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_scheduler_endpoint() -> dict:
    """
    Stop the scheduler.
    """
    try:
        stop_scheduler()
        return {
            "message": "Scheduler stopped",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run/{job_id}")
async def run_job_endpoint(job_id: str, background_tasks: BackgroundTasks) -> dict:
    """
    Manually trigger a scheduled job.
    
    Available jobs:
    - weekly_organization_update
    - daily_health_check
    - monthly_new_organizations
    """
    try:
        # Run in background for long-running jobs
        if job_id == "weekly_organization_update":
            background_tasks.add_task(weekly_organization_update)
            return {
                "message": f"Job {job_id} started in background",
                "timestamp": datetime.utcnow().isoformat()
            }
        elif job_id == "daily_health_check":
            result = await daily_health_check()
            return {
                "message": f"Job {job_id} completed",
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        elif job_id == "monthly_new_organizations":
            background_tasks.add_task(search_new_organizations)
            return {
                "message": f"Job {job_id} started in background",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-update")
async def run_weekly_update(background_tasks: BackgroundTasks) -> dict:
    """
    Manually trigger the weekly organization update.
    This runs in the background.
    """
    background_tasks.add_task(weekly_organization_update)
    return {
        "message": "Weekly update started",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/run-health-check")
async def run_health_check() -> dict:
    """
    Run the daily health check immediately.
    """
    result = await daily_health_check()
    return result


@router.post("/search-new")
async def search_new(
    department: Optional[str] = None,
    background_tasks: BackgroundTasks = None
) -> dict:
    """
    Search for new organizations.
    
    Args:
        department: Optional department to focus the search
    """
    if background_tasks:
        background_tasks.add_task(search_new_organizations, department)
        return {
            "message": f"Search started for {department or 'all departments'}",
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        result = await search_new_organizations(department)
        return result
