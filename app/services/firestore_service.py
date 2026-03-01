"""Firestore service for agent and session management."""
import logging
from datetime import datetime, timedelta
from typing import Optional

from google.cloud.firestore import AsyncClient

from app.config import get_settings
from app.models.agent import Agent
from app.models.session import Session

logger = logging.getLogger(__name__)


class FirestoreService:
    """Handles all Firestore operations for agents and sessions."""

    def __init__(self):
        """Initialize Firestore client."""
        settings = get_settings()
        self.client = AsyncClient(project=settings.gcp_project_id)
        self.agents_collection = settings.firestore_agents_collection
        self.sessions_collection = settings.firestore_sessions_collection
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
