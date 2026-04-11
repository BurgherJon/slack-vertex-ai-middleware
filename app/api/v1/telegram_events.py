"""Telegram Events API endpoint."""
import logging
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.services.message_processor_v2 import MessageProcessorV2
from app.services.platforms.telegram_connector import TelegramConnector
from app.core.dependencies import get_message_processor_v2, get_firestore_service
from app.services.firestore_service import FirestoreService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/events")
async def telegram_events(
    request: Request,
    background_tasks: BackgroundTasks,
    message_processor: MessageProcessorV2 = Depends(get_message_processor_v2),
    firestore: FirestoreService = Depends(get_firestore_service),
):
    """
    Telegram Bot API webhook endpoint.

    Handles message updates from Telegram. For MVP, uses the first enabled
    Telegram agent. In production with multiple Telegram bots, could match
    by bot username or separate webhook URLs per bot.

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

    # Telegram sends updates with structure: {"update_id": 123, "message": {...}}
    # Check if this is a message update
    message = data.get("message")

    if not message:
        # Not a message update - could be edited_message, channel_post, etc.
        logger.info(f"Received non-message Telegram update: {list(data.keys())}")
        return JSONResponse(content={"ok": True})

    # Handle message update
    try:
        # Ignore messages from bots to prevent loops
        from_user = message.get("from", {})
        is_bot = from_user.get("is_bot", False)

        if is_bot:
            logger.debug("Ignoring bot message to prevent loops")
            return JSONResponse(content={"ok": True})

        # Ignore edited messages
        if "edit_date" in message:
            logger.debug("Ignoring edited message")
            return JSONResponse(content={"ok": True})

        logger.info(
            f"Received Telegram message from user {from_user.get('id')}: "
            f"{message.get('text', '<non-text message>')}"
        )

        # Step 1: Find enabled Telegram agent
        # For MVP: Find first enabled Telegram agent
        # TODO: In production with multiple Telegram bots, match by bot username
        # or use separate webhook URLs (e.g., /telegram/events/<agent_id>)
        agents = await firestore.list_agents()
        agent = None

        for candidate_agent in agents:
            config = candidate_agent.get_telegram_config()
            if config and config.enabled:
                agent = candidate_agent
                break

        if not agent:
            logger.error("No enabled Telegram agent found")
            return JSONResponse(content={"ok": True})

        # Step 2: Get Telegram platform config from agent
        telegram_config = agent.get_telegram_config()
        if not telegram_config or not telegram_config.enabled:
            logger.error(f"Agent {agent.id} does not have Telegram enabled")
            return JSONResponse(content={"ok": True})

        # Validate that we have either direct token or Secret Manager config
        has_direct_token = telegram_config.telegram_bot_token is not None
        has_secret_config = (
            telegram_config.telegram_bot_token_secret is not None and
            telegram_config.telegram_bot_token_project_id is not None
        )

        if not has_direct_token and not has_secret_config:
            logger.error(
                f"Agent {agent.id} Telegram config missing bot token. "
                f"Need either telegram_bot_token OR (telegram_bot_token_secret + telegram_bot_token_project_id)"
            )
            return JSONResponse(content={"ok": True})

        # Step 3: Verify webhook secret token (if configured)
        # Create temporary connector for verification
        webhook_secret = telegram_config.telegram_webhook_secret

        if webhook_secret:
            connector_check = TelegramConnector(
                bot_token=telegram_config.telegram_bot_token if has_direct_token else None,
                bot_token_secret=telegram_config.telegram_bot_token_secret if has_secret_config else None,
                bot_token_project_id=telegram_config.telegram_bot_token_project_id if has_secret_config else None,
                webhook_secret=webhook_secret
            )

            if not await connector_check.verify_request(request):
                logger.warning("Invalid Telegram webhook secret token")
                raise HTTPException(status_code=401, detail="Invalid webhook secret")

        # Step 4: Create Telegram connector with agent's credentials
        connector = TelegramConnector(
            bot_token=telegram_config.telegram_bot_token if has_direct_token else None,
            bot_token_secret=telegram_config.telegram_bot_token_secret if has_secret_config else None,
            bot_token_project_id=telegram_config.telegram_bot_token_project_id if has_secret_config else None,
            webhook_secret=None  # Not needed for sending messages
        )

        # Step 5: Parse Telegram update into platform event
        platform_event = connector.parse_event(data)

        # Step 6: Process event in background
        background_tasks.add_task(
            message_processor.process_platform_event,
            platform_event,
            connector,
            agent.id
        )

        # Return immediately - Telegram expects 200 OK
        return JSONResponse(content={"ok": True})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Telegram event: {e}", exc_info=True)
        # Still return 200 to acknowledge receipt
        return JSONResponse(content={"ok": True})
