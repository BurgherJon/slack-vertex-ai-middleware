# Google Chat Setup Guide

This guide documents the steps to enable Google Chat for each agent.

## Prerequisites

- Google Cloud Project: `playingwithai-460811`
- Existing service accounts for each agent (used for Google Drive/Sheets access)
- Cloud Run middleware deployed

## Service Accounts

Each agent has its own dedicated service account:

### Growth Coach
- **Service Account**: `growth-coach-sheets@playingwithai-460811.iam.gserviceaccount.com`
- **Display Name**: Growth_Coach_Sheets
- **Key File**: `growth-coach-sa-key.json` (local only, not in git)

### Sam the Sommelier
- **Service Account**: `sommelier-sheets@playingwithai-460811.iam.gserviceaccount.com`
- **Display Name**: Sommelier Sheets
- **Key File**: `sommelier-sa-key.json` (local only, not in git)

## GCP Resources Created

### 1. Enable Google Chat API
```bash
gcloud services enable chat.googleapis.com --project playingwithai-460811
```

### 2. Grant Chat Bot Permissions

Growth Coach:
```bash
gcloud projects add-iam-policy-binding playingwithai-460811 \
  --member="serviceAccount:growth-coach-sheets@playingwithai-460811.iam.gserviceaccount.com" \
  --role="roles/chat.owner"
```

Sam the Sommelier:
```bash
gcloud projects add-iam-policy-binding playingwithai-460811 \
  --member="serviceAccount:sommelier-sheets@playingwithai-460811.iam.gserviceaccount.com" \
  --role="roles/chat.owner"
```

### 3. Verify Service Account Credentials in Secret Manager

Growth Coach:
```bash
gcloud iam service-accounts keys create growth-coach-sa-key.json \
  --iam-account=growth-coach-sheets@playingwithai-460811.iam.gserviceaccount.com \
  --project=playingwithai-460811
```

Sam the Sommelier:
```bash
gcloud iam service-accounts keys create sommelier-sa-key.json \
  --iam-account=sommelier-sheets@playingwithai-460811.iam.gserviceaccount.com \
  --project=playingwithai-460811
```

## Google Chat Bot Configuration

For each agent, you need to configure a Google Chat bot in the Google Cloud Console.

### Steps for Each Bot:

1. **Navigate to Google Chat API**
   - Go to: https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat
   - Select project: `playingwithai-460811`

2. **Configure Bot Settings**
   - Click "Configuration" in the left sidebar
   - Click "Create Configuration" or "Edit Configuration"

3. **Bot Information**
   - **App name**:
     - Growth Coach: "Growth Coach"
     - Sommelier: "Sam the Sommelier"
   - **Avatar URL**: Upload or provide URL for bot avatar
   - **Description**: Brief description of what the bot does

4. **Functionality**
   - Enable: "Receive 1:1 messages"
   - Enable: "Join spaces and group conversations" (optional)

5. **Connection Settings**
   - **App URL**: `https://slack-vertex-middleware-pti6lffniq-uc.a.run.app/api/v1/google-chat/events`
   - **Authentication**: Leave as default (Google will handle with service account)

6. **Visibility**
   - **Make bot available to**:
     - Select "Specific people and groups in your domain"
     - Add: `jonathancavell@gmail.com`
   - Or select "Everyone in your domain" if you want broader access

7. **Save Configuration**

## Firestore Configuration

After creating the Google Chat bots, you need to update Firestore with the service account credentials.

### Agent Document Structure

For each agent document in the `agents` collection, add a `platforms` array with Google Chat configuration:

```json
{
  "id": "Lr3zSrzP1ybV9RhiS5Gp",
  "display_name": "Growth Coach",
  "vertex_ai_agent_id": "projects/playingwithai-460811/locations/us-central1/reasoningEngines/3127398647243735040",
  "slack_bot_token": "xoxb-...",
  "slack_bot_id": "U0AFZ86NE00",
  "platforms": [
    {
      "platform": "slack",
      "enabled": true,
      "slack_bot_id": "U0AFZ86NE00",
      "slack_bot_token": "xoxb-..."
    },
    {
      "platform": "google_chat",
      "enabled": true,
      "google_chat_service_account": {
        "type": "service_account",
        "project_id": "playingwithai-460811",
        "private_key_id": "...",
        "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
        "client_email": "growth-coach-sheets@playingwithai-460811.iam.gserviceaccount.com",
        "client_id": "...",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "..."
      },
      "google_chat_bot_name": "projects/playingwithai-460811/bots/growth-coach"
    }
  ]
}
```

### Updating Firestore

You can update Firestore using:
1. **Firebase Console**: Manually edit the agent document
2. **Script**: Use a Python script to read the JSON key files and update Firestore
3. **Deployment Script**: Add to the agent deployment process

## User Identity Mapping

For cross-platform user identity, create a user document in the `users` collection:

```json
{
  "id": "user_unique_id",
  "primary_name": "Jonathan Cavell",
  "email": "jonathancavell@gmail.com",
  "identities": [
    {
      "platform": "slack",
      "platform_user_id": "U0AAB2BEZV5",
      "linked_at": "2026-04-04T00:00:00Z",
      "display_name": "Jonathan"
    },
    {
      "platform": "google_chat",
      "platform_user_id": "users/1234567890...",
      "linked_at": "2026-04-04T00:00:00Z",
      "display_name": "Jonathan Cavell"
    }
  ]
}
```

## Testing

1. **Find the bot in Google Chat**
   - Open Google Chat (chat.google.com)
   - Click "New chat" or search for the bot name
   - Start a direct message with the bot

2. **Send a test message**
   - Send: "Hello"
   - The bot should respond using the Vertex AI agent

3. **Check logs**
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=slack-vertex-middleware" \
     --limit 50 --format json --project playingwithai-460811
   ```

## Troubleshooting

### Bot not responding
- Check Cloud Run logs for errors
- Verify service account has `roles/chat.owner`
- Verify webhook URL is correct in Google Chat bot configuration
- Check that Google Chat API is enabled

### Authentication errors
- Verify service account JSON is correctly formatted in Firestore
- Check that the service account key is not expired
- Verify the service account has necessary permissions

### Message not reaching middleware
- Check that the webhook URL is publicly accessible
- Verify no firewall rules blocking Google Chat
- Check Cloud Run allows unauthenticated requests for the webhook endpoint

## Security Notes

- **Never commit service account keys to git** (already in `.gitignore`)
- Store service account credentials encrypted in Firestore
- Rotate service account keys periodically
- Use principle of least privilege for service account permissions
- Monitor service account usage in Cloud Console

## Next Steps

After completing Google Chat setup:
1. Test cross-platform sessions (message bot on Slack, then on Google Chat)
2. Test scheduled jobs with Google Chat output
3. Update agent deployment scripts to include Google Chat configuration
4. Document the setup process for new agents
