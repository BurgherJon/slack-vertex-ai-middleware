# Google Chat Bot - Terraform Template

This Terraform template creates a dedicated GCP project for a Google Chat bot.

## Why a Dedicated Project?

Google Chat API has a restriction: **one bot per GCP project**. If you want multiple Google Chat bots, each needs its own project.

## What This Creates

- New GCP project
- Google Chat API enabled
- Service account for the bot with Chat API permissions
- Organization policy override to allow service account key creation
- Outputs with next steps for configuration

## Prerequisites

- Google Workspace organization (Google Chat bots require Workspace)
- GCP organization ID
- Billing account ID
- Terraform 1.0+
- `gcloud` CLI authenticated

## Usage

### 1. Copy Template to Your Agent Repository

```bash
# In your agent repository
mkdir -p google-chat-terraform
cp -r /path/to/middleware/docs/terraform-templates/google-chat-project/* google-chat-terraform/
cd google-chat-terraform
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
- `bot_name`: Display name for your bot
- `bot_account_id`: Service account name (lowercase, hyphens)
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
3. Configure Google Chat bot in Console
4. Enable Google Chat in Firestore for your agent
5. Test the bot

## Important Notes

- **Security**: The service account key is sensitive. Delete it after storing in Secret Manager.
- **Organization Policy**: This template overrides the key creation policy for this project only.
- **Cleanup**: If you delete this project, you'll need to recreate it to re-enable the bot.

## Example Configuration

See `terraform.tfvars.example` for a complete example configuration.
