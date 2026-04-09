# Agent Infrastructure - Terraform Template

This Terraform template creates dedicated GCP infrastructure for agents that require it.

## Do You Need This?

**Use this template if your agent:**
- ✅ Uses Google Chat (REQUIRED - Google Chat API restriction)
- ✅ Needs dedicated service account for Google APIs (Drive, Sheets, etc.)
- ✅ Requires organizational separation from middleware

**Skip this template if your agent:**
- ❌ Only uses Slack (no dedicated infrastructure needed)
- ❌ Doesn't access Google APIs

## What This Creates

For agents that need dedicated infrastructure, this creates:
- New GCP project (required for Google Chat bots)
- Service account with appropriate permissions
- Required API enablements (Chat, Drive, Sheets, etc.)
- Organization policy override for service account key creation

## What This Creates

- New GCP project
- Required APIs enabled (customizable per agent)
- Service account for the agent with necessary permissions
- Organization policy override to allow service account key creation
- Outputs with next steps for configuration

## Slack-Only Agents

If your agent **only uses Slack** and doesn't need Google APIs:

**You don't need this template!** Simply:
1. Create your Slack bot in the Slack UI
2. Store the bot token in the middleware's Secret Manager
3. Register your agent with the middleware using `scripts/deploy_agent.py`

No dedicated GCP infrastructure required.

## Prerequisites

For agents that DO need dedicated infrastructure:

- GCP organization ID (Google Chat bots require a Workspace organization)
- Billing account ID
- Terraform 1.0+
- `gcloud` CLI authenticated

## Usage

### 1. Copy Template to Your Agent Repository

```bash
# In your agent repository
mkdir -p terraform
cp -r /path/to/middleware/docs/terraform-templates/agent-project/* terraform/
cd terraform
```

### 2. Configure Variables

```bash
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars
```

Fill in your values:
- `project_id`: Globally unique ID for the new project
- `organization_id`: Your GCP organization ID
- `billing_account`: Your billing account ID
- `agent_name`: Display name for your agent
- `agent_account_id`: Service account name (lowercase, hyphens)
- `secret_name`: Name for Secret Manager secret in middleware project

### 3. Deploy

```bash
terraform init
terraform plan
terraform apply
```

### 4. Follow Next Steps

After `terraform apply` completes, follow the "next_steps" output instructions:

#### 4a. Create Service Account Key (for Google Chat)

```bash
# Get the service account email from terraform output
export CHAT_SA_EMAIL=$(terraform output -raw chat_service_account_email)
export PROJECT_ID=$(terraform output -raw project_id)

# Create the key
gcloud iam service-accounts keys create ${PROJECT_ID}-sa-key.json \
  --iam-account=$CHAT_SA_EMAIL \
  --project=$PROJECT_ID
```

#### 4b. Store Key in Secret Manager

**IMPORTANT**: Store the key in **your agent's project** (not the middleware project):

```bash
# Store in YOUR agent's project's Secret Manager
gcloud secrets versions add your-agent-credentials \
  --data-file=${PROJECT_ID}-sa-key.json \
  --project=$PROJECT_ID

# Securely delete the key file
rm -f ${PROJECT_ID}-sa-key.json
```

#### 4c. Store Slack Token (if using Slack)

If your agent uses Slack, store the token in your agent's project:

```bash
# Get your Slack bot token from https://api.slack.com/apps
echo -n "xoxb-YOUR-SLACK-BOT-TOKEN" | gcloud secrets versions add your-agent-slack-token \
  --data-file=- \
  --project=$PROJECT_ID
```

#### 4d. Grant Middleware Access to Secrets

**CRITICAL STEP**: The middleware needs permission to read secrets from your agent's project. Without this, all messages will fail with `403 Permission Denied` errors.

```bash
# Set up variables
export MIDDLEWARE_PROJECT_ID="vertex-ai-middleware-prod"
export MIDDLEWARE_PROJECT_NUMBER=$(gcloud projects describe $MIDDLEWARE_PROJECT_ID --format="value(projectNumber)")
export MIDDLEWARE_SA="${MIDDLEWARE_PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant access to Google Chat credentials
gcloud secrets add-iam-policy-binding your-agent-credentials \
  --member="serviceAccount:${MIDDLEWARE_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID

# Grant access to Slack token (if using Slack)
gcloud secrets add-iam-policy-binding your-agent-slack-token \
  --member="serviceAccount:${MIDDLEWARE_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID
```

**What this does**: Allows the middleware's Cloud Run service account to read your bot credentials so it can authenticate API calls to Google Chat and/or Slack.

#### 4e. Configure Platform Settings

- For Google Chat: Configure the bot in Google Cloud Console
- For Slack: Configure the bot in Slack UI

#### 4f. Enable Platform in Firestore

Use the middleware scripts to register your agent and enable platforms:

```bash
cd /path/to/slack-vertex-ai-middleware

# Register the agent
python scripts/deploy_agent.py \
  --agent-name "Your Agent Name" \
  --vertex-ai-agent-id "projects/YOUR_PROJECT/locations/us-central1/reasoningEngines/YOUR_ENGINE_ID"

# Enable Google Chat (if using)
python scripts/enable_google_chat_agent.py \
  --project vertex-ai-middleware-prod \
  --agent-id "YOUR_AGENT_FIRESTORE_ID" \
  --secret-name "your-agent-credentials" \
  --google-chat-project-id "$PROJECT_ID"

# Enable Slack (if using)
python scripts/enable_slack_agent.py \
  --project vertex-ai-middleware-prod \
  --agent-id "YOUR_AGENT_FIRESTORE_ID" \
  --secret-name "your-agent-slack-token" \
  --slack-project-id "$PROJECT_ID"
```

#### 4g. Test the Agent

Send a test message through your configured platform(s).

## Important Notes

### Two Service Accounts

This setup typically creates **two separate service accounts**:

1. **`your-agent-apis@...`** (Google APIs SA)
   - Used by your agent's Reasoning Engine to access Google Drive, Sheets, etc.
   - **Share your Google Sheets/Drive files with this SA**
   - No key needed (Vertex AI uses Workload Identity)

2. **`your-agent@...`** (Platform bot SA)
   - Used by the middleware to send messages to Google Chat
   - Key stored in Secret Manager for middleware to use
   - **Do NOT share Sheets with this SA**

### Secret Location

Secrets are stored in **your agent's project**, not the middleware project. The middleware service account is granted `secretAccessor` permission to read them.

This approach:
- ✅ Better separation of concerns
- ✅ Easier to manage agent-specific credentials
- ✅ Cleaner project organization

### Common Issues

**"403 Permission Denied" when testing**: This is the most common error. You forgot step 4d (granting middleware access to secrets). Go back and run those commands.

**Messages not reaching agent**: Check the middleware logs:
```bash
gcloud run services logs read slack-vertex-middleware --project=vertex-ai-middleware-prod --region=us-central1 --limit=50
```

### Security & Cleanup

- **Security**: The service account key is sensitive. Delete it after storing in Secret Manager.
- **Organization Policy**: This template overrides the key creation policy for this project only.
- **Cleanup**: If you delete this project, you'll need to recreate it to re-enable the agent.

## Example Configuration

See `terraform.tfvars.example` for a complete example configuration.
