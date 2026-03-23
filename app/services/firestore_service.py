"""Firestore service for agent and session management."""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from google.cloud.firestore import AsyncClient

from app.config import get_settings
from app.models.agent import Agent
from app.models.session import Session
from app.models.scheduled_job import ScheduledJob

logger = logging.getLogger(__name__)


class FirestoreService:
    """Handles all Firestore operations for agents and sessions."""

    def __init__(self):
        """Initialize Firestore client."""
        settings = get_settings()
        self.client = AsyncClient(project=settings.gcp_project_id)
        self.agents_collection = settings.firestore_agents_collection
        self.sessions_collection = settings.firestore_sessions_collection
        self.scheduled_jobs_collection = settings.firestore_scheduled_jobs_collection
        logger.info(f"Firestore client initialized for project: {settings.gcp_project_id}")

    async def get_agent_by_bot_id(self, bot_id: str) -> Optional[Agent]:
        """
        Retrieve agent configuration by Slack bot ID.

        Args:
            bot_id: Slack bot user ID (B...)

        Returns:
            Agent configuration if found, None otherwise
        """
        try:
            query = (
                self.client.collection(self.agents_collection)
                .where("slack_bot_id", "==", bot_id)
                .limit(1)
            )

            docs = [d async for d in query.stream()]

            if not docs:
                logger.warning(f"No agent found for bot_id: {bot_id}")
                return None

            data = docs[0].to_dict()
            agent = Agent(**data, id=docs[0].id)
            logger.info(f"Found agent: {agent.display_name} (id: {agent.id})")
            return agent

        except Exception as e:
            logger.error(f"Error fetching agent by bot_id {bot_id}: {e}")
            return None

    async def get_session(
        self, slack_user_id: str, agent_id: str
    ) -> Optional[Session]:
        """
        Get existing session for user + agent combination if not expired.

        Sessions expire after `session_timeout_minutes` of inactivity.
        If the session has expired, it will be deleted and None returned.

        Args:
            slack_user_id: Slack user ID (U...)
            agent_id: Agent ID from agents collection

        Returns:
            Session if found and not expired, None otherwise
        """
        try:
            settings = get_settings()
            session_key = f"{slack_user_id}_{agent_id}"
            doc = await self.client.collection(self.sessions_collection).document(session_key).get()

            if not doc.exists:
                logger.info(f"No existing session for {session_key}")
                return None

            data = doc.to_dict()

            # Check if session has expired
            last_activity = data.get("last_activity_at")
            if last_activity:
                # Handle both datetime objects and Firestore timestamps
                if hasattr(last_activity, 'timestamp'):
                    last_activity = datetime.fromtimestamp(last_activity.timestamp())

                expiry_time = last_activity + timedelta(minutes=settings.session_timeout_minutes)
                if datetime.utcnow() > expiry_time:
                    logger.info(
                        f"Session {session_key} expired (last activity: {last_activity}, "
                        f"timeout: {settings.session_timeout_minutes} minutes)"
                    )
                    # Delete the expired session
                    await self.client.collection(self.sessions_collection).document(session_key).delete()
                    return None

            session = Session(**data, id=doc.id)
            logger.info(f"Found existing session: {session.id}")
            return session

        except Exception as e:
            logger.error(f"Error fetching session for {slack_user_id}/{agent_id}: {e}")
            return None

    async def create_session(
        self, slack_user_id: str, agent_id: str, vertex_ai_session_id: str
    ) -> Session:
        """
        Create new session mapping.

        Args:
            slack_user_id: Slack user ID (U...)
            agent_id: Agent ID from agents collection
            vertex_ai_session_id: Vertex AI session ID

        Returns:
            Newly created Session

        Raises:
            Exception: If session creation fails
        """
        try:
            session_key = f"{slack_user_id}_{agent_id}"
            now = datetime.utcnow()

            session_data = {
                "slack_user_id": slack_user_id,
                "agent_id": agent_id,
                "vertex_ai_session_id": vertex_ai_session_id,
                "created_at": now,
                "last_activity_at": now,
            }

            await self.client.collection(self.sessions_collection).document(
                session_key
            ).set(session_data)

            session = Session(**session_data, id=session_key)
            logger.info(f"Created new session: {session.id}")
            return session

        except Exception as e:
            logger.error(f"Error creating session for {slack_user_id}/{agent_id}: {e}")
            raise

    async def update_session_activity(self, session_id: str) -> None:
        """
        Update last activity timestamp for a session.

        Args:
            session_id: Session document ID

        Raises:
            Exception: If update fails
        """
        try:
            await self.client.collection(self.sessions_collection).document(
                session_id
            ).update({"last_activity_at": datetime.utcnow()})

            logger.debug(f"Updated activity timestamp for session: {session_id}")

        except Exception as e:
            logger.error(f"Error updating session activity for {session_id}: {e}")
            raise

    async def get_agent_by_id(self, agent_id: str) -> Optional[Agent]:
        """
        Retrieve agent configuration by document ID.

        Args:
            agent_id: Firestore document ID

        Returns:
            Agent configuration if found, None otherwise
        """
        try:
            doc = await self.client.collection(self.agents_collection).document(agent_id).get()

            if not doc.exists:
                logger.warning(f"No agent found for id: {agent_id}")
                return None

            data = doc.to_dict()
            agent = Agent(**data, id=doc.id)
            logger.info(f"Found agent: {agent.display_name} (id: {agent.id})")
            return agent

        except Exception as e:
            logger.error(f"Error fetching agent by id {agent_id}: {e}")
            return None

    async def get_scheduled_job(self, job_id: str) -> Optional[ScheduledJob]:
        """
        Get scheduled job by document ID.

        Args:
            job_id: Firestore document ID

        Returns:
            ScheduledJob if found, None otherwise
        """
        try:
            doc = await self.client.collection(self.scheduled_jobs_collection).document(job_id).get()

            if not doc.exists:
                logger.warning(f"No scheduled job found for id: {job_id}")
                return None

            data = doc.to_dict()
            # Handle Firestore timestamps
            for field in ["last_execution_at", "execution_started_at", "created_at", "updated_at"]:
                if field in data and data[field] and hasattr(data[field], "timestamp"):
                    data[field] = datetime.fromtimestamp(data[field].timestamp())

            job = ScheduledJob(**data, id=doc.id)
            logger.debug(f"Found scheduled job: {job.name} (id: {job.id})")
            return job

        except Exception as e:
            logger.error(f"Error fetching scheduled job {job_id}: {e}")
            return None

    async def create_scheduled_job(self, job_data: dict) -> ScheduledJob:
        """
        Create a new scheduled job document.

        Args:
            job_data: Dictionary of job fields

        Returns:
            Newly created ScheduledJob

        Raises:
            Exception: If creation fails
        """
        try:
            now = datetime.utcnow()
            job_data["created_at"] = now
            job_data["updated_at"] = now

            doc_ref = self.client.collection(self.scheduled_jobs_collection).document()
            await doc_ref.set(job_data)

            job = ScheduledJob(**job_data, id=doc_ref.id)
            logger.info(f"Created scheduled job: {job.name} (id: {job.id})")
            return job

        except Exception as e:
            logger.error(f"Error creating scheduled job: {e}")
            raise

    async def update_scheduled_job(self, job_id: str, updates: dict) -> Optional[ScheduledJob]:
        """
        Update scheduled job fields.

        Args:
            job_id: Firestore document ID
            updates: Dictionary of fields to update

        Returns:
            Updated ScheduledJob

        Raises:
            Exception: If update fails
        """
        try:
            updates["updated_at"] = datetime.utcnow()

            await self.client.collection(self.scheduled_jobs_collection).document(job_id).update(updates)

            logger.info(f"Updated scheduled job: {job_id}")
            return await self.get_scheduled_job(job_id)

        except Exception as e:
            logger.error(f"Error updating scheduled job {job_id}: {e}")
            raise

    async def delete_scheduled_job(self, job_id: str) -> None:
        """
        Delete scheduled job document.

        Args:
            job_id: Firestore document ID

        Raises:
            Exception: If deletion fails
        """
        try:
            await self.client.collection(self.scheduled_jobs_collection).document(job_id).delete()
            logger.info(f"Deleted scheduled job: {job_id}")

        except Exception as e:
            logger.error(f"Error deleting scheduled job {job_id}: {e}")
            raise

    async def list_scheduled_jobs(
        self,
        agent_id: Optional[str] = None,
        slack_user_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[ScheduledJob]:
        """
        List scheduled jobs with optional filters.

        Args:
            agent_id: Filter by agent ID
            slack_user_id: Filter by Slack user ID
            enabled_only: Only return enabled jobs

        Returns:
            List of ScheduledJob objects
        """
        try:
            query = self.client.collection(self.scheduled_jobs_collection)

            if agent_id:
                query = query.where("agent_id", "==", agent_id)
            if slack_user_id:
                query = query.where("slack_user_id", "==", slack_user_id)
            if enabled_only:
                query = query.where("enabled", "==", True)

            jobs = []
            async for doc in query.stream():
                data = doc.to_dict()
                # Handle Firestore timestamps
                for field in ["last_execution_at", "execution_started_at", "created_at", "updated_at"]:
                    if field in data and data[field] and hasattr(data[field], "timestamp"):
                        data[field] = datetime.fromtimestamp(data[field].timestamp())
                jobs.append(ScheduledJob(**data, id=doc.id))

            logger.info(f"Listed {len(jobs)} scheduled jobs")
            return jobs

        except Exception as e:
            logger.error(f"Error listing scheduled jobs: {e}")
            return []

    async def acquire_job_execution_lock(
        self,
        job_id: str,
        execution_id: str,
        lock_timeout_seconds: int = 300,
    ) -> bool:
        """
        Acquire execution lock for a scheduled job.

        Uses simple read-then-write pattern. Not perfectly atomic but sufficient
        for preventing most duplicate executions.

        Args:
            job_id: Firestore document ID
            execution_id: Unique execution ID for this attempt
            lock_timeout_seconds: Lock expiry time in seconds

        Returns:
            True if lock acquired, False if job is already being executed
        """
        try:
            doc_ref = self.client.collection(self.scheduled_jobs_collection).document(job_id)
            doc = await doc_ref.get()

            if not doc.exists:
                return False

            data = doc.to_dict()

            # Check if job is enabled
            if not data.get("enabled", True):
                logger.info(f"Job {job_id} is disabled, skipping")
                return False

            # Check if already being executed (lock is held)
            execution_started_at = data.get("execution_started_at")
            if execution_started_at:
                # Handle Firestore timestamp
                if hasattr(execution_started_at, "timestamp"):
                    execution_started_at = datetime.fromtimestamp(execution_started_at.timestamp())

                lock_expiry = execution_started_at + timedelta(seconds=lock_timeout_seconds)
                if datetime.utcnow() < lock_expiry:
                    logger.info(f"Job {job_id} is already being executed, skipping")
                    return False
                else:
                    logger.warning(f"Job {job_id} lock expired, allowing new execution")

            # Check for duplicate execution ID
            if data.get("last_execution_id") == execution_id:
                logger.info(f"Job {job_id} already executed with id {execution_id}, skipping")
                return False

            # Acquire lock
            await doc_ref.update({
                "execution_started_at": datetime.utcnow(),
                "last_execution_id": execution_id,
            })

            logger.info(f"Acquired execution lock for job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Error acquiring lock for job {job_id}: {e}")
            return False

    async def release_job_execution_lock(
        self,
        job_id: str,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """
        Release execution lock and update job status.

        Args:
            job_id: Firestore document ID
            success: Whether execution succeeded
            error: Error message if failed
        """
        try:
            updates = {
                "execution_started_at": None,
                "last_execution_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            if success:
                updates["consecutive_failures"] = 0
                updates["last_error"] = None
            else:
                updates["last_error"] = error
                # Increment failures using a transaction
                doc_ref = self.client.collection(self.scheduled_jobs_collection).document(job_id)
                doc = await doc_ref.get()
                if doc.exists:
                    current_failures = doc.to_dict().get("consecutive_failures", 0)
                    updates["consecutive_failures"] = current_failures + 1

            await self.client.collection(self.scheduled_jobs_collection).document(job_id).update(updates)
            logger.info(f"Released execution lock for job {job_id} (success={success})")

        except Exception as e:
            logger.error(f"Error releasing lock for job {job_id}: {e}")
