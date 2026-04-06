# Migration Guide: Personal GCP to Google Workspace Organization

This guide walks you through migrating the Vertex AI middleware infrastructure from a personal GCP project to a Google Workspace organization project. This migration is required to enable Google Chat bot functionality.

## Overview

**Current State**: Running in `playingwithai-460811` (personal GCP project)
**Target State**: Running in Google Workspace organization project
**Duration**: 2-3 days including testing
**Downtime**: None (parallel deployment with cutover)

## Why Migrate?

Google Chat API bots require a **Google Workspace Business** or **Enterprise** account. Personal Gmail accounts cannot create or deploy Google Chat bots via the API.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Google Workspace Business Starter subscription (CavellandCavell.com)
- [ ] Admin access to Google Workspace
- [ ] GCP Project Owner/Editor role
- [ ] Terraform installed (v1.0+)
- [ ] gcloud CLI installed and authenticated
- [ ] Access to current Firestore data
- [ ] List of Google Drive/Sheets files accessed by agents

---

## Phase 1: Pre-Migration Setup (Manual)

### Step 1.1: Create Google Workspace Account

1. Go to [workspace.google.com](https://workspace.google.com)
2. Sign up for **Business Starter** plan (~$6-7/month per user)
3. Use domain: **CavellandCavell.com**
4. Complete setup wizard
5. Verify domain ownership

**Estimated Time**: 30 minutes

### Step 1.2: Create GCP Project in Workspace Organization

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click project dropdown → **New Project**
3. **Project Name**: `vertex-ai-middleware-prod` (or your choice)
4. **Organization**: Select CavellandCavell.com organization
5. Click **Create**
6. Note the **Project ID** (e.g., `vertex-ai-middleware-prod-123456`)

**Estimated Time**: 5 minutes

### Step 1.3: Export Firestore Data

Export all data from the current project:

```bash
# Set old project
export OLD_PROJECT="playingwithai-460811"
gcloud config set project $OLD_PROJECT

# Create backup bucket (if doesn't exist)
gsutil mb -l us-central1 gs://${OLD_PROJECT}-backup

# Export Firestore
gcloud firestore export gs://${OLD_PROJECT}-backup/firestore-migration-$(date +%Y%m%d) \
  --project=$OLD_PROJECT

# Note the export path for later import
```

**Estimated Time**: 5-10 minutes

### Step 1.4: Document Current Configuration

Create an inventory file:

```bash
# Get current Vertex AI agent IDs from Firestore
# Document which Google Drive files/sheets are accessed
# Note current Slack app configurations
# Save current secret values
```

Create a file `migration-inventory.md`:

```markdown
## Current Configuration (playingwithai-460811)

### Vertex AI Agents
- Growth Coach: projects/playingwithai-460811/locations/us-central1/reasoningEngines/[ID]
- Sam the Sommelier: projects/playingwithai-460811/locations/us-central1/reasoningEngines/[ID]

### Service Accounts
- growth-coach-sheets@playingwithai-460811.iam.gserviceaccount.com
- sommelier-sheets@playingwithai-460811.iam.gserviceaccount.com

### Google Drive Files Accessed
- [List all sheets/files]

### Slack Apps
- Workspace: [workspace-name]
- App IDs: [list]
- Current webhook: https://slack-vertex-middleware-XXX.run.app/api/v1/slack/events

### GCS Bucket
- playingwithai-460811-slack-files
```

**Estimated Time**: 15 minutes

---

## Phase 2: Terraform Infrastructure Deployment

### Step 2.1: Configure Terraform

```bash
# Set new project
export NEW_PROJECT="your-new-project-id"
gcloud config set project $NEW_PROJECT

# Authenticate
gcloud auth application-default login

# Navigate to terraform directory
cd terraform

# Copy and edit variables
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
project_id  = "your-new-project-id"
region      = "us-central1"
environment = "prod"
```

**Estimated Time**: 5 minutes

### Step 2.2: Create Firestore Database

Terraform cannot create Firestore databases, so do it manually:

```bash
gcloud firestore databases create \
  --location=us-central1 \
  --type=firestore-native \
  --project=$NEW_PROJECT
```

**Estimated Time**: 2 minutes

### Step 2.3: Initialize and Apply Terraform

```bash
# Initialize
terraform init

# Review plan
terraform plan

# Review the output carefully - verify:
# - Project ID is correct
# - All required APIs will be enabled
# - Service accounts will be created
# - GCS bucket name is correct

# Apply infrastructure
terraform apply

# Type 'yes' when prompted
```

**Estimated Time**: 10-15 minutes

### Step 2.4: Save Terraform Outputs

```bash
# Save all outputs
terraform output -json > ../migration-outputs.json

# View key outputs
terraform output cloud_run_url
terraform output growth_coach_service_account_email
terraform output sommelier_service_account_email
```

**Estimated Time**: 1 minute

---

## Phase 3: Populate Secrets

### Step 3.1: Generate Service Account Keys

```bash
# Growth Coach
gcloud iam service-accounts keys create growth-coach-sa-key.json \
  --iam-account=$(terraform output -raw growth_coach_service_account_email) \
  --project=$NEW_PROJECT

# Sommelier
gcloud iam service-accounts keys create sommelier-sa-key.json \
  --iam-account=$(terraform output -raw sommelier_service_account_email) \
  --project=$NEW_PROJECT
```

**Estimated Time**: 1 minute

### Step 3.2: Store Keys in Secret Manager

```bash
# Growth Coach credentials
gcloud secrets versions add growth-coach-credentials \
  --data-file=growth-coach-sa-key.json \
  --project=$NEW_PROJECT

# Sommelier credentials
gcloud secrets versions add sommelier-credentials \
  --data-file=sommelier-sa-key.json \
  --project=$NEW_PROJECT

# Delete local key files immediately
rm -f growth-coach-sa-key.json sommelier-sa-key.json
```

**Estimated Time**: 2 minutes

### Step 3.3: Copy Slack Signing Secret

```bash
# Get secret from old project
OLD_SECRET=$(gcloud secrets versions access latest \
  --secret=slack-signing-secret \
  --project=$OLD_PROJECT)

# Store in new project
echo -n "$OLD_SECRET" | gcloud secrets versions add slack-signing-secret \
  --data-file=- \
  --project=$NEW_PROJECT
```

**Estimated Time**: 1 minute

---

## Phase 4: Redeploy Vertex AI Agents

### Step 4.1: Update Agent Deployment Configuration

Your agent deployment scripts should already be configured to use environment variables. Update them:

```bash
# Set new project
export GCP_PROJECT_ID=$NEW_PROJECT
export GCP_LOCATION="us-central1"
```

### Step 4.2: Redeploy Each Agent

Follow your existing agent deployment process for each agent:

```bash
# Example (adjust based on your actual deployment scripts)
python scripts/deploy_agent.py --agent growth-coach --project $NEW_PROJECT
python scripts/deploy_agent.py --agent sommelier --project $NEW_PROJECT
```

### Step 4.3: Capture New Agent IDs

Save the new Vertex AI agent resource names:

```bash
# Format: projects/NEW_PROJECT/locations/us-central1/reasoningEngines/[NEW_ID]
# Save these for Firestore updates
```

**Estimated Time**: 1-2 hours (depending on agent complexity)

---

## Phase 5: Deploy Middleware

### Step 5.1: Deploy Cloud Run Service

```bash
# Navigate to project root
cd ..

# Deploy using Cloud Build
gcloud builds submit \
  --config cloudbuild.yaml \
  --project=$NEW_PROJECT \
  --substitutions=_GCP_PROJECT_ID=$NEW_PROJECT,_GCP_LOCATION=us-central1

# Wait for deployment to complete
# Note the new Cloud Run URL
```

**Estimated Time**: 5-10 minutes

### Step 5.2: Verify Deployment

```bash
# Get Cloud Run URL
NEW_CLOUD_RUN_URL=$(gcloud run services describe slack-vertex-middleware \
  --region=us-central1 \
  --project=$NEW_PROJECT \
  --format='value(status.url)')

echo "New Cloud Run URL: $NEW_CLOUD_RUN_URL"

# Test health endpoint
curl $NEW_CLOUD_RUN_URL/health
```

**Estimated Time**: 2 minutes

---

## Phase 6: Migrate Firestore Data

### Step 6.1: Import Firestore Backup

```bash
# Find your export path from Step 1.3
export EXPORT_PATH="gs://playingwithai-460811-backup/firestore-migration-20260406"

# Import to new project
gcloud firestore import $EXPORT_PATH \
  --project=$NEW_PROJECT
```

**Estimated Time**: 5-10 minutes

### Step 6.2: Update Agent Documents

You need to update each agent document with new values. Create a script or update manually via Firebase Console:

**Growth Coach (`Lr3zSrzP1ybV9RhiS5Gp`):**
```json
{
  "vertex_ai_agent_id": "projects/NEW_PROJECT/locations/us-central1/reasoningEngines/NEW_ID",
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
      "google_chat_bot_name": "projects/NEW_PROJECT/bots/TBD"
    }
  ]
}
```

**Sam the Sommelier (`hynoYrK8SLdiroWvhe1M`):**
```json
{
  "vertex_ai_agent_id": "projects/NEW_PROJECT/locations/us-central1/reasoningEngines/NEW_ID",
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
      "google_chat_bot_name": "projects/NEW_PROJECT/bots/TBD"
    }
  ]
}
```

**Estimated Time**: 15 minutes

---

## Phase 7: Share Google Drive Files

### Step 7.1: Get New Service Account Emails

```bash
echo "Growth Coach: $(terraform output -raw growth_coach_service_account_email)"
echo "Sommelier: $(terraform output -raw sommelier_service_account_email)"
```

### Step 7.2: Share Files

For each Google Sheet/Drive file accessed by the agents:

1. Open the file in Google Drive
2. Click **Share**
3. Add both service account emails:
   - `growth-coach-sheets@NEW_PROJECT.iam.gserviceaccount.com`
   - `sommelier-sheets@NEW_PROJECT.iam.gserviceaccount.com`
4. Grant **Editor** access (if they need to write)
5. Click **Send** (uncheck "Notify people")

**Important**: Files remain in your personal Google Drive - no migration needed!

**Estimated Time**: 10-15 minutes (depending on number of files)

---

## Phase 8: Update Slack Integrations

### Step 8.1: Update Webhook URLs

For each Slack app:

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Select your app
3. Go to **Event Subscriptions**
4. Update **Request URL** to:
   ```
   https://NEW_CLOUD_RUN_URL/api/v1/slack/events
   ```
5. Click **Save Changes**
6. Verify the URL (should show green checkmark)

Repeat for each Slack bot (Growth Coach, Sam the Sommelier).

**Estimated Time**: 10 minutes

---

## Phase 9: Configure Google Chat Bots

### Step 9.1: Create Google Chat Bot Configurations

In the new Workspace project:

1. Go to: https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat
2. Select project: `NEW_PROJECT`
3. Click **Configuration** → **Create Configuration**

**Growth Coach Bot:**
- **App name**: `Growth Coach`
- **Avatar URL**: Upload coaching icon
- **Description**: `Your personal growth and accountability coach`
- **Functionality**:
  - ✅ Receive 1:1 messages
  - ✅ Join spaces and group conversations
- **App URL**: `https://NEW_CLOUD_RUN_URL/api/v1/google-chat/events`
- **Visibility**: Specific people → Add `jonathancavell@gmail.com`
- Click **Save**
- **Note the bot name**: `projects/NEW_PROJECT/bots/[BOT_ID]`

**Sam the Sommelier Bot:**
- **App name**: `Sam the Sommelier`
- **Avatar URL**: Upload wine icon
- **Description**: `Your wine expert and sommelier`
- Same settings as above
- **Note the bot name**: `projects/NEW_PROJECT/bots/[BOT_ID]`

**Estimated Time**: 15 minutes

### Step 9.2: Update Firestore with Bot Names

Update each agent document's Google Chat platform configuration:

```json
{
  "platform": "google_chat",
  "enabled": true,
  "google_chat_service_account_secret": "growth-coach-credentials",
  "google_chat_bot_name": "projects/NEW_PROJECT/bots/ACTUAL_BOT_ID"
}
```

**Estimated Time**: 5 minutes

### Step 9.3: Create User Identity Mapping

Create a document in Firestore `users` collection:

```json
{
  "primary_name": "Jonathan Cavell",
  "email": "jonathancavell@gmail.com",
  "identities": [
    {
      "platform": "slack",
      "platform_user_id": "U0AAB2BEZV5",
      "linked_at": "2026-04-06T00:00:00Z",
      "display_name": "Jonathan"
    },
    {
      "platform": "google_chat",
      "platform_user_id": "users/YOUR_GOOGLE_CHAT_ID",
      "linked_at": "2026-04-06T00:00:00Z",
      "display_name": "Jonathan Cavell"
    }
  ],
  "created_at": "2026-04-06T00:00:00Z",
  "updated_at": "2026-04-06T00:00:00Z"
}
```

To get your Google Chat user ID: Send a test message to one of the bots and check the Cloud Run logs.

**Estimated Time**: 10 minutes

---

## Phase 10: Testing & Validation

Use this checklist to verify everything works:

```bash
# Monitor logs in real-time
gcloud run logs tail slack-vertex-middleware \
  --region=us-central1 \
  --project=$NEW_PROJECT
```

### Test Checklist

- [ ] **Slack - Growth Coach DM**: Send "Hello", verify response
- [ ] **Slack - Sam the Sommelier DM**: Send "Hello", verify response
- [ ] **Slack - Image Upload**: Send image, verify GCS upload
- [ ] **Google Chat - Growth Coach DM**: Send "Hello", verify response
- [ ] **Google Chat - Sam the Sommelier DM**: Send "Hello", verify response
- [ ] **Scheduled Jobs**: Wait for next minute, verify job executes
- [ ] **Cross-Platform Session**: Message on Slack, continue on Google Chat
- [ ] **Google Sheets Access**: Verify agents can read/write sheets

### Validation Commands

```bash
# Check Cloud Run is healthy
curl $(terraform output -raw cloud_run_url)/health

# Check Firestore collections
gcloud firestore collections list --project=$NEW_PROJECT

# Verify service accounts
gcloud iam service-accounts list --project=$NEW_PROJECT

# Check Secret Manager secrets
gcloud secrets list --project=$NEW_PROJECT
```

**Estimated Time**: 30-60 minutes

---

## Phase 11: Decommission Old Infrastructure

**IMPORTANT**: Only proceed after running the new system for 1-2 weeks without issues!

### Week 1: Monitor

- Monitor new system for errors
- Keep old project running as fallback
- Verify all scheduled jobs execute correctly

### Week 2-3: Disable Old Scheduler

```bash
gcloud config set project $OLD_PROJECT

# Pause Cloud Scheduler
gcloud scheduler jobs pause scheduled-jobs-dispatcher \
  --location=us-central1
```

### Week 3-4: Stop Old Cloud Run

```bash
# Delete Cloud Run service
gcloud run services delete slack-vertex-middleware \
  --region=us-central1 \
  --project=$OLD_PROJECT
```

### After 4 Weeks: Delete Old Project

```bash
# Final backup
gcloud firestore export gs://${OLD_PROJECT}-backup/final-backup-$(date +%Y%m%d) \
  --project=$OLD_PROJECT

# Delete project (cannot be undone after 30 days!)
gcloud projects delete $OLD_PROJECT
```

**Estimated Time**: 4 weeks monitoring period

---

## Rollback Plan

If you need to rollback to the old system:

1. **Slack**: Change webhook URLs back to old Cloud Run URL
2. **Google Chat**: Disable bots in new project
3. **Cloud Run**: Old service should still be running
4. **Data**: Firestore changes are in new project only

---

## Cost Comparison

### Old Project (Personal GCP)
- Cloud Run: ~$10-20/month
- Firestore: ~$5/month
- GCS: ~$1/month
- Vertex AI: Pay per query
- **Total**: ~$15-30/month

### New Project (Workspace + GCP)
- Google Workspace: $6/month per user
- GCP costs: Same as above
- **Total**: ~$20-35/month

**Additional Cost**: $6/month for Google Workspace (enables Google Chat bots)

---

## Support and Troubleshooting

### Common Issues

**Issue**: Terraform API enablement errors
**Solution**: Wait 2-3 minutes for APIs to propagate, then run `terraform apply` again

**Issue**: Cloud Run deployment fails
**Solution**: Check that all secrets have values, verify service account permissions

**Issue**: Agents can't access Google Sheets
**Solution**: Verify sheets are shared with new service account emails

**Issue**: Google Chat bot not appearing
**Solution**: Check bot visibility settings, ensure added to your domain/user

### Getting Help

- Check Cloud Run logs: `gcloud run logs read slack-vertex-middleware --region=us-central1 --project=$NEW_PROJECT`
- Review Terraform state: `terraform show`
- Check service account permissions: `gcloud projects get-iam-policy $NEW_PROJECT`

---

## Next Steps After Migration

1. Update agent deployment scripts with new project ID
2. Update `FOR_AGENT_DEVELOPERS.md` with new workflow
3. Create runbooks for common operations
4. Setup monitoring and alerting
5. Document the new architecture

---

## Summary

**Total Estimated Time**: 6-8 hours of active work + 2-4 weeks monitoring

**Phases**:
1. Pre-Migration Setup: 1 hour
2. Terraform Deployment: 30 minutes
3. Populate Secrets: 5 minutes
4. Redeploy Agents: 1-2 hours
5. Deploy Middleware: 15 minutes
6. Migrate Data: 30 minutes
7. Share Google Drive: 15 minutes
8. Update Slack: 10 minutes
9. Configure Google Chat: 30 minutes
10. Testing: 1 hour
11. Decommission: 4 weeks monitoring

**Key Benefits**:
- Google Chat bot support
- Infrastructure-as-Code (reproducible)
- Professional Workspace setup
- No Google Drive file migration needed
