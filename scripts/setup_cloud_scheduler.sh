#!/bin/bash
# Setup Cloud Scheduler service account and permissions for scheduled jobs.
#
# This script:
# 1. Creates a service account for Cloud Scheduler
# 2. Grants the service account permission to invoke Cloud Run
# 3. Outputs the configuration values needed for the middleware
#
# Prerequisites:
# - gcloud CLI installed and authenticated
# - Appropriate IAM permissions in the GCP project
#
# Usage:
#   ./setup_cloud_scheduler.sh --project-id YOUR_PROJECT_ID --cloud-run-service YOUR_SERVICE_NAME
#
# Example:
#   ./setup_cloud_scheduler.sh --project-id my-project --cloud-run-service slack-vertex-middleware

set -e

# Default values
REGION="us-central1"
SERVICE_ACCOUNT_NAME="scheduler-sa"
SERVICE_ACCOUNT_DISPLAY_NAME="Cloud Scheduler Service Account"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --project-id)
            PROJECT_ID="$2"
            shift 2
            ;;
        --cloud-run-service)
            CLOUD_RUN_SERVICE="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --service-account-name)
            SERVICE_ACCOUNT_NAME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$PROJECT_ID" ]; then
    # Try to get from environment or gcloud config
    PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
fi

if [ -z "$PROJECT_ID" ]; then
    echo "Error: --project-id is required or set GCP_PROJECT_ID environment variable"
    exit 1
fi

if [ -z "$CLOUD_RUN_SERVICE" ]; then
    echo "Error: --cloud-run-service is required"
    exit 1
fi

echo "======================================"
echo "Cloud Scheduler Setup"
echo "======================================"
echo "Project ID:        $PROJECT_ID"
echo "Region:            $REGION"
echo "Cloud Run Service: $CLOUD_RUN_SERVICE"
echo "Service Account:   $SERVICE_ACCOUNT_NAME"
echo "======================================"
echo ""

# Full service account email
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Step 1: Create service account (if it doesn't exist)
echo "Step 1: Creating service account..."
if gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
    echo "  Service account already exists: $SERVICE_ACCOUNT_EMAIL"
else
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --project="$PROJECT_ID" \
        --display-name="$SERVICE_ACCOUNT_DISPLAY_NAME" \
        --description="Service account for Cloud Scheduler to invoke Cloud Run scheduled jobs"
    echo "  ✓ Created service account: $SERVICE_ACCOUNT_EMAIL"
fi
echo ""

# Step 2: Get Cloud Run service URL
echo "Step 2: Getting Cloud Run service URL..."
CLOUD_RUN_URL=$(gcloud run services describe "$CLOUD_RUN_SERVICE" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(status.url)" 2>/dev/null || echo "")

if [ -z "$CLOUD_RUN_URL" ]; then
    echo "  Warning: Could not retrieve Cloud Run URL."
    echo "  Make sure the Cloud Run service is deployed first."
    echo "  You'll need to set CLOUD_RUN_URL manually in your configuration."
    CLOUD_RUN_URL="<YOUR_CLOUD_RUN_URL>"
else
    echo "  ✓ Cloud Run URL: $CLOUD_RUN_URL"
fi
echo ""

# Step 3: Grant Cloud Run invoker role
echo "Step 3: Granting Cloud Run invoker permission..."
gcloud run services add-iam-policy-binding "$CLOUD_RUN_SERVICE" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/run.invoker" \
    --quiet
echo "  ✓ Granted roles/run.invoker to $SERVICE_ACCOUNT_EMAIL"
echo ""

# Step 4: Enable Cloud Scheduler API (if not already enabled)
echo "Step 4: Enabling Cloud Scheduler API..."
gcloud services enable cloudscheduler.googleapis.com --project="$PROJECT_ID" --quiet
echo "  ✓ Cloud Scheduler API enabled"
echo ""

# Output configuration
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Add these values to your middleware configuration (.env or Cloud Run env vars):"
echo ""
echo "  CLOUD_RUN_URL=$CLOUD_RUN_URL"
echo "  CLOUD_SCHEDULER_LOCATION=$REGION"
echo "  CLOUD_SCHEDULER_SERVICE_ACCOUNT=$SERVICE_ACCOUNT_EMAIL"
echo ""
echo "For Cloud Run deployment (cloudbuild.yaml or deploy script), add:"
echo ""
echo "  --set-env-vars CLOUD_RUN_URL=$CLOUD_RUN_URL"
echo "  --set-env-vars CLOUD_SCHEDULER_LOCATION=$REGION"
echo "  --set-env-vars CLOUD_SCHEDULER_SERVICE_ACCOUNT=$SERVICE_ACCOUNT_EMAIL"
echo ""
echo "======================================"
