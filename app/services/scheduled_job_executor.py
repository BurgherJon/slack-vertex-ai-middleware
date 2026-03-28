"""Scheduled job execution service."""
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.config import get_settings
from app.core.exceptions import ResourceExhaustedError
from app.services.firestore_service import FirestoreService
from app.services.vertex_ai_service import VertexAIService
from app.services.slack_service import SlackService

logger = logging.getLogger(__name__)


class ScheduledJobExecutor:
    """Executes scheduled jobs with duplicate prevention and error handling."""

    def __init__(
        self,
        firestore: FirestoreService,
        vertex_ai: VertexAIService,
        slack: SlackService,
    ):
        """
        Initialize the job executor.

        Args:
            firestore: Firestore service for data access
            vertex_ai: Vertex AI service for agent calls
            slack: Slack service for posting messages
        """
        self.firestore = firestore
        self.vertex_ai = vertex_ai
        self.slack = slack
        self.settings = get_settings()

    async def execute_job(self, job_id: str, execution_id: str) -> bool:
        """
        Execute a scheduled job.

        Flow:
        1. Acquire execution lock (Firestore transaction)
        2. Verify job is enabled
        3. Get agent configuration
        4. Get or create Vertex AI session (stored in Firestore for continuity)
        5. Send prompt to agent
        6. Send response to Slack user
        7. Update execution tracking

        Args:
            job_id: Firestore document ID of the job
            execution_id: Unique execution ID for idempotency

        Returns:
            True if execution succeeded, False if skipped or failed
        """
        job = None
        try:
            # Step 1: Acquire execution lock
            lock_acquired = await self.firestore.acquire_job_execution_lock(
                job_id=job_id,
                execution_id=execution_id,
                lock_timeout_seconds=self.settings.scheduled_job_lock_timeout_seconds,
            )

            if not lock_acquired:
                logger.info(f"Could not acquire lock for job {job_id}, skipping")
                return False

            # Step 2: Get and validate job
            job = await self.firestore.get_scheduled_job(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found")
                return False

            if not job.enabled:
                logger.info(f"Job {job_id} is disabled, skipping")
                await self.firestore.release_job_execution_lock(job_id, success=True)
                return False

            logger.info(f"Executing scheduled job: {job.name} (id: {job_id})")

            # Step 3: Get agent configuration
            agent = await self.firestore.get_agent_by_id(job.agent_id)
            if not agent:
                error_msg = f"Agent {job.agent_id} not found"
                logger.error(error_msg)
                await self.firestore.release_job_execution_lock(
                    job_id, success=False, error=error_msg
                )
                return False

            # Step 4: Get existing session or create new one
            # This ensures the user can continue the conversation when replying
            session_id = await self._get_or_create_session(
                slack_user_id=job.slack_user_id,
                agent_id=job.agent_id,
                vertex_ai_agent_id=agent.vertex_ai_agent_id,
            )
            logger.info(f"Using Vertex AI session: {session_id}")

            # Resolve Slack user's display name and prefix the prompt
            user_info = await self.slack.get_user_info(
                token=agent.slack_bot_token, user_id=job.slack_user_id
            )
            if user_info:
                user_display_name = (
                    user_info.get("profile", {}).get("display_name")
                    or user_info.get("real_name")
                    or job.slack_user_id
                )
            else:
                user_display_name = job.slack_user_id

            # Prefix the prompt with user identity (same format as regular messages)
            prefixed_prompt = (
                f"[From: {user_display_name} | SlackID: {job.slack_user_id}] {job.prompt}"
            )

            # Step 5: Send prompt to Vertex AI agent
            response = await self.vertex_ai.send_message(
                agent_id=agent.vertex_ai_agent_id,
                session_id=session_id,
                message=prefixed_prompt,
            )

            # Step 6: Only send to Slack if agent provided an actual response
            if response.text and response.text.strip():
                # Use conversations.open to get the canonical DM channel
                dm_channel = await self.slack.open_conversation(
                    token=agent.slack_bot_token, user_id=job.slack_user_id
                )

                # Format message with job name for context
                formatted_message = f"*Scheduled: {job.name}*\n\n{response.text}"

                await self.slack.post_message(
                    token=agent.slack_bot_token,
                    channel=dm_channel,
                    text=formatted_message,
                )
                logger.info(f"Sent response to Slack for job {job_id}")
            else:
                logger.info(f"No response from agent for job {job_id}, skipping Slack message")

            # Step 7: Mark success and release lock
            await self.firestore.release_job_execution_lock(job_id, success=True)

            # Clear any pending retry (if this was a retry execution)
            if job.retry_at:
                await self.firestore.update_scheduled_job(job_id, {
                    "retry_at": None,
                    "retry_reason": None,
                })
                logger.info(f"Cleared retry for job {job_id} after successful execution")

            logger.info(f"Successfully executed job {job_id}")
            return True

        except ResourceExhaustedError as e:
            # Google API rate limit - schedule a silent retry in 1 minute
            logger.warning(f"Rate limit hit for job {job_id}: {e}")

            retry_at = datetime.utcnow() + timedelta(minutes=1)
            await self.firestore.update_scheduled_job(job_id, {
                "retry_at": retry_at,
                "retry_reason": "rate_limit_429",
            })
            logger.info(f"Scheduled retry for job {job_id} at {retry_at}")

            # Release lock (not a failure, just rate limited)
            await self.firestore.release_job_execution_lock(job_id, success=True)
            return False

        except Exception as e:
            error_msg = str(e)
            logger.exception(f"Error executing job {job_id}: {e}")

            # Release lock with error
            if job:
                await self.firestore.release_job_execution_lock(
                    job_id, success=False, error=error_msg
                )

            return False

    async def test_execute_job(self, job_id: str) -> dict:
        """
        Test run a job without affecting execution tracking.

        Useful for validating job configuration before enabling scheduling.

        Args:
            job_id: Firestore document ID of the job

        Returns:
            Dict with success status and response or error
        """
        try:
            # Get job
            job = await self.firestore.get_scheduled_job(job_id)
            if not job:
                return {"success": False, "error": "Job not found"}

            # Get agent
            agent = await self.firestore.get_agent_by_id(job.agent_id)
            if not agent:
                return {"success": False, "error": f"Agent {job.agent_id} not found"}

            # Create session
            session_id = await self.vertex_ai.create_session(agent.vertex_ai_agent_id)

            # Resolve user identity
            user_info = await self.slack.get_user_info(
                token=agent.slack_bot_token, user_id=job.slack_user_id
            )
            user_display_name = job.slack_user_id
            if user_info:
                user_display_name = (
                    user_info.get("profile", {}).get("display_name")
                    or user_info.get("real_name")
                    or job.slack_user_id
                )

            # Send to agent
            prefixed_prompt = (
                f"[From: {user_display_name} | SlackID: {job.slack_user_id}] {job.prompt}"
            )
            response = await self.vertex_ai.send_message(
                agent_id=agent.vertex_ai_agent_id,
                session_id=session_id,
                message=prefixed_prompt,
            )

            # Send to Slack
            dm_channel = await self.slack.open_conversation(
                token=agent.slack_bot_token, user_id=job.slack_user_id
            )
            formatted_message = f"*[TEST] Scheduled: {job.name}*\n\n{response.text}"
            await self.slack.post_message(
                token=agent.slack_bot_token,
                channel=dm_channel,
                text=formatted_message,
            )

            return {
                "success": True,
                "response": response.text,
                "message": "Test execution completed, response sent to Slack",
            }

        except Exception as e:
            logger.exception(f"Error in test execution for job {job_id}: {e}")
            return {"success": False, "error": str(e)}

    async def _get_or_create_session(
        self, slack_user_id: str, agent_id: str, vertex_ai_agent_id: str
    ) -> str:
        """
        Get existing session or create new one.

        This ensures that when a scheduled job sends a message to a user,
        any replies from the user will continue in the same conversation.

        Args:
            slack_user_id: Slack user ID (U...)
            agent_id: Agent ID from agents collection
            vertex_ai_agent_id: Vertex AI agent resource name

        Returns:
            Vertex AI session ID
        """
        # Try to get existing session
        session = await self.firestore.get_session(
            slack_user_id=slack_user_id, agent_id=agent_id
        )

        if session:
            # Update last activity timestamp
            await self.firestore.update_session_activity(session.id)
            logger.info(f"Using existing session: {session.id}")
            return session.vertex_ai_session_id

        # No existing session, create new one in Vertex AI
        vertex_session_id = await self.vertex_ai.create_session(vertex_ai_agent_id)

        # Store in Firestore so user replies continue the conversation
        await self.firestore.create_session(
            slack_user_id=slack_user_id,
            agent_id=agent_id,
            vertex_ai_session_id=vertex_session_id,
        )

        logger.info(f"Created new session: {vertex_session_id}")
        return vertex_session_id
