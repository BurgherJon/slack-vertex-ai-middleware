"""Google Chat Events API endpoint."""
import logging
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.services.message_processor_v2 import MessageProcessorV2
from app.services.platforms.google_chat_connector import GoogleChatConnector
from app.core.dependencies import get_message_processor_v2, get_firestore_service
from app.services.firestore_service import FirestoreService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google-chat", tags=["google-chat"])


@router.post("/events")
async def google_chat_events(
    request: Request,
    background_tasks: BackgroundTasks,
    message_processor: MessageProcessorV2 = Depends(get_message_processor_v2),
    firestore: FirestoreService = Depends(get_firestore_service),
):
    """
    Google Chat Events API endpoint.

    Handles:
    1. URL verification (when configuring the webhook)
    2. Message events from Google Chat

    Returns 200 immediately. Processes events in background.

    Args:
        request: FastAPI request object
        background_tasks: FastAPI background tasks
        message_processor: Message processor service (v2)
        firestore: Firestore service

    Returns:
        JSON response acknowledging receipt
    """
    # Parse JSON
    data = await request.json()

    # Google Chat events have structure: {chat: {messagePayload: {message: ...}}}
    # Check if this is a message event
    chat_data = data.get("chat", {})
    message_payload = chat_data.get("messagePayload")

    if not message_payload:
        # Not a message event - could be ADDED_TO_SPACE, REMOVED_FROM_SPACE, etc.
        logger.info(f"Received non-message Google Chat event: {list(data.keys())}")
        return JSONResponse(content={"status": "ok"})

    # Handle message event
    try:
        message = message_payload.get("message", {})
        space = message.get("space", {})
        space_name = space.get("name")

        # Ignore bot messages to prevent loops
        sender = message.get("sender", {})
        sender_type = sender.get("type")
        if sender_type == "BOT":
            logger.debug("Ignoring bot message to prevent loops")
            return JSONResponse(content={"status": "ok"})

        logger.info(
            f"Received message event from space: {space_name}, "
            f"sender: {sender.get('name')}, "
            f"text: {message.get('text')}"
        )

        # Step 1: Identify which agent this message is for
        # Look up agent by space (for group chats) or by bot name
        # For DM conversations, we need to find the agent by service account

        # Get all agents and find the one configured for this space
        # For MVP, we'll use a simpler approach: find agent by checking
        # if the message was sent to a space where the bot is configured

        # TODO: Implement agent lookup by space or bot ID
        # For now, we'll try to match by checking which agent has Google Chat enabled

        agents = await firestore.list_agents()
        agent = None
        google_chat_config = None

        for candidate_agent in agents:
            config = candidate_agent.get_google_chat_config()
            if config and config.enabled:
                # For MVP, use the first enabled Google Chat agent
                # In production, match by bot name or space
                agent = candidate_agent
                google_chat_config = config
                break

        if not agent or not google_chat_config:
            logger.error("No agent found with Google Chat configuration")
            return JSONResponse(content={"status": "ok"})

        # Step 2: Create Google Chat connector with agent's secret reference
        if not google_chat_config.google_chat_service_account_secret:
            logger.error(f"Agent {agent.id} has no Google Chat service account secret")
            return JSONResponse(content={"status": "ok"})

        connector = GoogleChatConnector(
            service_account_secret_name=google_chat_config.google_chat_service_account_secret
        )

        # Step 3: Verify request (optional for MVP)
        # Google Chat webhook verification can be added here
        # signature_valid = await connector.verify_request(request)
        # if not signature_valid:
        #     logger.warning("Invalid Google Chat request signature")
        #     raise HTTPException(status_code=401, detail="Invalid signature")

        # Step 4: Parse Google Chat event into platform event
        platform_event = connector.parse_event(data)

        # Step 5: Process event in background
        background_tasks.add_task(
            message_processor.process_platform_event,
            platform_event,
            connector,
            agent.id
        )

        # Return immediately
        return JSONResponse(content={"status": "ok"})

    except Exception as e:
        logger.error(f"Error processing Google Chat event: {e}", exc_info=True)
        # Still return 200 to acknowledge receipt
        return JSONResponse(content={"status": "ok"})
