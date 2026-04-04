"""Slack platform connector implementation."""
import logging
import hmac
import hashlib
import time
from typing import Optional
from fastapi import Request

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
import aiohttp

from app.services.platforms.base import PlatformConnector
from app.schemas.platform_event import PlatformEvent

logger = logging.getLogger(__name__)


class SlackConnector(PlatformConnector):
    """
    Slack platform connector implementation.

    Handles Slack-specific operations including message sending,
    file downloads, and webhook verification.
    """

    def __init__(self, bot_token: str, signing_secret: Optional[str] = None):
        """
        Initialize Slack connector.

        Args:
            bot_token: Slack Bot User OAuth Token (xoxb-...)
            signing_secret: Slack signing secret for webhook verification
        """
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self.client = AsyncWebClient(token=bot_token)

    async def send_message(self, recipient_id: str, text: str) -> dict:
        """
        Send message to Slack channel.

        Args:
            recipient_id: Slack channel ID or DM channel ID
            text: Message text to send

        Returns:
            Slack API response dict

        Raises:
            SlackApiError: If Slack API call fails
        """
        try:
            logger.debug(f"Posting message to Slack channel: {recipient_id}")
            response = await self.client.chat_postMessage(
                channel=recipient_id,
                text=text
            )

            if response["ok"]:
                response_channel = response.get("channel")
                response_ts = response.get("ts")
                logger.info(
                    f"Successfully posted message to channel: {recipient_id}, "
                    f"response_channel: {response_channel}, ts: {response_ts}"
                )

                if response_channel != recipient_id:
                    logger.warning(
                        f"Channel mismatch! Requested: {recipient_id}, "
                        f"Got: {response_channel}"
                    )
            else:
                logger.error(
                    f"Slack API returned ok=False for channel {recipient_id}: "
                    f"{response}"
                )

            return response

        except SlackApiError as e:
            error_message = e.response.get("error", "unknown_error")
            logger.error(
                f"Slack API error posting to channel {recipient_id}: {error_message}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error posting to Slack channel {recipient_id}: {e}"
            )
            raise

    async def download_file(self, file_url: str) -> bytes:
        """
        Download a file from Slack's private URL.

        Slack file URLs (url_private) require authentication with the bot token.

        Args:
            file_url: The url_private from a Slack file object

        Returns:
            Raw file bytes

        Raises:
            Exception: If download fails
        """
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.bot_token}"}
            async with session.get(file_url, headers=headers) as response:
                if response.status == 200:
                    file_bytes = await response.read()
                    logger.info(
                        f"Downloaded file from Slack: {len(file_bytes)} bytes"
                    )
                    return file_bytes
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Failed to download file: {response.status} - {error_text}"
                    )
                    raise Exception(
                        f"Failed to download Slack file: {response.status}"
                    )

    async def get_user_info(self, user_id: str) -> dict:
        """
        Get Slack user profile info (display name, real name).

        Args:
            user_id: Slack user ID (U...)

        Returns:
            User info dict from Slack API with keys:
                - display_name: User's display name
                - real_name: User's real name
                - email: Email (if available)

        Raises:
            SlackApiError: If Slack API call fails
        """
        try:
            response = await self.client.users_info(user=user_id)
            if response["ok"]:
                user = response["user"]
                profile = user.get("profile", {})
                return {
                    "display_name": profile.get("display_name") or user.get("real_name") or user_id,
                    "real_name": user.get("real_name"),
                    "email": profile.get("email")
                }
            else:
                logger.error(f"Failed to get user info: {response}")
                return {"display_name": user_id}
        except SlackApiError as e:
            logger.error(
                f"Error getting user info for {user_id}: {e.response.get('error')}"
            )
            return {"display_name": user_id}

    async def open_conversation(self, user_id: str) -> str:
        """
        Open or get existing DM conversation with a user.

        This ensures we're using the canonical DM channel ID, which can
        help with message threading issues.

        Args:
            user_id: Slack user ID to open DM with

        Returns:
            Channel ID for the DM conversation

        Raises:
            SlackApiError: If conversation cannot be opened
        """
        try:
            response = await self.client.conversations_open(users=[user_id])
            if response["ok"]:
                channel_id = response["channel"]["id"]
                logger.debug(
                    f"Opened conversation with user {user_id}: {channel_id}"
                )
                return channel_id
            else:
                logger.error(f"Failed to open conversation: {response}")
                raise Exception(f"Failed to open conversation: {response}")
        except SlackApiError as e:
            logger.error(
                f"Error opening conversation: {e.response.get('error')}"
            )
            raise

    async def verify_request(self, request: Request) -> bool:
        """
        Verify Slack request signature.

        Slack signs all requests with an HMAC-SHA256 signature.

        Args:
            request: FastAPI request object

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.signing_secret:
            logger.warning("No signing secret configured, skipping verification")
            return True

        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        # Prevent replay attacks (reject requests older than 5 minutes)
        try:
            if abs(time.time() - int(timestamp)) > 60 * 5:
                logger.warning("Request timestamp too old, possible replay attack")
                return False
        except (ValueError, TypeError):
            logger.warning("Invalid timestamp in request")
            return False

        # Get request body
        body = await request.body()
        body_str = body.decode("utf-8")

        # Verify signature
        sig_basestring = f"v0:{timestamp}:{body_str}"
        computed_signature = (
            "v0="
            + hmac.new(
                self.signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        return hmac.compare_digest(computed_signature, signature)

    def parse_event(self, data: dict) -> PlatformEvent:
        """
        Parse Slack event into unified PlatformEvent.

        Args:
            data: Slack event callback data

        Returns:
            Normalized PlatformEvent

        Raises:
            ValueError: If event format is invalid
        """
        event_data = data.get("event", {})

        user_id = event_data.get("user")
        channel_id = event_data.get("channel")
        message_text = event_data.get("text", "")
        files = event_data.get("files", [])

        if not user_id or not channel_id:
            raise ValueError(f"Invalid Slack event: missing user or channel")

        return PlatformEvent(
            platform="slack",
            user_id=user_id,
            user_email=None,  # Slack doesn't provide email in events
            message_text=message_text,
            space_id=channel_id,
            files=files,
            raw_event=data
        )
