"""Vertex AI Reasoning Engine service."""
import logging
from typing import Optional
import uuid
import asyncio
import json

import vertexai
from vertexai.preview import reasoning_engines
from google.cloud.aiplatform_v1beta1.types import reasoning_engine_execution_service as res_types
from google.protobuf import struct_pb2
from google.api_core.exceptions import ResourceExhausted

from app.config import get_settings
from app.core.exceptions import ResourceExhaustedError

logger = logging.getLogger(__name__)


class VertexAIResponse:
    """Wrapper for Vertex AI agent response."""

    def __init__(self, text: str):
        """
        Initialize response.

        Args:
            text: Response text from the agent
        """
        self.text = text


class VertexAIService:
    """Handles Vertex AI Reasoning Engine operations."""

    def __init__(self):
        """Initialize Vertex AI client."""
        settings = get_settings()
        vertexai.init(
            project=settings.gcp_project_id, location=settings.gcp_location
        )
        self._engines: dict = {}
        self._exec_clients: dict = {}
        logger.info(
            f"Vertex AI initialized for project: {settings.gcp_project_id}, "
            f"location: {settings.gcp_location}"
        )

    def _get_engine(self, agent_id: str) -> reasoning_engines.ReasoningEngine:
        """Get or create a Reasoning Engine instance."""
        if agent_id not in self._engines:
            engine = reasoning_engines.ReasoningEngine(agent_id)
            self._engines[agent_id] = engine
            self._exec_clients[agent_id] = engine.execution_api_client
            logger.info(f"Created ReasoningEngine instance for: {agent_id}")
        return self._engines[agent_id]

    async def create_session(self, agent_id: str, user_name: Optional[str] = None) -> str:
        """
        Create a new session in the Reasoning Engine.

        Args:
            agent_id: Vertex AI reasoning engine resource name
            user_name: Optional user's actual name to use as user_id

        Returns:
            Session ID from the Reasoning Engine
        """
        try:
            engine = self._get_engine(agent_id)

            # Use user's actual name if provided, otherwise generate a random ID
            if user_name:
                user_id = user_name
            else:
                user_id = f"user-{uuid.uuid4().hex[:12]}"

            # Create session in the Reasoning Engine
            loop = asyncio.get_event_loop()
            session = await loop.run_in_executor(
                None,
                lambda: engine.create_session(user_id=user_id)
            )

            session_id = session.get("id", f"session-{uuid.uuid4().hex[:16]}")

            # Store user_id with session_id for later queries
            # We'll encode both in the session_id we return
            combined_id = f"{user_id}:{session_id}"

            logger.info(f"Created Reasoning Engine session for user '{user_name}': {combined_id}")
            return combined_id

        except ResourceExhausted as e:
            logger.warning(f"Rate limit exceeded creating session for agent {agent_id}: {e}")
            raise ResourceExhaustedError(
                "Looks like Google won't let me think right now, try again in a minute."
            )
        except Exception as e:
            error_str = str(e).lower()
            if "429" in str(e) or "resource_exhausted" in error_str:
                logger.warning(
                    f"Rate limit exceeded (wrapped) creating session for agent {agent_id}: {e}"
                )
                raise ResourceExhaustedError(
                    "Looks like Google won't let me think right now, try again in a minute."
                )
            logger.error(f"Error creating session for agent {agent_id}: {e}")
            raise

    async def send_message(
        self, agent_id: str, session_id: str, message: str
    ) -> VertexAIResponse:
        """
        Send message to Vertex AI Reasoning Engine and get response.

        Args:
            agent_id: Vertex AI reasoning engine resource name
            session_id: Combined user_id:session_id from create_session
            message: User message text (may contain embedded image references)

        Returns:
            VertexAIResponse containing agent's response text
        """
        message_length = len(message)
        logger.info(f"Sending message to agent (length: {message_length} chars)")

        try:
            engine = self._get_engine(agent_id)
            exec_client = self._exec_clients[agent_id]

            # Parse the combined session_id
            if ":" in session_id:
                user_id, re_session_id = session_id.split(":", 1)
            else:
                # Fallback for old-style session IDs
                user_id = session_id
                re_session_id = None

            # Create input as Struct
            input_struct = struct_pb2.Struct()
            input_data = {
                "message": message,
                "user_id": user_id,
            }
            if re_session_id:
                input_data["session_id"] = re_session_id
            input_struct.update(input_data)

            # Create the request
            request = res_types.StreamQueryReasoningEngineRequest(
                name=engine.resource_name,
                input=input_struct,
                class_method="stream_query"
            )

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()

            def stream_query():
                responses = []
                for chunk in exec_client.stream_query_reasoning_engine(request=request):
                    if chunk.data:
                        chunk_str = chunk.data.decode('utf-8')
                        responses.append(chunk_str)
                return responses

            chunks = await loop.run_in_executor(None, stream_query)
            chunk_count = len(chunks)

            # Extract text content from response chunks
            full_response = self._extract_text_from_chunks(
                chunks, message_length=message_length
            )

            if not full_response.strip():
                logger.warning(
                    f"Empty response from Reasoning Engine {agent_id} "
                    f"for session {session_id} "
                    f"(received {chunk_count} chunks)"
                )

            logger.info(
                f"Received response from Reasoning Engine {agent_id} "
                f"({chunk_count} chunks, {len(full_response)} chars)"
            )

            return VertexAIResponse(text=full_response)

        except ResourceExhausted as e:
            logger.warning(
                f"Rate limit exceeded for Reasoning Engine {agent_id}, "
                f"session {session_id}: {e}"
            )
            raise ResourceExhaustedError(
                "Looks like Google won't let me think right now, try again in a minute."
            )
        except Exception as e:
            error_str = str(e).lower()
            if "429" in str(e) or "resource_exhausted" in error_str:
                logger.warning(
                    f"Rate limit exceeded (wrapped) for Reasoning Engine {agent_id}, "
                    f"session {session_id}: {e}"
                )
                raise ResourceExhaustedError(
                    "Looks like Google won't let me think right now, try again in a minute."
                )
            logger.error(
                f"Error sending message to Reasoning Engine {agent_id}, "
                f"session {session_id}: {e}"
            )
            raise

    def _extract_text_from_chunks(
        self, chunks: list, message_length: int = 0
    ) -> str:
        """
        Extract text content from Reasoning Engine response chunks.

        The chunks contain JSON with various content types including
        function calls, function responses, and text content.
        We extract only the final text content.

        Args:
            chunks: List of JSON strings from the stream
            message_length: Length of the original message (for diagnostic logging)

        Returns:
            Extracted text content
        """
        text_parts = []
        chunk_count = len(chunks)

        for i, chunk_str in enumerate(chunks):
            try:
                chunk = json.loads(chunk_str)
                content = chunk.get("content", {})
                parts = content.get("parts", [])

                for part in parts:
                    # Extract text content (skip function calls/responses)
                    if "text" in part:
                        text_parts.append(part["text"])

            except json.JSONDecodeError:
                # If not valid JSON, might be raw text
                text_parts.append(chunk_str)
            except Exception as e:
                logger.debug(f"Error parsing chunk {i}: {e}")
                continue

        result = "".join(text_parts)

        # Log diagnostic info when response is empty
        if not result.strip() and chunk_count > 0:
            # Log first chunk preview to help diagnose empty responses
            first_chunk_preview = chunks[0][:500] if chunks else "(no chunks)"
            logger.warning(
                f"Empty text extracted from {chunk_count} chunks. "
                f"Input message was {message_length} chars. "
                f"First chunk preview: {first_chunk_preview}"
            )

        return result
