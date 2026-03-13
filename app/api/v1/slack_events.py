"""Slack Events API endpoint."""
import hmac
import hashlib
import time
import logging
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.schemas.slack import SlackEvent, SlackChallenge
from app.services.message_processor import MessageProcessor
from app.core.dependencies import get_message_processor
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])


@router.post("/events")
async def slack_events(
    request: Request,
    background_tasks: BackgroundTasks,
    message_processor: MessageProcessor = Depends(get_message_processor),
):
    """
    Slack Events API endpoint.

    Handles:
    1. URL verification challenge (when configuring Request URL)
    2. Event callbacks (app_mention, message, etc.)

    Returns 200 within 3 seconds. Processes events in background.

    Args:
        request: FastAPI request object
        background_tasks: FastAPI background tasks
        message_processor: Message processor service

    Returns:
        JSON response with challenge (for verification) or ok status
    """
    settings = get_settings()

    # Acknowledge Slack retries immediately to prevent duplicate processing.
    # Slack retries events (up to 3 times) if the webhook doesn't respond
    # quickly enough. These retries carry the X-Slack-Retry-Num header.
    retry_num = request.headers.get("X-Slack-Retry-Num")
    if retry_num is not None:
        retry_reason = request.headers.get("X-Slack-Retry-Reason", "unknown")
        logger.info(f"Acknowledging Slack retry #{retry_num} (reason: {retry_reason})")
        return JSONResponse(content={"ok": True})

    # Get request headers
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    # Prevent replay attacks (reject requests older than 5 minutes)
    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            logger.warning("Request timestamp too old, possible replay attack")
            raise HTTPException(status_code=400, detail="Request timestamp too old")
    except (ValueError, TypeError):
        logger.warning("Invalid timestamp in request")
        raise HTTPException(status_code=400, detail="Invalid timestamp")

    # Get request body
    body = await request.body()
    body_str = body.decode("utf-8")

    # Verify Slack request signature
    sig_basestring = f"v0:{timestamp}:{body_str}"
    computed_signature = (
        "v0="
        + hmac.new(
            settings.slack_signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )

    if not hmac.compare_digest(computed_signature, signature):
        logger.warning("Invalid Slack signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse JSON
    data = await request.json()

    # Handle URL verification challenge
    if data.get("type") == "url_verification":
        try:
            challenge = SlackChallenge(**data)
            logger.info("Slack URL verification challenge received")
            return JSONResponse(content={"challenge": challenge.challenge})
        except Exception as e:
            logger.error(f"Error parsing Slack challenge: {e}")
            raise HTTPException(status_code=400, detail="Invalid challenge format")

    # Handle event callback
    if data.get("type") == "event_callback":
        try:
            event = SlackEvent(**data)

            # Ignore bot messages to prevent loops
            if event.event.get("bot_id"):
                logger.debug("Ignoring bot message to prevent loops")
                return JSONResponse(content={"ok": True})

            # Ignore message edits and deletions (only handle new messages)
            if event.event.get("subtype") in ["message_changed", "message_deleted"]:
                logger.debug(f"Ignoring message subtype: {event.event.get('subtype')}")
                return JSONResponse(content={"ok": True})

            logger.info(f"Received event: {event.event.get('type')} from user {event.event.get('user')}")

            # Process event in background (must return 200 within 3 seconds)
            background_tasks.add_task(message_processor.process_slack_event, event)

            # Return immediately
            return JSONResponse(content={"ok": True})

        except Exception as e:
            logger.error(f"Error parsing Slack event: {e}")
            # Still return 200 to acknowledge receipt
            return JSONResponse(content={"ok": True})

    # Unknown event type
    logger.warning(f"Unknown Slack event type: {data.get('type')}")
    return JSONResponse(content={"ok": True})
