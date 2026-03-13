# Troubleshooting Guide

Common issues and solutions for the Slack to Vertex AI middleware.

## Table of Contents

- [Slack Integration Issues](#slack-integration-issues)
- [Vertex AI Issues](#vertex-ai-issues)
- [Firestore Issues](#firestore-issues)
- [Local Development Issues](#local-development-issues)
- [Production Deployment Issues](#production-deployment-issues)

---

## Slack Integration Issues

### Messages appear separately instead of as a conversation thread

**Symptoms**: Each message exchange appears as a separate item. Messages show in "History" but the Chat view only shows the most recent message instead of a continuous conversation.

**Root Cause**: Your Slack app is configured as an "Agent or Assistant" in Slack's Agents & AI Apps settings.

**Solution**:
1. Go to https://api.slack.com/apps → Your app
2. Navigate to **"Agents & AI Apps"** in the left sidebar
3. **Disable** the "Agent or Assistant" configuration
4. Your DMs should now show as a normal conversation thread

**Why this happens**: Slack's "Agent or Assistant" mode is designed for one-off query assistants (like search bots) where each interaction is independent. It intentionally shows each exchange separately. For conversational bots that maintain context across messages, you should NOT use this mode.

---

### Bot doesn't respond to messages

**Symptoms**: Send a DM to bot, no response

**Checks**:

1. **Verify agent is registered in Firestore**:
   ```bash
   gcloud firestore documents list agents
   ```
   Ensure there's a document with your `slack_bot_id`

2. **Check Slack Events API is configured**:
   - Go to https://api.slack.com/apps → Your app → Event Subscriptions
   - Verify Request URL shows green checkmark ✓
   - Verify `message.im` is subscribed under "Subscribe to bot events"

3. **Check middleware logs**:
   ```bash
   # Local:
   # Watch terminal running uvicorn

   # Production:
   gcloud run logs read slack-vertex-middleware \
     --region us-central1 \
     --limit 50
   ```

4. **Verify bot token is valid**:
   ```bash
   # Test with Slack API
   curl https://slack.com/api/auth.test \
     -H "Authorization: Bearer xoxb-your-token"
   ```

### "URL verification failed" when configuring Events API

**Symptoms**: Slack shows error when setting Request URL

**Solutions**:

1. **Ensure middleware is running**:
   ```bash
   # Local: Check uvicorn is running
   # Production: Check Cloud Run service is deployed

   # Test health endpoint
   curl https://YOUR_URL/health
   ```

2. **Check signing secret**:
   - Verify `.env` has correct `SLACK_SIGNING_SECRET`
   - Must match: https://api.slack.com/apps → Your app → Basic Information

3. **For ngrok**: Ensure tunnel is active
   ```bash
   # Check ngrok status
   curl http://localhost:4040/api/tunnels
   ```

### Bot responds multiple times to a single message

**Symptoms**: Sending one message to the bot produces 2-3 identical (or similar) responses. Google Cloud logs show multiple separate Vertex AI sessions being created for the same message.

**Root Cause**: Slack retries event delivery if the webhook doesn't respond quickly enough (within ~3 seconds). Each retry is processed as a new event, creating a new Vertex AI session and sending another response.

**Solution**: The middleware handles this by checking for the `X-Slack-Retry-Num` header and immediately acknowledging retries without reprocessing. If you're seeing this issue, ensure your deployed version includes this retry handling in `app/api/v1/slack_events.py`.

**How to verify**: Check Cloud Run logs for entries like:
```
Acknowledging Slack retry #1 (reason: http_timeout)
```
If you don't see these log lines, your deployed version may be outdated. Redeploy the middleware.

---

### "Invalid signature" errors in logs

**Symptoms**: Middleware rejects Slack requests with 401

**Solutions**:

1. **Verify signing secret matches**:
   ```bash
   grep SLACK_SIGNING_SECRET .env
   ```
   Compare with Slack app settings

2. **Check system time** (for replay attack prevention):
   ```bash
   date
   # Should be accurate (use NTP)
   ```

3. **Restart middleware** after changing signing secret

---

## Vertex AI Issues

### "Agent not found" errors

**Symptoms**: Logs show agent not found when processing messages

**Solutions**:

1. **Check agent ID format** (most common issue):
   - For Reasoning Engines: `projects/PROJECT/locations/LOCATION/reasoningEngines/ENGINE_ID`
   - For legacy agents: `projects/PROJECT/locations/LOCATION/agents/AGENT_ID`
   - Must be full resource name, not just the ID

2. **Verify Reasoning Engine exists**:
   ```bash
   # The gcloud ai agents command is for legacy agents
   # For Reasoning Engines, check via Python or Vertex AI Console
   ```

3. **Verify permissions**:
   ```bash
   gcloud projects get-iam-policy PROJECT_ID
   # Should have aiplatform.reasoningEngines.* permissions
   ```

### Empty or no response from agent

**Symptoms**: Bot responds but message is empty or generic error

**Solutions**:

1. **Test agent directly** in Vertex AI Console
   - Verify agent works independently

2. **Check agent deployment status**:
   ```bash
   gcloud ai agents describe AGENT_ID --location=us-central1
   ```

3. **Review Vertex AI quota**:
   - Check quotas in GCP Console
   - Vertex AI may be rate-limited

### Session creation fails

**Symptoms**: Errors creating Vertex AI sessions

**Solutions**:

1. **Check Vertex AI API is enabled**:
   ```bash
   gcloud services list --enabled | grep aiplatform
   ```

2. **Verify service account permissions**:
   - Cloud Run service account needs `aiplatform.sessions.create`

3. **Check project/location configuration**:
   ```bash
   grep GCP_ .env
   ```

---

## Firestore Issues

### "Permission denied" errors

**Symptoms**: Can't read/write Firestore

**Solutions**:

1. **Enable Firestore API**:
   ```bash
   gcloud services enable firestore.googleapis.com
   ```

2. **Check authentication**:
   ```bash
   # Local:
   gcloud auth application-default login

   # Production: Verify service account has roles:
   # - roles/datastore.user (or roles/owner)
   ```

3. **Verify database exists**:
   ```bash
   gcloud firestore databases list
   ```

### "Database not found" or setup_firestore.py fails

**Symptoms**: Running setup_firestore.py fails with database errors

**Root Cause**: Firestore database must be created BEFORE running the setup script.

**Solution**:
```bash
# 1. First authenticate
gcloud auth application-default login

# 2. Create the database (must be done once per project)
gcloud firestore databases create \
  --location=us-central1 \
  --type=firestore-native

# 3. Then run the setup script
python scripts/setup_firestore.py --project-id YOUR_PROJECT_ID
```

### Agent not found in Firestore

**Symptoms**: `get_agent_by_bot_id` returns None, logs show "No agent found for bot_id: U..."

**Root Cause**: Using wrong ID format. Slack Events API sends `user_id` (U...) in authorizations, NOT `bot_id` (B...).

**Solutions**:

1. **Get the correct user_id** (this is the most common issue):
   ```bash
   # Get the user_id that Slack will send in events
   curl -s https://slack.com/api/auth.test \
     -H "Authorization: Bearer xoxb-your-token" | jq .user_id
   # Output: "U0AFZ86NE00" - use THIS, not the B... from Slack settings
   ```

2. **Verify agent document exists with correct ID**:
   ```bash
   gcloud firestore documents list --collection=agents
   # Check that slack_bot_id field has the U... ID
   ```

3. **Re-run deploy_agent.py with correct user_id**:
   ```bash
   python scripts/deploy_agent.py \
     --agent-name "..." \
     --vertex-ai-agent-id "..." \
     --slack-bot-id "U0AFZ86NE00" \
     --slack-bot-token "..."
   ```

**Why this happens**: The Slack app settings show a "Bot User ID" starting with `B`, but the Events API sends the `user_id` starting with `U` in the `authorizations` field. The middleware looks up agents using this `user_id`.

### Sessions not being created

**Symptoms**: New sessions don't appear in Firestore

**Solutions**:

1. **Check Firestore write permissions**
2. **Verify sessions collection exists**:
   ```bash
   gcloud firestore collections list
   ```

3. **Check logs for errors**:
   ```bash
   gcloud run logs read slack-vertex-middleware \
     --region us-central1 \
     --format json | grep session
   ```

---

## Local Development Issues

### ngrok tunnel not working

**Symptoms**: Can't access localhost via ngrok URL

**Solutions**:

1. **Verify ngrok is installed and authenticated**:
   ```bash
   ngrok version
   ngrok config check
   ```

2. **Check tunnel is active**:
   ```bash
   curl http://localhost:4040/api/tunnels
   ```

3. **Restart ngrok**:
   ```bash
   ngrok http 8080
   ```

4. **For Linux VM**: Ensure VM can make outbound connections

### Firestore emulator not connecting

**Symptoms**: Local dev can't connect to Firestore emulator

**Solutions**:

1. **Start emulator**:
   ```bash
   gcloud emulators firestore start --host-port=0.0.0.0:8681
   ```

2. **Set environment variable**:
   ```bash
   export FIRESTORE_EMULATOR_HOST=localhost:8681
   ```

3. **Verify emulator is running**:
   ```bash
   curl http://localhost:8681
   ```

### Module import errors

**Symptoms**: `ModuleNotFoundError` when running app

**Solutions**:

1. **Activate virtual environment**:
   ```bash
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify Python version**:
   ```bash
   python --version  # Should be 3.11 or 3.12
   ```

### "ModuleNotFoundError: No module named 'aiohttp'"

**Symptoms**: Error when running the app, Slack async client fails

**Solution**: Install aiohttp (should be in requirements.txt):
```bash
pip install aiohttp
```

### pip install takes forever or hangs

**Symptoms**: `pip install -r requirements.txt` runs for many minutes with "Resolving dependencies" messages

**Cause**: The google-cloud-aiplatform package has complex dependencies that pip needs to resolve.

**Solutions**:

1. **Use pinned versions** (already in requirements.txt):
   ```bash
   pip install -r requirements.txt
   ```

2. **If still slow, try upgrading pip**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Clear pip cache if having issues**:
   ```bash
   pip cache purge
   pip install -r requirements.txt
   ```

---

## Production Deployment Issues

### Cloud Run deployment fails

**Symptoms**: `gcloud run deploy` fails

**Solutions**:

1. **Check Cloud Run API is enabled**:
   ```bash
   gcloud services enable run.googleapis.com
   ```

2. **Verify Docker builds**:
   ```bash
   docker build -t test .
   ```

3. **Check build logs**:
   ```bash
   gcloud builds list --limit 5
   gcloud builds log BUILD_ID
   ```

### Service crashes on startup

**Symptoms**: Cloud Run service won't start

**Solutions**:

1. **Check environment variables**:
   ```bash
   gcloud run services describe slack-vertex-middleware \
     --region us-central1 \
     --format yaml
   ```

2. **Verify secrets are set**:
   ```bash
   gcloud secrets list
   gcloud secrets versions list slack-signing-secret
   ```

3. **Review startup logs**:
   ```bash
   gcloud run logs read slack-vertex-middleware \
     --region us-central1 \
     --limit 100
   ```

### Secrets not accessible

**Symptoms**: Cloud Run can't access Secret Manager secrets

**Solutions**:

1. **Grant permissions**:
   ```bash
   PROJECT_NUMBER=$(gcloud projects describe PROJECT_ID --format="value(projectNumber)")

   gcloud secrets add-iam-policy-binding slack-signing-secret \
     --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

2. **Verify secret exists**:
   ```bash
   gcloud secrets describe slack-signing-secret
   ```

3. **Redeploy after fixing permissions**

---

## Getting Help

If you've tried the above and still have issues:

1. **Check full logs**:
   ```bash
   gcloud run logs read slack-vertex-middleware \
     --region us-central1 \
     --format json \
     --limit 100 > logs.json
   ```

2. **Verify all components**:
   - Slack app configured correctly
   - Vertex AI agent deployed and working
   - Firestore has correct agent documents
   - Cloud Run service running

3. **Test components individually**:
   - Test Slack Events API with simple endpoint
   - Test Vertex AI agent in Console
   - Test Firestore access with gcloud

4. **Open GitHub issue** with:
   - Error messages
   - Relevant log snippets
   - Steps to reproduce
