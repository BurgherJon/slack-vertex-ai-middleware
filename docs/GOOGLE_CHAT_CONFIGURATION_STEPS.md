# Google Chat Bot Configuration - Step by Step

Follow these steps to configure each agent (Growth Coach and Sam the Sommelier) as Google Chat bots.

## Prerequisites

✅ Google Chat API enabled
✅ Service account permissions granted (`roles/chat.owner`)
✅ Service account credentials in Secret Manager
✅ Middleware deployed with Google Chat support

## Configuration Steps

### Step 1: Access Google Chat API Configuration

1. Go to: https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat
2. Select project: **playingwithai-460811**
3. Click **"Configuration"** in the left sidebar

---

## Growth Coach Configuration

### Step 2a: Create Growth Coach Bot

1. Click **"Create Configuration"** (or "Edit Configuration" if one exists)

2. **App name**: `Growth Coach`

3. **Avatar URL**: Upload an image or use a URL for the bot's avatar
   - Recommended: Upload a motivational/coaching themed icon

4. **Description**:
   ```
   Your personal growth and accountability coach. Helps you tackle challenges and overcome obstacles.
   ```

5. **Functionality**:
   - ✅ Enable: **"Receive 1:1 messages"**
   - ✅ Enable: **"Join spaces and group conversations"** (optional)

6. **Connection settings**:
   - **App URL**:
     ```
     https://slack-vertex-middleware-pti6lffniq-uc.a.run.app/api/v1/google-chat/events
     ```
   - **Authentication**: Leave as default (automatically handled by service account)

7. **Visibility**:
   - Select: **"Specific people and groups in your domain"**
   - Add: `jonathancavell@gmail.com`
   - Or select: **"Everyone in your domain"** for wider access

8. **Permissions**:
   - Leave as default

9. Click **"Save"**

10. **Note the Bot Name**: After saving, you'll see a bot resource name like:
    ```
    projects/playingwithai-460811/bots/XXXXXXXXX
    ```
    Copy this for later use.

---

## Sam the Sommelier Configuration

### Step 2b: Create Sam the Sommelier Bot

**Note**: Google Chat requires creating a separate bot configuration per service account. Since we want two distinct bots, we need to create separate configurations.

**Option 1: Using Google Cloud Console UI**
1. Repeat the same steps as Growth Coach with these values:
   - **App name**: `Sam the Sommelier`
   - **Description**:
     ```
     Your wine expert and sommelier. Get personalized wine recommendations and learn about wine.
     ```
   - **Avatar URL**: Upload a wine-themed icon
   - Same webhook URL and visibility settings

**Option 2: Using API** (if UI doesn't support multiple bots)
You may need to create this bot using the Google Chat API or deploy it as a separate Google Cloud project. Check Google Chat documentation for multi-bot support.

---

## Step 3: Update Firestore with Google Chat Configuration

Now that the bots are configured, update each agent's Firestore document.

### Growth Coach (Agent ID: `Lr3zSrzP1ybV9RhiS5Gp`)

1. Open Firebase Console: https://console.firebase.google.com/
2. Select project: **playingwithai-460811**
3. Go to **Firestore Database**
4. Navigate to collection: **agents**
5. Click on document: **Lr3zSrzP1ybV9RhiS5Gp**
6. Click **"Edit Document"** or add a field

7. Add the `platforms` array (if it doesn't exist):
   ```json
   {
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
         "google_chat_service_account_secret": "growth-coach-credentials",
         "google_chat_bot_name": "projects/playingwithai-460811/bots/XXXXXXXXX"
       }
     ]
   }
   ```

8. Replace `XXXXXXXXX` with the actual bot name from Step 2a
9. Click **"Save"**

### Sam the Sommelier (Agent ID: `hynoYrK8SLdiroWvhe1M`)

1. Navigate to document: **hynoYrK8SLdiroWvhe1M**
2. Add/update the `platforms` array:
   ```json
   {
     "platforms": [
       {
         "platform": "slack",
         "enabled": true,
         "slack_bot_id": "U0ALNDQ6EUE",
         "slack_bot_token": "xoxb-..."
       },
       {
         "platform": "google_chat",
         "enabled": true,
         "google_chat_service_account_secret": "sommelier-credentials",
         "google_chat_bot_name": "projects/playingwithai-460811/bots/YYYYYYYYY"
       }
     ]
   }
   ```

3. Replace `YYYYYYYYY` with the actual bot name from Step 2b
4. Click **"Save"**

---

## Step 4: Test Google Chat Bots

### Find and Message the Bot

1. Open Google Chat: https://chat.google.com
2. Click **"New chat"** or use the search bar
3. Search for: **"Growth Coach"** or **"Sam the Sommelier"**
4. Click on the bot to open a DM
5. Send a test message: `Hello`

### Expected Behavior

1. The bot should respond using the Vertex AI agent
2. Response should appear within a few seconds
3. Check Cloud Run logs if no response:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=slack-vertex-middleware AND timestamp>=\$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S)Z" --limit 50 --format json --project playingwithai-460811
   ```

---

## Step 5: Create User Identity Mapping

For cross-platform sessions (same conversation on Slack and Google Chat), create a user document.

1. Open Firestore Database
2. Navigate to collection: **users** (create if doesn't exist)
3. Click **"Add Document"**
4. Set auto-ID or use a custom ID
5. Add fields:
   ```json
   {
     "primary_name": "Jonathan Cavell",
     "email": "jonathancavell@gmail.com",
     "identities": [
       {
         "platform": "slack",
         "platform_user_id": "U0AAB2BEZV5",
         "linked_at": "2026-04-04T16:00:00Z",
         "display_name": "Jonathan"
       },
       {
         "platform": "google_chat",
         "platform_user_id": "users/YOUR_GOOGLE_CHAT_USER_ID",
         "linked_at": "2026-04-04T16:00:00Z",
         "display_name": "Jonathan Cavell"
       }
     ],
     "created_at": "2026-04-04T16:00:00Z",
     "updated_at": "2026-04-04T16:00:00Z"
   }
   ```

6. To get your Google Chat user ID:
   - Send a message to the bot
   - Check Cloud Run logs for the `platform_user_id` in the event
   - Or use: `users/<email>` format if your workspace allows

---

## Troubleshooting

### Bot Not Appearing in Google Chat
- Verify bot is published to your user/domain in Configuration > Visibility
- Check that you're logged in with the correct Google account
- Wait a few minutes for bot directory to update

### Bot Not Responding
1. Check Cloud Run logs for errors:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=slack-vertex-middleware AND severity>=WARNING" --limit 30 --format json --project playingwithai-460811
   ```

2. Verify webhook URL is correct in bot configuration

3. Check service account has `roles/chat.owner`:
   ```bash
   gcloud projects get-iam-policy playingwithai-460811 --flatten="bindings[].members" --filter="bindings.members:serviceAccount:growth-coach-sheets@*"
   ```

4. Verify secret exists and is accessible:
   ```bash
   gcloud secrets versions access latest --secret="growth-coach-credentials" --project playingwithai-460811 | head -5
   ```

### Authentication Errors
- Verify service account credentials in Secret Manager are valid
- Check Cloud Run service account has Secret Manager access
- Verify Google Chat API is enabled

### Cross-Platform Session Not Working
- Verify user document exists in `users` collection
- Check that both platform identities are correctly mapped
- Verify email auto-linking is configured (if used)

---

## Next Steps

After successful configuration:
- [ ] Test cross-platform sessions (message on Slack, then Google Chat)
- [ ] Update scheduled jobs to support Google Chat output
- [ ] Deploy new agent development scripts
- [ ] Update FOR_AGENT_DEVELOPERS.md
