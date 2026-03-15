# Agent Deployment - Middleware Integration

This guide covers how to integrate your Vertex AI agent with the Slack middleware layer.

⚠️ **IMPORTANT**: Copy this file to your agent repository (e.g., `growth-coach-agent/MIDDLEWARE_INTEGRATION.md`) so you see it when working on the agent!

## Table of Contents

1. [Creating a Brand New Agent](#creating-a-brand-new-agent)
2. [Updating an Existing Agent](#updating-an-existing-agent)
3. [Troubleshooting](#troubleshooting)
4. [Quick Reference](#quick-reference)

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

**Remember**: Save this file in your agent repo so it's always available when working on the agent!
