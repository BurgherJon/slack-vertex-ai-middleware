# Agent Deployment - Middleware Integration

This guide covers how to integrate your Vertex AI agent with the Slack middleware layer.

⚠️ **IMPORTANT**: Copy this file to your agent repository (e.g., `growth-coach-agent/MIDDLEWARE_INTEGRATION.md`) so you see it when working on the agent!

## Table of Contents

1. [Creating a Brand New Agent](#creating-a-brand-new-agent)
2. [Updating an Existing Agent](#updating-an-existing-agent)
3. [Troubleshooting](#troubleshooting)
4. [Quick Reference](#quick-reference)
5. [Receiving Images from Slack](#receiving-images-from-slack)
6. [Building Scheduled Job Tools](#building-scheduled-job-tools)

---

## Creating a Brand New Agent

Follow these steps when creating a completely new agent and want to make it available via Slack.

### Step 1: Create Slack Bot (5 minutes)

> **IMPORTANT**: After creating your Slack app, ensure it is NOT configured as an "Agent or Assistant" in the **Agents & AI Apps** settings. This mode changes the DM UI to show messages separately instead of as a conversation thread.

```bash
# Navigate to middleware repo
cd /path/to/slack_to_agent_integration

# Option A: Use the template manifest (easiest)
# 1. Copy the template
cp slack-app-manifest.template.yml my-new-agent-manifest.yml

# 2. Edit the manifest (change app name, bot name, etc.)
nano my-new-agent-manifest.yml

# 3. Create the app using Slack CLI
slack apps create -m my-new-agent-manifest.yml
# Follow prompts to name the bot and select workspace

# Option B: Manual creation via web UI
# 1. Go to https://api.slack.com/apps
# 2. Create new app → From an app manifest
# 3. Copy/paste slack-app-manifest.template.yml
# 4. Customize the app name and bot name
```

### Step 2: Install Bot and Get Credentials

```bash
# After creating the app:
# 1. Go to https://api.slack.com/apps → Select your new app
# 2. Navigate to "OAuth & Permissions"
# 3. Click "Install to Workspace"
# 4. Copy the "Bot User OAuth Token" (starts with xoxb-)
# 5. Go to "Basic Information"
# 6. Copy the "Signing Secret"

# Save the token:
export NEW_AGENT_SLACK_BOT_TOKEN="xoxb-your-token-here"

# IMPORTANT: Add the new bot's signing secret to the middleware .env
# The middleware supports multiple comma-separated signing secrets:
# SLACK_SIGNING_SECRET=existing-secret,new-bot-signing-secret
# You must add the new secret BEFORE configuring Event Subscriptions,
# otherwise Slack's URL verification challenge will fail.

# IMPORTANT: Get the correct user_id (NOT the B... bot_id from Slack settings!)
# The middleware uses user_id from Slack's authorizations, which starts with U
curl -s https://slack.com/api/auth.test \
  -H "Authorization: Bearer $NEW_AGENT_SLACK_BOT_TOKEN" | jq .user_id
# Example output: "U0AFZ86NE00"

export NEW_AGENT_SLACK_BOT_ID="U0AFZ86NE00"  # Use the U... ID, not B...
```

### Step 3: Deploy Your Agent to Vertex AI

```bash
# In your agent repository (e.g., my-new-agent/)
# Deploy your agent using your deployment method

# For Vertex AI Reasoning Engines (ADK agents), the ID format is:
# projects/PROJECT/locations/LOCATION/reasoningEngines/ENGINE_ID

# Example: After deploying, you'll get an ID like:
# projects/my-project/locations/us-central1/reasoningEngines/7454674542670118912

export NEW_AGENT_VERTEX_ID="projects/YOUR_PROJECT/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID"
```

### Step 4: Register Agent with Middleware

```bash
cd /path/to/slack_to_agent_integration

python scripts/deploy_agent.py \
  --agent-name "My New Agent" \
  --vertex-ai-agent-id "$NEW_AGENT_VERTEX_ID" \
  --slack-bot-id "$NEW_AGENT_SLACK_BOT_ID" \
  --slack-bot-token "$NEW_AGENT_SLACK_BOT_TOKEN"

# This script will:
# 1. Validate the Vertex AI agent exists and is accessible
# 2. Validate the Slack bot token is valid
# 3. Create a new agent record in Firestore
# 4. Output confirmation and next steps
```

### Step 5: Configure Slack Events API

```bash
# The middleware needs to receive messages from Slack

# Get your middleware URL:
# - Local dev: Your ngrok URL (e.g., https://abc123.ngrok.io)
# - Production: Your Cloud Run URL

# Then:
# 1. Go to https://api.slack.com/apps → Your new app
# 2. Navigate to "Event Subscriptions"
# 3. Enable Events
# 4. Set Request URL: https://YOUR_MIDDLEWARE_URL/api/v1/slack/events
# 5. Wait for green checkmark ✓ (verification success)
# 6. Under "Subscribe to bot events", add: message.im
# 7. Click "Save Changes"
# 8. Reinstall the app to workspace if prompted
```

### Step 6: Test Your New Agent

```bash
# 1. Open Slack
# 2. Find your new bot in the Apps section (left sidebar)
# 3. Click on the bot to open a DM
# 4. Send it a message: "Hello!"
# 5. You should get a response from your Vertex AI agent

# Check logs if no response:
# Local development:
#   - Check your terminal running uvicorn for logs

# Production:
gcloud run logs read slack-vertex-middleware \
  --region us-central1 \
  --limit 50
```

### Step 7: Document in Your Agent Repo

```bash
# Copy this file to your agent repo for future reference:
cp /path/to/slack_to_agent_integration/docs/FOR_AGENT_DEVELOPERS.md \
   /path/to/your-agent-repo/MIDDLEWARE_INTEGRATION.md

# Edit MIDDLEWARE_INTEGRATION.md to include agent-specific info:
# - Your agent's Slack bot ID
# - Your agent's display name
# - Vertex AI agent ID
# - Any agent-specific deployment notes
```

**Example agent-specific documentation to add:**

```markdown
# My New Agent - Middleware Integration

## Agent Details
- **Display Name**: My New Agent
- **Slack Bot ID**: B01234567
- **Vertex AI Agent ID**: projects/my-project/locations/us-central1/agents/abc123

## Quick Update Commands

When deploying a new version:

\`\`\`bash
# After deploying to Vertex AI, update middleware:
python /path/to/slack_to_agent_integration/scripts/deploy_agent.py \\
  --agent-name "My New Agent" \\
  --vertex-ai-agent-id "projects/my-project/locations/us-central1/agents/NEW_ID" \\
  --slack-bot-id "B01234567" \\
  --slack-bot-token "$MY_NEW_AGENT_SLACK_TOKEN"
\`\`\`
```

---

## Updating an Existing Agent

When you deploy a new version of an existing agent to Vertex AI, you need to update the middleware.

### Quick Update (2 minutes)

1. **Deploy to Vertex AI** and get the new agent ID:

   ```bash
   # In your agent repository
   gcloud ai agents deploy --agent-file=agent.yaml --location=us-central1

   # Output will show:
   # Agent deployed: projects/YOUR_PROJECT/locations/us-central1/agents/NEW_ID

   # Copy this ID
   export NEW_VERTEX_AI_AGENT_ID="projects/YOUR_PROJECT/locations/us-central1/agents/NEW_ID"
   ```

2. **Update the middleware**:

   ```bash
   cd /path/to/slack_to_agent_integration

   python scripts/deploy_agent.py \
     --agent-name "Growth Coach" \
     --vertex-ai-agent-id "$NEW_VERTEX_AI_AGENT_ID" \
     --slack-bot-id "B01234567" \
     --slack-bot-token "$GROWTH_COACH_SLACK_TOKEN"
   ```

3. **Verify the update**:

   ```bash
   # Send a test DM to the bot in Slack
   # Check that it responds with the new agent version behavior

   # Check Firestore to verify update:
   gcloud firestore documents list agents --limit=10
   ```

### What This Does

The `deploy_agent.py` script updates Firestore so the middleware knows to route messages to your new agent version.

**Without this step**, Slack messages will still go to the OLD agent version!

---

## Troubleshooting

### Bot doesn't respond to messages

**Check Firestore**: Verify agent is registered with correct bot_id

```bash
# View Firestore collections
gcloud firestore collections list

# View agents in Firestore
gcloud firestore documents list agents

# Or use Firebase Console:
# https://console.firebase.google.com/project/YOUR_PROJECT/firestore
```

**Check Slack Events**: Ensure Request URL is verified (green checkmark)
- Go to https://api.slack.com/apps → Your app → Event Subscriptions
- Verify the Request URL shows a green checkmark

**Check logs**:

```bash
# Local development:
# Check your terminal running uvicorn

# Production:
gcloud run logs read slack-vertex-middleware \
  --region us-central1 \
  --limit 50 \
  --format json
```

### "Agent not found" error

**Verify agent ID is correct:**

```bash
# List all agents in Vertex AI
gcloud ai agents list --location=us-central1

# Get details of a specific agent
gcloud ai agents describe AGENT_ID --location=us-central1
```

**Check agent deployed successfully:**
- Ensure deployment completed without errors
- Verify using the Vertex AI Console

**Ensure you're using the full agent resource name:**
- Format: `projects/PROJECT_ID/locations/LOCATION/agents/AGENT_ID`
- Not just `AGENT_ID`

### "Slack bot token invalid"

**Get fresh token:**
1. Go to https://api.slack.com/apps → Your app
2. Navigate to "OAuth & Permissions"
3. Copy the "Bot User OAuth Token" (starts with `xoxb-`)
4. Ensure you're copying the entire token

**Verify token format:**
```bash
# Token should start with xoxb-
echo $SLACK_BOT_TOKEN | grep "^xoxb-"
```

**Check token hasn't been revoked:**
- In Slack app settings, check if app is still installed to workspace
- Try reinstalling the app if needed

### "URL verification failed" (Slack)

**Check signing secret is included in the middleware config:**
```bash
# In middleware repo .env file
grep SLACK_SIGNING_SECRET .env

# SLACK_SIGNING_SECRET supports comma-separated values (one per Slack app).
# Your new bot's signing secret must be in this list BEFORE configuring
# Event Subscriptions, otherwise the URL verification challenge will fail.
# Find each secret at: https://api.slack.com/apps → Your app → Basic Information
```

**Ensure middleware is running and accessible:**
```bash
# Test health endpoint
curl https://YOUR_MIDDLEWARE_URL/health

# Should return: {"status":"healthy"}
```

**For ngrok:** Make sure tunnel is active

```bash
# Check ngrok is running
curl http://localhost:4040/api/tunnels

# Should show active tunnel
```

### No response but no errors

**Check Vertex AI agent is responding:**
- Test directly in Vertex AI Console
- Send a test query to verify agent works independently

**Verify session management:**
```bash
# Check Firestore sessions collection
gcloud firestore documents list sessions --limit=10
```

**Check Slack bot has correct scopes:**
- Go to https://api.slack.com/apps → Your app → OAuth & Permissions
- Verify bot has these scopes:
  - `chat:write`
  - `im:history`
  - `im:read`

---

## Full Documentation

See the middleware repo for complete documentation:

- **Repository**: [Your GitHub Repo URL]
- **Main README**: [Your Repo]/README.md
- **Deployment Guide**: [Your Repo]/docs/AGENT_DEPLOYMENT.md
- **Slack Setup**: [Your Repo]/docs/SLACK_SETUP.md
- **GCP Setup**: [Your Repo]/docs/GCP_SETUP.md

---

## Quick Reference

### Create New Agent

```bash
# 1. Create Slack bot (use template manifest)
slack apps create -m slack-app-manifest.template.yml

# 2. Install to workspace and get credentials
# (via Slack web UI - get token starting with xoxb-)

# 3. Get the correct user_id for the bot (IMPORTANT: use U..., not B...)
curl -s https://slack.com/api/auth.test \
  -H "Authorization: Bearer xoxb-your-token" | jq .user_id

# 4. Deploy agent to Vertex AI (for Reasoning Engines)
# Get the reasoningEngines ID from your deployment

# 5. Register with middleware
python scripts/deploy_agent.py \
  --agent-name "Agent Name" \
  --vertex-ai-agent-id "projects/.../reasoningEngines/ID" \
  --slack-bot-id "U..." \
  --slack-bot-token "xoxb-..."

# 6. Configure Slack Events API
# (Set Request URL via Slack web UI)

# 7. Test with DM in Slack
```

### Update Existing Agent

```bash
# 1. Deploy to Vertex AI (get new agent ID)
# For Reasoning Engines, this will be a new reasoningEngines/ID

# 2. Get the correct user_id (if you don't have it saved)
curl -s https://slack.com/api/auth.test \
  -H "Authorization: Bearer xoxb-your-token" | jq .user_id

# 3. Update middleware
python scripts/deploy_agent.py \
  --agent-name "Agent Name" \
  --vertex-ai-agent-id "projects/.../reasoningEngines/NEW_ID" \
  --slack-bot-id "U..." \
  --slack-bot-token "xoxb-..."

# 4. Test with DM in Slack
```

### Check Status

```bash
# View registered agents
gcloud firestore documents list agents

# View active sessions
gcloud firestore documents list sessions

# Check logs
gcloud run logs read slack-vertex-middleware --region us-central1 --limit 50
```

---

## Receiving Images from Slack

The middleware can download images from Slack messages and forward them to your agent. However, **ADK agents are not multimodal by default** - you need to update your agent code to handle images.

### What the Middleware Sends

When a user sends an image via Slack, the middleware adds an `images` field to your agent's input:

```python
{
    "message": "[From: John Smith | SlackID: U0AFZ86NE00] What wine pairs with this?",
    "user_id": "slack-user-abc123",
    "session_id": "5695302693795397632",
    "images": [
        {
            "data": "iVBORw0KGgoAAAANSUhEUgAA...",  # base64-encoded image
            "mime_type": "image/png"
        }
    ]
}
```

### Prerequisites

1. **Add `files:read` scope** to your Slack bot:
   - Go to https://api.slack.com/apps → Your app → OAuth & Permissions
   - Under Bot Token Scopes, add `files:read`
   - Reinstall the app to your workspace

2. **Use a multimodal model** in your agent (e.g., `gemini-2.0-flash` or `gemini-1.5-pro`)

### Updating Your ADK Agent

By default, ADK agents only process the `message` field. To handle images, you need to modify your agent's `stream_query` method to:

1. Extract images from the input
2. Convert base64 data to Gemini `Part` objects
3. Include them in the prompt to the LLM

### Example Implementation

Here's how to update your agent to process images:

```python
import base64
from google.genai import types

class MyAgent:
    def __init__(self):
        # Use a multimodal model
        self.model = "gemini-2.0-flash"
        # ... rest of initialization

    def stream_query(self, *, message: str, user_id: str, session_id: str = None, images: list = None, **kwargs):
        """
        Process a user query, optionally with images.

        Args:
            message: The user's text message
            user_id: User identifier
            session_id: Session identifier for conversation continuity
            images: Optional list of image dicts with 'data' (base64) and 'mime_type'
        """
        # Build the content parts for the prompt
        content_parts = []

        # Add images first (if any)
        if images:
            for img in images:
                image_bytes = base64.b64decode(img["data"])
                content_parts.append(
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=img["mime_type"]
                    )
                )

        # Add the text message
        content_parts.append(types.Part.from_text(message))

        # Create the content object
        user_content = types.Content(
            role="user",
            parts=content_parts
        )

        # Send to the model (adjust based on your agent's architecture)
        # This example assumes you're using the Gemini client directly
        response = self.client.models.generate_content_stream(
            model=self.model,
            contents=[user_content],
            # ... your other config
        )

        for chunk in response:
            yield chunk.text
```

### For ADK Agents Using `LlmAgent`

If you're using `google.adk.agents.LlmAgent`, you'll need to customize how content is built. The simplest approach is to override the query handling:

```python
from google.adk.agents import LlmAgent
from google.genai import types
import base64

class MultimodalAgent(LlmAgent):
    def __init__(self, **kwargs):
        super().__init__(
            model="gemini-2.0-flash",  # Must be multimodal
            **kwargs
        )

    async def _build_user_content(self, message: str, images: list = None) -> types.Content:
        """Build user content with optional images."""
        parts = []

        # Add images first
        if images:
            for img in images:
                image_bytes = base64.b64decode(img["data"])
                parts.append(
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=img["mime_type"]
                    )
                )

        # Add text
        parts.append(types.Part.from_text(message))

        return types.Content(role="user", parts=parts)
```

### Testing Image Support

1. Deploy your updated agent to Vertex AI
2. Update the middleware registration (same Slack bot, new Vertex AI agent ID)
3. Send an image to your bot via Slack DM
4. Check Cloud Run logs for:
   - `"Downloaded image: image/png, XXXXX bytes"` - middleware received image
   - `"Sending 1 image(s) to Reasoning Engine"` - middleware forwarded to your agent

### Troubleshooting

**Agent returns empty response when image is sent:**
- Your agent isn't processing the `images` field - implement the handling above
- Check your model supports vision (use `gemini-2.0-flash` or `gemini-1.5-pro`)

**"I didn't like that request" message:**
- This is the middleware's fallback when the agent returns an empty response
- Usually means the agent doesn't know how to handle the `images` parameter

**Image not appearing in agent input:**
- Verify `files:read` scope is added to your Slack bot
- Check middleware logs for download errors

---

## Building Scheduled Job Tools

Your agent can provide tools that allow users to manage their own scheduled jobs through the middleware API. This enables features like:
- "Remind me every morning at 9 AM to review my goals"
- "Show me my scheduled check-ins"
- "Cancel my daily standup reminder"

### Scheduled Jobs API

The middleware exposes a REST API for managing scheduled jobs. Your agent can call these endpoints using HTTP tools.

**Base URL**: `https://YOUR_MIDDLEWARE_URL/api/v1/scheduled-jobs`

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/scheduled-jobs` | Create a new scheduled job |
| `GET` | `/scheduled-jobs?slack_user_id={user_id}` | List jobs for a user |
| `GET` | `/scheduled-jobs/{job_id}` | Get a specific job |
| `PATCH` | `/scheduled-jobs/{job_id}` | Update a job |
| `DELETE` | `/scheduled-jobs/{job_id}` | Delete a job |

### Data Model

Each scheduled job has the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable name (e.g., "Daily Goal Review") |
| `prompt` | string | The message sent to the agent when the job runs |
| `agent_id` | string | Your agent's Firestore document ID |
| `slack_user_id` | string | The Slack user ID who will receive responses |
| `schedule` | string | Cron expression (e.g., "0 9 * * 1-5" for 9 AM weekdays) |
| `timezone` | string | IANA timezone (e.g., "America/New_York") |
| `enabled` | boolean | Whether the job is active |

### Example: Create Job Tool

Here's an example tool definition for creating scheduled jobs:

```python
from google.adk.tools import FunctionTool

def create_scheduled_reminder(
    name: str,
    prompt: str,
    schedule: str,
    timezone: str = "UTC"
) -> dict:
    """
    Create a scheduled reminder that will message the user on a recurring schedule.

    Args:
        name: A friendly name for this reminder (e.g., "Morning Goals Check-in")
        prompt: The message that will be sent to trigger the conversation
        schedule: Cron expression for when to run (e.g., "0 9 * * 1-5" for 9 AM weekdays)
        timezone: IANA timezone name (e.g., "America/New_York", "Europe/London")

    Returns:
        The created job details including its ID
    """
    import requests

    # These would come from your agent's context/configuration
    middleware_url = "https://your-middleware.run.app"
    agent_id = "your-agent-firestore-id"
    slack_user_id = get_current_slack_user_id()  # From conversation context

    response = requests.post(
        f"{middleware_url}/api/v1/scheduled-jobs",
        json={
            "name": name,
            "prompt": prompt,
            "agent_id": agent_id,
            "slack_user_id": slack_user_id,
            "schedule": schedule,
            "timezone": timezone,
            "enabled": True
        }
    )

    return response.json()

create_reminder_tool = FunctionTool(func=create_scheduled_reminder)
```

### Example: List Jobs Tool

```python
def list_my_scheduled_jobs() -> list:
    """
    List all scheduled jobs for the current user.

    Returns:
        List of scheduled jobs with their details and status
    """
    import requests

    middleware_url = "https://your-middleware.run.app"
    slack_user_id = get_current_slack_user_id()

    response = requests.get(
        f"{middleware_url}/api/v1/scheduled-jobs",
        params={"slack_user_id": slack_user_id}
    )

    return response.json()["jobs"]

list_jobs_tool = FunctionTool(func=list_my_scheduled_jobs)
```

### Example: Delete Job Tool

```python
def delete_scheduled_job(job_id: str) -> dict:
    """
    Delete a scheduled job by its ID.

    Args:
        job_id: The ID of the job to delete (from list_my_scheduled_jobs)

    Returns:
        Confirmation of deletion
    """
    import requests

    middleware_url = "https://your-middleware.run.app"

    response = requests.delete(
        f"{middleware_url}/api/v1/scheduled-jobs/{job_id}"
    )

    return {"success": response.status_code == 204, "job_id": job_id}

delete_job_tool = FunctionTool(func=delete_scheduled_job)
```

### Cron Expression Reference

| Schedule | Cron Expression |
|----------|-----------------|
| Every day at 9 AM | `0 9 * * *` |
| Weekdays at 9 AM | `0 9 * * 1-5` |
| Every Monday at 10 AM | `0 10 * * 1` |
| Every hour | `0 * * * *` |
| Every 30 minutes | `*/30 * * * *` |
| First day of month at noon | `0 12 1 * *` |

Format: `minute hour day-of-month month day-of-week`

### Security Considerations

1. **User Ownership**: Jobs are filtered by `slack_user_id` - users can only see/modify their own jobs
2. **Agent Scope**: Include `agent_id` filter when listing to show only jobs for your agent
3. **Validation**: The API validates cron expressions and timezone values

### Accessing User Context

When a scheduled job executes, the prompt is sent to your agent with the user's identity:

```
[From: John Smith | SlackID: U0AFZ86NE00] What should I focus on today?
```

Your agent can use this to personalize responses or access user-specific data.

---

**Remember**: Save this file in your agent repo so it's always available when working on the agent!
