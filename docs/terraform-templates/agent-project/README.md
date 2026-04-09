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

After `terraform apply` completes, follow the "next_steps" output instructions to:
1. Create service account key
2. Store key in middleware project's Secret Manager
3. Configure platform-specific settings (Google Chat bot, etc.)
4. Enable platform in Firestore for your agent
5. Test the agent

## Important Notes

- **Security**: The service account key is sensitive. Delete it after storing in Secret Manager.
- **Organization Policy**: This template overrides the key creation policy for this project only.
- **Cleanup**: If you delete this project, you'll need to recreate it to re-enable the agent.

## Example Configuration

See `terraform.tfvars.example` for a complete example configuration.
