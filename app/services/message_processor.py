"""Background message processing service."""
import logging
from typing import Dict, Any

from app.schemas.slack import SlackEvent
from app.services.firestore_service import FirestoreService
from app.services.vertex_ai_service import VertexAIService
from app.services.slack_service import SlackService

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Handles background processing of Slack messages."""

    def __init__(
        self,
        firestore: FirestoreService,
        vertex_ai: VertexAIService,
        slack: SlackService,
    ):
        """
        Initialize message processor.

        Args:
            firestore: Firestore service instance
            vertex_ai: Vertex AI service instance
            slack: Slack service instance
        """
        self.firestore = firestore
        self.vertex_ai = vertex_ai
        self.slack = slack

    async def process_slack_event(self, event: SlackEvent) -> None:
        """
        Process a Slack event in the background.

        Flow:
        1. Extract user message and identify agent
        2. Get/create Vertex AI session
        3. Send message to Vertex AI
        4. Post response back to Slack

        Args:
            event: Slack event from Events API

        Note:
            This function catches all exceptions to prevent background task failures
            from crashing the application.
        """
        try:
            # Extract event details
            event_data: Dict[str, Any] = event.event
            slack_user_id = event_data.get("user")
            channel_id = event_data.get("channel")
            message_text = event_data.get("text", "")

            if not all([slack_user_id, channel_id, message_text]):
                logger.warning(f"Incomplete event data: {event_data}")
                return

            # Log the channel type for debugging DM threading issues
            channel_type = event_data.get("channel_type", "unknown")
            logger.info(
                f"Processing message from user {slack_user_id} in channel {channel_id} "
                f"(type: {channel_type})"
            )

            # Step 1: Identify which agent this message is for
            # The bot_id in the event tells us which bot received the message
            # However, for DMs, we need to look at the channel type
            # For now, we'll need to identify the agent from the authorized user
            # or from the bot_id if it's in the event

            # Get the bot ID from authorizations (Slack provides this)
            bot_id = None
            if event.authorizations and len(event.authorizations) > 0:
                bot_id = event.authorizations[0].get("user_id")

            if not bot_id:
                # Fallback: check if bot_id is in the event itself
                bot_id = event_data.get("bot_id")

            if not bot_id:
                logger.error(f"No bot_id found in event: {event.model_dump()}")
                return

            agent = await self.firestore.get_agent_by_bot_id(bot_id)
            if not agent:
                logger.error(f"No agent found for bot_id: {bot_id}")
                # Optionally: send error message to user
                return

            logger.info(f"Processing message for agent: {agent.display_name}")

            # Step 2: Get or create Vertex AI session
            session_id = await self._get_or_create_session(
                slack_user_id=slack_user_id,
                agent_id=agent.id,
                vertex_ai_agent_id=agent.vertex_ai_agent_id,
            )

            # Step 3: Send message to Vertex AI Agent Engine
            response = await self.vertex_ai.send_message(
                agent_id=agent.vertex_ai_agent_id,
                session_id=session_id,
                message=message_text,
            )

            # Step 4: Post response to Slack
            # Use conversations.open to ensure we're posting to the canonical DM channel
            # This can help with message threading/history issues
            dm_channel = await self.slack.open_conversation(
                token=agent.slack_bot_token, user_id=slack_user_id
            )

            if dm_channel != channel_id:
                logger.warning(
                    f"Channel ID mismatch: event had {channel_id}, "
                    f"conversations.open returned {dm_channel}"
                )

            await self.slack.post_message(
                token=agent.slack_bot_token, channel=dm_channel, text=response.text
            )

            logger.info(f"Successfully processed message for user {slack_user_id}")

        except Exception as e:
            logger.exception(f"Unexpected error processing Slack event: {e}")
            # In production, consider sending a generic error message to the user
            # For MVP, we'll just log it

    async def _get_or_create_session(
        self, slack_user_id: str, agent_id: str, vertex_ai_agent_id: str
    ) -> str:
        """
        Get existing session or create new one.

        Args:
            slack_user_id: Slack user ID (U...)
            agent_id: Agent ID from agents collection
            vertex_ai_agent_id: Vertex AI agent resource name

        Returns:
            Vertex AI session ID

        Raises:
            Exception: If session operations fail
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
        vertex_session_id = await self.vertex_ai.create_session(
            vertex_ai_agent_id
        )

        # Store in Firestore
        await self.firestore.create_session(
            slack_user_id=slack_user_id,
            agent_id=agent_id,
            vertex_ai_session_id=vertex_session_id,
        )

        logger.info(f"Created new session: {vertex_session_id}")
        return vertex_session_id
