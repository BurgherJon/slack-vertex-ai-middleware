"""Scheduled Jobs API endpoints."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import get_settings
from app.schemas.scheduled_job import (
    ExecuteJobRequest,
    ExecuteJobResponse,
    ScheduledJobCreate,
    ScheduledJobListResponse,
    ScheduledJobResponse,
    ScheduledJobUpdate,
)
from app.services.scheduled_job_service import ScheduledJobService
from app.services.scheduled_job_executor import ScheduledJobExecutor
from app.core.dependencies import get_scheduled_job_service, get_scheduled_job_executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduled-jobs", tags=["scheduled-jobs"])


async def verify_cloud_scheduler_token(request: Request) -> bool:
    """
    Verify the request comes from Cloud Scheduler with valid OIDC token.

    Args:
        request: FastAPI request object

    Returns:
        True if token is valid, False otherwise
    """
    settings = get_settings()

    # Skip verification if Cloud Scheduler is not configured
    if not settings.cloud_scheduler_service_account or not settings.cloud_run_url:
        logger.warning("Cloud Scheduler not configured, skipping OIDC verification")
        return True

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("No Bearer token in Authorization header")
        return False

    token = auth_header.split(" ")[1]
    try:
        # Verify the OIDC token
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=settings.cloud_run_url,
        )
        # Verify it's from the expected service account
        expected_email = settings.cloud_scheduler_service_account
        actual_email = claims.get("email", "")
        if actual_email != expected_email:
            logger.warning(
                f"OIDC token email mismatch: expected {expected_email}, got {actual_email}"
            )
            return False
        return True
    except Exception as e:
        logger.warning(f"OIDC token verification failed: {e}")
        return False


@router.post("", response_model=ScheduledJobResponse, status_code=201)
async def create_scheduled_job(
    job_data: ScheduledJobCreate,
    service: ScheduledJobService = Depends(get_scheduled_job_service),
):
    """
    Create a new scheduled job.

    Creates a job in Firestore and a corresponding Cloud Scheduler job
    that will trigger execution on the specified schedule.
    """
    try:
        job = await service.create_job(job_data)
        return ScheduledJobResponse(
            id=job.id,
            name=job.name,
            prompt=job.prompt,
            agent_id=job.agent_id,
            slack_user_id=job.slack_user_id,
            schedule=job.schedule,
            timezone=job.timezone,
            enabled=job.enabled,
            last_execution_at=job.last_execution_at,
            last_error=job.last_error,
            consecutive_failures=job.consecutive_failures,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error creating scheduled job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create scheduled job")


@router.get("", response_model=ScheduledJobListResponse)
async def list_scheduled_jobs(
    agent_id: Optional[str] = None,
    slack_user_id: Optional[str] = None,
    service: ScheduledJobService = Depends(get_scheduled_job_service),
):
    """
    List scheduled jobs with optional filtering.

    Args:
        agent_id: Filter by agent ID
        slack_user_id: Filter by Slack user ID
    """
    jobs = await service.list_jobs(agent_id=agent_id, slack_user_id=slack_user_id)
    return ScheduledJobListResponse(
        jobs=[
            ScheduledJobResponse(
                id=job.id,
                name=job.name,
                prompt=job.prompt,
                agent_id=job.agent_id,
                slack_user_id=job.slack_user_id,
                schedule=job.schedule,
                timezone=job.timezone,
                enabled=job.enabled,
                last_execution_at=job.last_execution_at,
                last_error=job.last_error,
                consecutive_failures=job.consecutive_failures,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
            for job in jobs
        ],
        total=len(jobs),
    )


@router.get("/{job_id}", response_model=ScheduledJobResponse)
async def get_scheduled_job(
    job_id: str,
    service: ScheduledJobService = Depends(get_scheduled_job_service),
):
    """Get a specific scheduled job by ID."""
    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scheduled job not found")

    return ScheduledJobResponse(
        id=job.id,
        name=job.name,
        prompt=job.prompt,
        agent_id=job.agent_id,
        slack_user_id=job.slack_user_id,
        schedule=job.schedule,
        timezone=job.timezone,
        enabled=job.enabled,
        last_execution_at=job.last_execution_at,
        last_error=job.last_error,
        consecutive_failures=job.consecutive_failures,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.patch("/{job_id}", response_model=ScheduledJobResponse)
async def update_scheduled_job(
    job_id: str,
    updates: ScheduledJobUpdate,
    service: ScheduledJobService = Depends(get_scheduled_job_service),
):
    """
    Update a scheduled job.

    Only include fields you want to change. Updates are synced
    to Cloud Scheduler automatically.
    """
    try:
        job = await service.update_job(job_id, updates)
        if not job:
            raise HTTPException(status_code=404, detail="Scheduled job not found")

        return ScheduledJobResponse(
            id=job.id,
            name=job.name,
            prompt=job.prompt,
            agent_id=job.agent_id,
            slack_user_id=job.slack_user_id,
            schedule=job.schedule,
            timezone=job.timezone,
            enabled=job.enabled,
            last_execution_at=job.last_execution_at,
            last_error=job.last_error,
            consecutive_failures=job.consecutive_failures,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error updating scheduled job: {e}")
        raise HTTPException(status_code=500, detail="Failed to update scheduled job")


@router.delete("/{job_id}", status_code=204)
async def delete_scheduled_job(
    job_id: str,
    service: ScheduledJobService = Depends(get_scheduled_job_service),
):
    """
    Delete a scheduled job.

    Removes the job from Firestore and deletes the corresponding
    Cloud Scheduler job.
    """
    success = await service.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scheduled job not found")


@router.post("/{job_id}/execute", response_model=ExecuteJobResponse)
async def execute_scheduled_job(
    job_id: str,
    body: ExecuteJobRequest,
    request: Request,
    executor: ScheduledJobExecutor = Depends(get_scheduled_job_executor),
):
    """
    Execute a scheduled job.

    This endpoint is called by Cloud Scheduler and is protected
    by OIDC token verification.
    """
    # Verify Cloud Scheduler token
    if not await verify_cloud_scheduler_token(request):
        raise HTTPException(status_code=401, detail="Invalid authorization")

    success = await executor.execute_job(job_id, body.execution_id)
    return ExecuteJobResponse(
        success=success,
        job_id=job_id,
        message="Execution completed" if success else "Execution skipped or failed",
    )


@router.post("/{job_id}/test")
async def test_scheduled_job(
    job_id: str,
    executor: ScheduledJobExecutor = Depends(get_scheduled_job_executor),
):
    """
    Test run a scheduled job.

    Executes the job immediately without affecting execution tracking.
    The response is sent to the configured Slack user with a [TEST] prefix.
    """
    result = await executor.test_execute_job(job_id)
    if not result["success"]:
        raise HTTPException(
            status_code=400 if "not found" in result.get("error", "").lower() else 500,
            detail=result.get("error", "Test execution failed"),
        )
    return result
