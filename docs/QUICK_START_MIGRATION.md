# Quick Start: GCP Migration to Google Workspace

This is your starting point for migrating from personal GCP to Google Workspace organization. Follow these steps to begin.

## Overview

**Current**: `playingwithai-460811` (personal GCP)
**Target**: New Google Workspace organization project
**Time**: 2-3 days including testing
**Goal**: Enable Google Chat bots + maintain Slack functionality

---

## Step 1: Sign Up for Google Workspace ⏱️ 30 minutes

1. Go to [workspace.google.com](https://workspace.google.com)
2. Click **Get Started**
3. Select **Business Starter** plan ($6-7/month)
4. Use domain: **CavellandCavell.com**
5. Complete signup and verify domain

**✋ STOP HERE** until Workspace is fully set up and domain verified.

---

## Step 2: Create GCP Project in Workspace Organization ⏱️ 5 minutes

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click project dropdown → **New Project**
3. **Project Name**: `vertex-ai-middleware-prod` (or your choice)
4. **Organization**: Select **CavellandCavell.com**
5. Click **Create**
6. **SAVE THE PROJECT ID** (e.g., `vertex-ai-middleware-prod-123456`)

```bash
# Set environment variable for later use
export NEW_PROJECT="your-new-project-id-here"
echo "NEW_PROJECT=$NEW_PROJECT" >> ~/.bashrc
```

---

## Step 3: Export Current Data ⏱️ 10 minutes

```bash
# Set old project
export OLD_PROJECT="playingwithai-460811"
gcloud config set project $OLD_PROJECT

# Create backup bucket (if doesn't exist)
gsutil mb -l us-central1 gs://${OLD_PROJECT}-backup

# Export Firestore
gcloud firestore export gs://${OLD_PROJECT}-backup/firestore-migration-$(date +%Y%m%d)

# Save the export path
echo "Export completed to: gs://${OLD_PROJECT}-backup/firestore-migration-$(date +%Y%m%d)"
```

**✅ Checkpoint**: You should see "Export completed successfully" message.

---

## Step 4: Configure Terraform ⏱️ 5 minutes

```bash
# Navigate to terraform directory
cd terraform

# Create your terraform.tfvars
cp terraform.tfvars.example terraform.tfvars

# Edit the file
nano terraform.tfvars
```

Set:
```hcl
project_id  = "your-new-project-id"  # From Step 2
region      = "us-central1"
environment = "prod"
```

Save and exit (Ctrl+X, Y, Enter).

---

## Step 5: Authenticate and Initialize Terraform ⏱️ 5 minutes

```bash
# Switch to new project
gcloud config set project $NEW_PROJECT

# Authenticate for Terraform
gcloud auth application-default login

# Create Firestore database
gcloud firestore databases create \
  --location=us-central1 \
  --type=firestore-native \
  --project=$NEW_PROJECT

# Initialize Terraform
terraform init
```

**✅ Checkpoint**: You should see "Terraform has been successfully initialized!"

---

## Step 6: Review and Apply Infrastructure ⏱️ 15 minutes

```bash
# Review what will be created
terraform plan

# Read through the output carefully!
# Verify project ID, service accounts, GCS bucket name

# Apply infrastructure (this creates everything)
terraform apply

# Type 'yes' when prompted
```

**✅ Checkpoint**: You should see "Apply complete! Resources: XX added, 0 changed, 0 destroyed."

---

## Step 7: Save Outputs ⏱️ 1 minute

```bash
# Save all outputs to file
terraform output -json > ../migration-outputs.json

# View key outputs
terraform output cloud_run_url
terraform output growth_coach_service_account_email
terraform output sommelier_service_account_email

# View next steps
terraform output next_steps
```

**✅ Checkpoint**: You should see Cloud Run URL and service account emails.

---

## Step 8: Populate Secrets ⏱️ 5 minutes

```bash
# Generate service account keys
gcloud iam service-accounts keys create growth-coach-sa-key.json \
  --iam-account=$(terraform output -raw growth_coach_service_account_email)

gcloud iam service-accounts keys create sommelier-sa-key.json \
  --iam-account=$(terraform output -raw sommelier_service_account_email)

# Store in Secret Manager
gcloud secrets versions add growth-coach-credentials \
  --data-file=growth-coach-sa-key.json --project=$NEW_PROJECT

gcloud secrets versions add sommelier-credentials \
  --data-file=sommelier-sa-key.json --project=$NEW_PROJECT

# Copy Slack signing secret from old project
OLD_SECRET=$(gcloud secrets versions access latest \
  --secret=slack-signing-secret --project=$OLD_PROJECT)

echo -n "$OLD_SECRET" | gcloud secrets versions add slack-signing-secret \
  --data-file=- --project=$NEW_PROJECT

# Delete local key files
rm -f growth-coach-sa-key.json sommelier-sa-key.json
```

**✅ Checkpoint**: You should see "Created version [1] of the secret" for each secret.

---

## Step 9: What's Next?

You've completed the infrastructure setup! The next major steps are:

1. **Redeploy Vertex AI Agents** (1-2 hours)
   - Deploy Growth Coach to new project
   - Deploy Sam the Sommelier to new project
   - Capture new agent IDs

2. **Deploy Middleware** (15 minutes)
   - Build and deploy Cloud Run service

3. **Import Firestore Data** (30 minutes)
   - Import backup from old project
   - Update agent documents with new IDs

4. **Share Google Drive Files** (15 minutes)
   - Share sheets with new service account emails

5. **Update External Integrations** (30 minutes)
   - Update Slack webhook URLs
   - Configure Google Chat bots

6. **Test Everything** (1 hour)
   - Slack integration
   - Google Chat integration
   - Scheduled jobs
   - Cross-platform sessions

---

## Detailed Guide

For complete step-by-step instructions for the remaining phases, see:

📖 **[MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)**

This guide covers:
- Phases 4-11 in detail
- Troubleshooting common issues
- Testing checklist
- Rollback plan
- Decommissioning old infrastructure

---

## Summary: What You Just Did

✅ Created Google Workspace account
✅ Created new GCP project in Workspace org
✅ Exported Firestore data from old project
✅ Deployed complete infrastructure with Terraform:
   - Enabled all required APIs
   - Created service accounts with permissions
   - Set up Secret Manager
   - Created GCS bucket
   - Deployed Cloud Run service
   - Created Cloud Scheduler job
✅ Populated secrets with credentials

**Infrastructure is ready!** You can now proceed with redeploying agents and migrating data.

---

## Quick Commands Reference

```bash
# View Terraform outputs
cd terraform
terraform output

# Check Cloud Run status
gcloud run services describe slack-vertex-middleware \
  --region=us-central1 --project=$NEW_PROJECT

# List service accounts
gcloud iam service-accounts list --project=$NEW_PROJECT

# Check secrets
gcloud secrets list --project=$NEW_PROJECT

# View Cloud Run logs
gcloud run logs tail slack-vertex-middleware \
  --region=us-central1 --project=$NEW_PROJECT
```

---

## Need Help?

- **Terraform issues**: Check [terraform/README.md](../terraform/README.md)
- **Detailed migration steps**: See [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)
- **Google Chat setup**: See [GOOGLE_CHAT_CONFIGURATION_STEPS.md](./GOOGLE_CHAT_CONFIGURATION_STEPS.md)

---

## Estimated Timeline from Here

- **Agent Redeployment**: 1-2 hours
- **Middleware Deployment**: 15 minutes
- **Data Migration**: 30 minutes
- **Drive Sharing**: 15 minutes
- **External Updates**: 30 minutes
- **Testing**: 1 hour

**Total Remaining**: ~4-5 hours of active work

You're making great progress! 🚀
