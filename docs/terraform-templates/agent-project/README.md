# Agent Project - Terraform Template

This Terraform template creates a dedicated GCP project for an agent that uses Google Chat.

## Why a Dedicated Project?

Some agents may require dedicated GCP projects for various reasons:
- **Google Chat bots**: Google Chat API has a restriction of one bot per GCP project
- **Organizational separation**: Isolate agent resources from middleware
- **Independent lifecycle**: Agents can be created/destroyed without affecting middleware

## What This Creates

- New GCP project
- Required APIs enabled (customizable per agent)
- Service account for the agent with necessary permissions
- Organization policy override to allow service account key creation
- Outputs with next steps for configuration

## Prerequisites

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
