"""Background message processing service."""
import base64
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

from app.schemas.slack import SlackEvent
from app.services.firestore_service import FirestoreService
from app.services.vertex_ai_service import VertexAIService
from app.services.slack_service import SlackService
from app.core.exceptions import ResourceExhaustedError

if TYPE_CHECKING:
    from app.services.gcs_service import GCSService

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Handles background processing of Slack messages."""

    def __init__(
        self,
        firestore: FirestoreService,
        vertex_ai: VertexAIService,
        slack: SlackService,
        gcs: Optional["GCSService"] = None,
    ):
        """
        Initialize message processor.

        Args:
            firestore: Firestore service instance
            vertex_ai: Vertex AI service instance
            slack: Slack service instance
            gcs: Optional GCS service instance for file uploads
        """
        self.firestore = firestore
        self.vertex_ai = vertex_ai
        self.slack = slack
        self.gcs = gcs

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
        agent = None
        try:
            # Extract event details
            event_data: Dict[str, Any] = event.event
            slack_user_id = event_data.get("user")
            channel_id = event_data.get("channel")
            message_text = event_data.get("text", "")

            # Extract and download any image attachments
            files = event_data.get("files", [])
            images = []

            if not all([slack_user_id, channel_id]):
                logger.warning(f"Incomplete event data: {event_data}")
                return

            # Log the channel type for debugging DM threading issues
            channel_type = event_data.get("channel_type", "unknown")
            logger.info(
                f"Processing message from user {slack_user_id} in channel {channel_id} "
                f"(type: {channel_type}), files: {len(files)}"
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

            # Download and process image files from Slack
            failed_file_uploads = 0
            total_image_files = 0
            for file in files:
                mimetype = file.get("mimetype", "")
                if mimetype.startswith("image/"):
                    total_image_files += 1
                    url = file.get("url_private")
                    filename = file.get("name")
                    if url:
                        try:
                            image_bytes = await self.slack.download_file(
                                token=agent.slack_bot_token,
                                url=url
                            )

                            # Upload to GCS if enabled, otherwise use base64
                            if self.gcs:
                                gcs_result = await self.gcs.upload_file(
                                    file_bytes=image_bytes,
                                    mime_type=mimetype,
                                    original_filename=filename,
                                )
                                images.append({
                                    "gcs_uri": gcs_result["gcs_uri"],
                                    "mime_type": mimetype,
                                })
                                logger.info(
                                    f"Uploaded image to GCS: {gcs_result['gcs_uri']} "
                                    f"({len(image_bytes)} bytes)"
                                )
                            else:
                                # Fallback to base64 encoding (only when GCS not configured)
                                images.append({
                                    "data": base64.b64encode(image_bytes).decode("utf-8"),
                                    "mime_type": mimetype,
                                })
                                logger.info(
                                    f"Downloaded image (base64): {mimetype}, "
                                    f"{len(image_bytes)} bytes"
                                )
                        except Exception as e:
                            logger.error(f"Failed to process image: {e}")
                            failed_file_uploads += 1

            # If files were attached but none could be processed, notify user and stop
            if total_image_files > 0 and failed_file_uploads == total_image_files:
                logger.warning(
                    f"All {failed_file_uploads} file upload(s) failed for user {slack_user_id}"
                )
                dm_channel = await self.slack.open_conversation(
                    token=agent.slack_bot_token, user_id=slack_user_id
                )
                await self.slack.post_message(
                    token=agent.slack_bot_token,
                    channel=dm_channel,
                    text="I'm sorry, you tried to send me a file but I don't have any place to put it!",
                )
                return

            # Resolve Slack user's display name and prefix the message
            # so the agent knows who is talking
            user_info = await self.slack.get_user_info(
                token=agent.slack_bot_token, user_id=slack_user_id
            )
            if user_info:
                user_display_name = (
                    user_info.get("profile", {}).get("display_name")
                    or user_info.get("real_name")
                    or slack_user_id
                )
            else:
                user_display_name = slack_user_id

            message_text = f"[From: {user_display_name} | SlackID: {slack_user_id}] {message_text}"
            logger.info(f"Resolved user identity: {user_display_name} ({slack_user_id})")

            # Embed image references in the message text
            # The agent will use view_image() tool to see the actual image content
            if images:
                image_refs = []
                for img in images:
                    if "gcs_uri" in img:
                        image_refs.append(f"[IMAGE: {img['gcs_uri']} | {img['mime_type']}]")
                if image_refs:
                    image_prefix = "\n".join(image_refs)
                    message_text = f"{image_prefix}\n\n{message_text}"
                    logger.info(f"Embedded {len(image_refs)} image reference(s) in message")

            # Step 2: Get or create Vertex AI session
            session_id = await self._get_or_create_session(
                slack_user_id=slack_user_id,
                agent_id=agent.id,
                vertex_ai_agent_id=agent.vertex_ai_agent_id,
            )

            # Step 3: Send message to Vertex AI Agent Engine
            # Note: images are embedded in message_text, not passed separately
            # (ADK Runner.run() doesn't support 'images' parameter)
            response = await self.vertex_ai.send_message(
                agent_id=agent.vertex_ai_agent_id,
                session_id=session_id,
                message=message_text,
            )

            # Step 4: Post response to Slack
            # Handle empty responses with a user-friendly message
            response_text = response.text.strip()
            if not response_text:
                logger.warning(
                    f"Empty response from agent (images: {len(images) if images else 0})"
                )
                response_text = (
                    "I didn't like that request. Did you send me a file when I'm not "
                    "set up for it? Or exceeded the character limit?"
                )

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
                token=agent.slack_bot_token, channel=dm_channel, text=response_text
            )

            logger.info(f"Successfully processed message for user {slack_user_id}")

        except ResourceExhaustedError as e:
            # Google API rate limit hit - send friendly message to user
            logger.warning(f"Rate limit hit for user {slack_user_id}: {e}")
            try:
                if agent:
                    dm_channel = await self.slack.open_conversation(
                        token=agent.slack_bot_token, user_id=slack_user_id
                    )
                    await self.slack.post_message(
                        token=agent.slack_bot_token,
                        channel=dm_channel,
                        text=str(e),
                    )
            except Exception as slack_error:
                logger.error(f"Failed to send rate limit message to Slack: {slack_error}")

        except Exception as e:
            logger.exception(f"Unexpected error processing Slack event: {e}")

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
