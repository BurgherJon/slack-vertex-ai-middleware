"""Service for managing scheduled jobs and Cloud Scheduler integration."""
import logging
from typing import List, Optional

from croniter import croniter
from google.cloud import scheduler_v1
from google.protobuf import duration_pb2

from app.config import get_settings
from app.models.scheduled_job import ScheduledJob
from app.schemas.scheduled_job import ScheduledJobCreate, ScheduledJobUpdate
from app.services.firestore_service import FirestoreService

logger = logging.getLogger(__name__)


class ScheduledJobService:
    """Manages scheduled job lifecycle and Cloud Scheduler integration."""

    def __init__(self, firestore: FirestoreService):
        """
        Initialize the scheduled job service.

        Args:
            firestore: FirestoreService instance for data access
        """
        self.firestore = firestore
        self.settings = get_settings()

        # Initialize Cloud Scheduler client if configured
        if self.settings.cloud_scheduler_service_account:
            self.scheduler_client = scheduler_v1.CloudSchedulerAsyncClient()
        else:
            self.scheduler_client = None
            logger.warning(
                "Cloud Scheduler service account not configured. "
                "Jobs will be stored but not scheduled."
            )

    def _validate_cron_expression(self, cron: str) -> bool:
        """
        Validate a cron expression.

        Args:
            cron: Cron expression string

        Returns:
            True if valid, False otherwise
        """
        try:
            croniter(cron)
            return True
        except (ValueError, KeyError):
            return False

    def _get_scheduler_job_name(self, job_id: str) -> str:
        """
        Generate Cloud Scheduler job resource name.

        Args:
            job_id: Firestore document ID

        Returns:
            Full resource name for Cloud Scheduler job
        """
        return (
            f"projects/{self.settings.gcp_project_id}/"
            f"locations/{self.settings.cloud_scheduler_location}/"
            f"jobs/scheduled-job-{job_id}"
        )

    def _get_scheduler_parent(self) -> str:
        """Get the Cloud Scheduler parent resource name."""
        return (
            f"projects/{self.settings.gcp_project_id}/"
            f"locations/{self.settings.cloud_scheduler_location}"
        )

    async def _create_cloud_scheduler_job(self, job: ScheduledJob) -> Optional[str]:
        """
        Create a Cloud Scheduler job for the scheduled job.

        Args:
            job: ScheduledJob to create scheduler for

        Returns:
            Cloud Scheduler job name if created, None otherwise
        """
        if not self.scheduler_client or not self.settings.cloud_run_url:
            logger.warning("Cloud Scheduler not fully configured, skipping job creation")
            return None

        try:
            scheduler_job_name = self._get_scheduler_job_name(job.id)

            # Build the HTTP target
            http_target = scheduler_v1.HttpTarget(
                uri=f"{self.settings.cloud_run_url}/api/v1/scheduled-jobs/{job.id}/execute",
                http_method=scheduler_v1.HttpMethod.POST,
                headers={"Content-Type": "application/json"},
                body=b'{"execution_id": "' + b'${scheduler.uuid}' + b'"}',
                oidc_token=scheduler_v1.OidcToken(
                    service_account_email=self.settings.cloud_scheduler_service_account,
                    audience=self.settings.cloud_run_url,
                ),
            )

            # Build the scheduler job
            scheduler_job = scheduler_v1.Job(
                name=scheduler_job_name,
                schedule=job.schedule,
                time_zone=job.timezone,
                http_target=http_target,
                retry_config=scheduler_v1.RetryConfig(
                    retry_count=0,  # We handle retries via consecutive_failures tracking
                ),
            )

            # Create the job
            request = scheduler_v1.CreateJobRequest(
                parent=self._get_scheduler_parent(),
                job=scheduler_job,
            )
            created_job = await self.scheduler_client.create_job(request=request)
            logger.info(f"Created Cloud Scheduler job: {created_job.name}")
            return created_job.name

        except Exception as e:
            logger.error(f"Error creating Cloud Scheduler job: {e}")
            return None

    async def _update_cloud_scheduler_job(self, job: ScheduledJob) -> bool:
        """
        Update the Cloud Scheduler job for a scheduled job.

        Args:
            job: ScheduledJob with updated settings

        Returns:
            True if updated successfully
        """
        if not self.scheduler_client or not job.cloud_scheduler_job_name:
            return False

        try:
            # Build updated HTTP target
            http_target = scheduler_v1.HttpTarget(
                uri=f"{self.settings.cloud_run_url}/api/v1/scheduled-jobs/{job.id}/execute",
                http_method=scheduler_v1.HttpMethod.POST,
                headers={"Content-Type": "application/json"},
                body=b'{"execution_id": "' + b'${scheduler.uuid}' + b'"}',
                oidc_token=scheduler_v1.OidcToken(
                    service_account_email=self.settings.cloud_scheduler_service_account,
                    audience=self.settings.cloud_run_url,
                ),
            )

            # Build updated scheduler job
            scheduler_job = scheduler_v1.Job(
                name=job.cloud_scheduler_job_name,
                schedule=job.schedule,
                time_zone=job.timezone,
                http_target=http_target,
                state=scheduler_v1.Job.State.ENABLED if job.enabled else scheduler_v1.Job.State.PAUSED,
            )

            request = scheduler_v1.UpdateJobRequest(job=scheduler_job)
            await self.scheduler_client.update_job(request=request)
            logger.info(f"Updated Cloud Scheduler job: {job.cloud_scheduler_job_name}")
            return True

        except Exception as e:
            logger.error(f"Error updating Cloud Scheduler job: {e}")
            return False

    async def _delete_cloud_scheduler_job(self, scheduler_job_name: str) -> bool:
        """
        Delete a Cloud Scheduler job.

        Args:
            scheduler_job_name: Full resource name of the scheduler job

        Returns:
            True if deleted successfully
        """
        if not self.scheduler_client:
            return False

        try:
            request = scheduler_v1.DeleteJobRequest(name=scheduler_job_name)
            await self.scheduler_client.delete_job(request=request)
            logger.info(f"Deleted Cloud Scheduler job: {scheduler_job_name}")
            return True

        except Exception as e:
            logger.error(f"Error deleting Cloud Scheduler job: {e}")
            return False

    async def _pause_cloud_scheduler_job(self, scheduler_job_name: str) -> bool:
        """
        Pause a Cloud Scheduler job.

        Args:
            scheduler_job_name: Full resource name of the scheduler job

        Returns:
            True if paused successfully
        """
        if not self.scheduler_client:
            return False

        try:
            request = scheduler_v1.PauseJobRequest(name=scheduler_job_name)
            await self.scheduler_client.pause_job(request=request)
            logger.info(f"Paused Cloud Scheduler job: {scheduler_job_name}")
            return True

        except Exception as e:
            logger.error(f"Error pausing Cloud Scheduler job: {e}")
            return False

    async def _resume_cloud_scheduler_job(self, scheduler_job_name: str) -> bool:
        """
        Resume a paused Cloud Scheduler job.

        Args:
            scheduler_job_name: Full resource name of the scheduler job

        Returns:
            True if resumed successfully
        """
        if not self.scheduler_client:
            return False

        try:
            request = scheduler_v1.ResumeJobRequest(name=scheduler_job_name)
            await self.scheduler_client.resume_job(request=request)
            logger.info(f"Resumed Cloud Scheduler job: {scheduler_job_name}")
            return True

        except Exception as e:
            logger.error(f"Error resuming Cloud Scheduler job: {e}")
            return False

    async def create_job(self, job_data: ScheduledJobCreate) -> ScheduledJob:
        """
        Create a new scheduled job and corresponding Cloud Scheduler job.

        Args:
            job_data: Job creation data

        Returns:
            Created ScheduledJob

        Raises:
            ValueError: If validation fails
        """
        # Validate cron expression
        if not self._validate_cron_expression(job_data.schedule):
            raise ValueError(f"Invalid cron expression: {job_data.schedule}")

        # Validate agent exists
        agent = await self.firestore.get_agent_by_id(job_data.agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {job_data.agent_id}")

        # Create Firestore document
        job = await self.firestore.create_scheduled_job(job_data.model_dump())

        # Create Cloud Scheduler job
        scheduler_job_name = await self._create_cloud_scheduler_job(job)
        if scheduler_job_name:
            await self.firestore.update_scheduled_job(
                job.id, {"cloud_scheduler_job_name": scheduler_job_name}
            )
            job = await self.firestore.get_scheduled_job(job.id)

        return job

    async def update_job(self, job_id: str, updates: ScheduledJobUpdate) -> Optional[ScheduledJob]:
        """
        Update job configuration and sync with Cloud Scheduler.

        Args:
            job_id: Firestore document ID
            updates: Fields to update

        Returns:
            Updated ScheduledJob or None if not found

        Raises:
            ValueError: If validation fails
        """
        # Get existing job
        job = await self.firestore.get_scheduled_job(job_id)
        if not job:
            return None

        # Validate cron if being updated
        update_dict = updates.model_dump(exclude_unset=True)
        if "schedule" in update_dict and not self._validate_cron_expression(update_dict["schedule"]):
            raise ValueError(f"Invalid cron expression: {update_dict['schedule']}")

        # Update Firestore
        updated_job = await self.firestore.update_scheduled_job(job_id, update_dict)

        # Sync with Cloud Scheduler
        if updated_job and updated_job.cloud_scheduler_job_name:
            # Check if enabled status changed
            if "enabled" in update_dict:
                if update_dict["enabled"]:
                    await self._resume_cloud_scheduler_job(updated_job.cloud_scheduler_job_name)
                else:
                    await self._pause_cloud_scheduler_job(updated_job.cloud_scheduler_job_name)
            # Check if schedule or timezone changed
            elif "schedule" in update_dict or "timezone" in update_dict:
                await self._update_cloud_scheduler_job(updated_job)

        return updated_job

    async def delete_job(self, job_id: str) -> bool:
        """
        Delete job from Firestore and Cloud Scheduler.

        Args:
            job_id: Firestore document ID

        Returns:
            True if deleted
        """
        job = await self.firestore.get_scheduled_job(job_id)
        if not job:
            return False

        # Delete Cloud Scheduler job first
        if job.cloud_scheduler_job_name:
            await self._delete_cloud_scheduler_job(job.cloud_scheduler_job_name)

        # Delete Firestore document
        await self.firestore.delete_scheduled_job(job_id)
        return True

    async def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """
        Get a single job by ID.

        Args:
            job_id: Firestore document ID

        Returns:
            ScheduledJob if found
        """
        return await self.firestore.get_scheduled_job(job_id)

    async def list_jobs(
        self,
        agent_id: Optional[str] = None,
        slack_user_id: Optional[str] = None,
    ) -> List[ScheduledJob]:
        """
        List jobs with optional filtering.

        Args:
            agent_id: Filter by agent ID
            slack_user_id: Filter by Slack user ID

        Returns:
            List of ScheduledJob objects
        """
        return await self.firestore.list_scheduled_jobs(
            agent_id=agent_id,
            slack_user_id=slack_user_id,
        )
