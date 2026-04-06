# Terraform Infrastructure for Vertex AI Middleware

This directory contains Terraform configuration for deploying the complete GCP infrastructure for the Slack/Google Chat Vertex AI middleware.

## What Gets Created

- **APIs**: All required GCP APIs (Firestore, Vertex AI, Cloud Run, Secret Manager, etc.)
- **Service Accounts**:
  - `growth-coach-sheets` (Google Chat + Drive access)
  - `sommelier-sheets` (Google Chat + Drive access)
  - `scheduler-sa` (Cloud Scheduler invoker)
- **IAM Permissions**: All necessary roles and permissions
- **Secret Manager**: Secret definitions for credentials and API keys
- **GCS Bucket**: Temporary storage for Slack file uploads (1-day lifecycle)
- **Cloud Run**: Middleware service deployment
- **Cloud Scheduler**: Scheduled job dispatcher (runs every minute)

## Prerequisites

1. **Google Workspace Business Starter** account (for Google Chat bot support)
2. **GCP Project** created in Workspace organization
3. **Terraform** installed (v1.0+)
4. **gcloud CLI** installed and authenticated
5. **Project Owner** or **Editor** permissions

## Initial Setup

### 1. Configure Terraform Variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
project_id  = "your-workspace-project-id"
region      = "us-central1"
environment = "prod"
```

### 2. Authenticate with GCP

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 3. Create Firestore Database

Terraform cannot create Firestore databases, so create it manually:

```bash
gcloud firestore databases create \
  --location=us-central1 \
  --type=firestore-native \
  --project=YOUR_PROJECT_ID
```

### 4. (Optional) Setup Terraform State Backend

For team collaboration, store Terraform state in GCS:

```bash
# Create bucket for Terraform state
gsutil mb gs://YOUR_PROJECT_ID-terraform-state

# Enable versioning
gsutil versioning set on gs://YOUR_PROJECT_ID-terraform-state
```

Uncomment the backend configuration in `providers.tf`:
```hcl
backend "gcs" {
  bucket = "YOUR_PROJECT_ID-terraform-state"
  prefix = "middleware/state"
}
```

## Deployment

### 1. Initialize Terraform

```bash
terraform init
```

### 2. Review the Plan

```bash
terraform plan
```

Review all resources that will be created. Verify:
- Correct project ID
- All required APIs
- Service accounts and permissions
- GCS bucket name

### 3. Apply Infrastructure

```bash
terraform apply
```

Type `yes` when prompted. This will take 5-10 minutes.

### 4. Save Outputs

```bash
terraform output -json > outputs.json
```

The outputs include:
- Cloud Run URL
- Service account emails
- GCS bucket name
- Webhook URLs
- Next steps guide

## Post-Deployment Steps

After `terraform apply` completes, you must:

### 1. Generate Service Account Keys

```bash
# Growth Coach
gcloud iam service-accounts keys create growth-coach-sa-key.json \
  --iam-account=$(terraform output -raw growth_coach_service_account_email)

# Sommelier
gcloud iam service-accounts keys create sommelier-sa-key.json \
  --iam-account=$(terraform output -raw sommelier_service_account_email)
```

### 2. Store Keys in Secret Manager

```bash
PROJECT_ID=$(terraform output -raw project_id)

# Growth Coach credentials
gcloud secrets versions add growth-coach-credentials \
  --data-file=growth-coach-sa-key.json \
  --project=$PROJECT_ID

# Sommelier credentials
gcloud secrets versions add sommelier-credentials \
  --data-file=sommelier-sa-key.json \
  --project=$PROJECT_ID

# Delete local key files
rm -f growth-coach-sa-key.json sommelier-sa-key.json
```

### 3. Add Slack Signing Secret

```bash
# Get the comma-separated list of Slack signing secrets from old project
OLD_SECRET=$(gcloud secrets versions access latest \
  --secret=slack-signing-secret \
  --project=playingwithai-460811)

# Store in new project
echo -n "$OLD_SECRET" | gcloud secrets versions add slack-signing-secret \
  --data-file=- \
  --project=$PROJECT_ID
```

## Updating Infrastructure

To modify infrastructure:

1. Edit the relevant `.tf` file
2. Run `terraform plan` to review changes
3. Run `terraform apply` to apply changes

## Common Operations

### View Current State

```bash
terraform show
```

### List All Resources

```bash
terraform state list
```

### Get Specific Output

```bash
terraform output cloud_run_url
terraform output growth_coach_service_account_email
```

### Refresh State

```bash
terraform refresh
```

## Destroying Infrastructure

**WARNING**: This will delete all resources. Ensure you have backups!

```bash
terraform destroy
```

## Troubleshooting

### API Not Enabled Error

If you see "API not enabled" errors, wait a few minutes for APIs to propagate, then run `terraform apply` again.

### Permission Denied Errors

Ensure you have the following roles:
- `roles/owner` or `roles/editor` on the project
- `roles/iam.securityAdmin` (for service account creation)
- `roles/resourcemanager.projectIamAdmin` (for IAM bindings)

### Firestore Error

Terraform cannot create Firestore databases. Create it manually first:
```bash
gcloud firestore databases create --location=us-central1 --type=firestore-native --project=YOUR_PROJECT_ID
```

### Cloud Run Image Not Found

The initial Cloud Run deployment uses a placeholder image. Deploy the actual application using Cloud Build:
```bash
cd ..
gcloud builds submit --config cloudbuild.yaml --project YOUR_PROJECT_ID
```

## File Structure

```
terraform/
├── README.md                 # This file
├── terraform.tfvars.example  # Example variables
├── terraform.tfvars          # Your variables (gitignored)
├── providers.tf              # Terraform and provider config
├── variables.tf              # Variable definitions
├── apis.tf                   # GCP API enablement
├── firestore.tf              # Firestore placeholder
├── service_accounts.tf       # Service accounts and IAM
├── secrets.tf                # Secret Manager secrets
├── storage.tf                # GCS bucket configuration
├── cloud_run.tf              # Cloud Run service
├── scheduler.tf              # Cloud Scheduler job
└── outputs.tf                # Output values
```

## Next Steps

After Terraform deployment:
1. Deploy Vertex AI agents to new project
2. Deploy Cloud Run middleware
3. Import Firestore data from old project
4. Share Google Drive files with new service accounts
5. Update Slack webhook URLs
6. Configure Google Chat bots
7. Test all integrations

See the main project README for detailed migration steps.
