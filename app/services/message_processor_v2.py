"""Platform-agnostic message processing service (v2 - multi-platform)."""
import base64
import logging
from typing import Optional, TYPE_CHECKING

from app.schemas.platform_event import PlatformEvent
from app.services.firestore_service import FirestoreService
from app.services.vertex_ai_service import VertexAIService
from app.services.identity_service import IdentityService
from app.services.platforms.base import PlatformConnector
from app.core.exceptions import ResourceExhaustedError

if TYPE_CHECKING:
    from app.services.gcs_service import GCSService

logger = logging.getLogger(__name__)


class MessageProcessorV2:
    """
    Platform-agnostic message processor.

    Handles messages from any platform (Slack, Google Chat, etc.) using
    unified user identities and platform connectors.
    """

    def __init__(
        self,
        firestore: FirestoreService,
        vertex_ai: VertexAIService,
        identity: IdentityService,
        gcs: Optional["GCSService"] = None,
    ):
        """
        Initialize message processor.

        Args:
            firestore: Firestore service instance
            vertex_ai: Vertex AI service instance
            identity: Identity service instance
            gcs: Optional GCS service instance for file uploads
        """
        self.firestore = firestore
        self.vertex_ai = vertex_ai
        self.identity = identity
        self.gcs = gcs

    async def process_platform_event(
        self,
        event: PlatformEvent,
        connector: PlatformConnector,
        agent_id: str
    ) -> None:
        """
        Process a platform event in the background.

        Flow:
        1. Resolve platform identity to unified user
        2. Get/create Vertex AI session
        3. Download and process file attachments
        4. Send message to Vertex AI
        5. Post response back via platform connector

        Args:
            event: Platform event (normalized from Slack, Google Chat, etc.)
            connector: Platform connector for sending responses
            agent_id: Agent ID handling this message

        Note:
            This function catches all exceptions to prevent background task failures
            from crashing the application.
        """
        user = None
        try:
            # Step 1: Resolve platform identity to unified user
            # Note: For Google Chat, get_user_info() will fail since the Chat API
            # doesn't have a users.get() method. We use display_name from event
            # for initial user creation, but always use user.primary_name after that.
            user_info = await connector.get_user_info(event.user_id)
            display_name = user_info.get("display_name", event.user_id)
            email = user_info.get("email") or event.user_email

            user = await self.identity.resolve_user(
                platform=event.platform,
                platform_user_id=event.user_id,
                email=email,
                display_name=display_name
            )

            logger.info(
                f"Processing message from user {user.id} ({user.primary_name}) "
                f"on {event.platform}"
            )

            # Get agent configuration
            agent = await self.firestore.get_agent_by_id(agent_id)
            if not agent:
                logger.error(f"Agent {agent_id} not found")
                return

            # Download and process image files
            images = []
            failed_file_uploads = 0
            total_image_files = 0

            for file in event.files:
                mimetype = file.get("mimetype", "")
                if mimetype.startswith("image/"):
                    total_image_files += 1
                    url = file.get("url_private") or file.get("url")
                    filename = file.get("name")
                    if url:
                        try:
                            image_bytes = await connector.download_file(url)

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
                                # Fallback to base64 encoding
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
                    f"All {failed_file_uploads} file upload(s) failed for user {user.id}"
                )
                conversation_id = await connector.open_conversation(
                    event.user_id,
                    space_id=event.space_id
                )
                await connector.send_message(
                    recipient_id=conversation_id,
                    text="I'm sorry, you tried to send me a file but I don't have any place to put it!",
                )
                return

            # Build message text with user identity prefix
            message_text = f"[From: {user.primary_name} | {event.platform}_id: {event.user_id}] {event.message_text}"

            # Embed image references in the message text
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
                user_id=user.id,
                agent_id=agent_id,
                vertex_ai_agent_id=agent.vertex_ai_agent_id,
                platform=event.platform,
                user_name=user.primary_name
            )

            # Step 3: Send message to Vertex AI Agent Engine
            response = await self.vertex_ai.send_message(
                agent_id=agent.vertex_ai_agent_id,
                session_id=session_id,
                message=message_text,
            )

            # Step 4: Post response back via platform connector
            response_text = response.text.strip()
            if not response_text:
                image_count = len(images) if images else 0
                message_len = len(message_text)
                logger.warning(
                    f"Empty response from agent for user {user.id} "
                    f"(images: {image_count}, message_length: {message_len})"
                )
                # Provide context-appropriate error message
                if image_count > 0:
                    response_text = (
                        "I wasn't able to process that request. "
                        "I may not be set up to handle images."
                    )
                else:
                    response_text = (
                        "I wasn't able to process that request. "
                        "Please try rephrasing or shortening your message."
                    )

            # Open conversation and send response
            conversation_id = await connector.open_conversation(
                event.user_id,
                space_id=event.space_id
            )
            await connector.send_message(
                recipient_id=conversation_id,
                text=response_text
            )

            logger.info(
                f"Successfully processed message for user {user.id} on {event.platform}"
            )

        except ResourceExhaustedError as e:
            # Google API rate limit hit - send friendly message to user
            logger.warning(f"Rate limit hit for user {user.id if user else 'unknown'}: {e}")
            try:
                if user and connector:
                    conversation_id = await connector.open_conversation(
                        event.user_id,
                        space_id=event.space_id
                    )
                    await connector.send_message(
                        recipient_id=conversation_id,
                        text=str(e),
                    )
            except Exception as slack_error:
                logger.error(f"Failed to send rate limit message: {slack_error}")

        except Exception as e:
            logger.exception(f"Unexpected error processing platform event: {e}")

    async def _get_or_create_session(
        self,
        user_id: str,
        agent_id: str,
        vertex_ai_agent_id: str,
        platform: str,
        user_name: str = None
    ) -> str:
        """
        Get existing session or create new one for unified user.

        Args:
            user_id: Unified user ID from users collection
            agent_id: Agent ID from agents collection
            vertex_ai_agent_id: Vertex AI agent resource name
            platform: Platform this message came from
            user_name: User's actual name to pass to the Reasoning Engine

        Returns:
            Vertex AI session ID

        Raises:
            Exception: If session operations fail
        """
        # Try to get existing session
        session = await self.firestore.get_session_by_user(
            user_id=user_id,
            agent_id=agent_id
        )

        if session:
            # Update last activity timestamp and track platform usage
            await self.firestore.update_session_platforms(session.id, platform)
            logger.info(
                f"Using existing session: {session.id} "
                f"(now includes platform: {platform})"
            )
            return session.vertex_ai_session_id

        # No existing session, create new one in Vertex AI
        # Pass user's actual name so the agent can recognize them
        vertex_session_id = await self.vertex_ai.create_session(
            vertex_ai_agent_id,
            user_name=user_name
        )

        # Store in Firestore
        await self.firestore.create_session_for_user(
            user_id=user_id,
            agent_id=agent_id,
            vertex_ai_session_id=vertex_session_id,
            platform=platform
        )

        logger.info(f"Created new session: {vertex_session_id} for user {user_id}")
        return vertex_session_id
