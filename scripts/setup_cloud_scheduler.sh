#!/bin/bash
# Setup Cloud Scheduler dispatcher job for scheduled jobs.
#
# This script:
# 1. Creates a service account for Cloud Scheduler (if not exists)
# 2. Grants the service account permission to invoke Cloud Run
# 3. Creates a single dispatcher job that runs every minute
#
# The dispatcher job calls /api/v1/scheduled-jobs/process which:
# - Queries Firestore for enabled jobs
# - Checks which jobs are due based on their cron schedule
# - Executes each due job
#
# Prerequisites:
# - gcloud CLI installed and authenticated
# - Appropriate IAM permissions in the GCP project
# - Cloud Run service already deployed
#
# Usage:
#   ./setup_cloud_scheduler.sh --cloud-run-service YOUR_SERVICE_NAME
#
# Example:
#   ./setup_cloud_scheduler.sh --cloud-run-service slack-vertex-middleware

set -e

# Default values
REGION="us-central1"
SERVICE_ACCOUNT_NAME="scheduler-sa"
SERVICE_ACCOUNT_DISPLAY_NAME="Cloud Scheduler Service Account"
DISPATCHER_JOB_NAME="scheduled-jobs-dispatcher"
DISPATCHER_SCHEDULE="* * * * *"  # Every minute

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
        --schedule)
            DISPATCHER_SCHEDULE="$2"
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
echo "Cloud Scheduler Dispatcher Setup"
echo "======================================"
echo "Project ID:        $PROJECT_ID"
echo "Region:            $REGION"
echo "Cloud Run Service: $CLOUD_RUN_SERVICE"
echo "Service Account:   $SERVICE_ACCOUNT_NAME"
echo "Dispatcher Job:    $DISPATCHER_JOB_NAME"
echo "Schedule:          $DISPATCHER_SCHEDULE"
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
    echo "  Error: Could not retrieve Cloud Run URL."
    echo "  Make sure the Cloud Run service is deployed first."
    exit 1
fi
echo "  ✓ Cloud Run URL: $CLOUD_RUN_URL"
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

# Step 5: Create or update the dispatcher job
echo "Step 5: Creating dispatcher Cloud Scheduler job..."
DISPATCHER_FULL_NAME="projects/$PROJECT_ID/locations/$REGION/jobs/$DISPATCHER_JOB_NAME"

# Check if job exists
if gcloud scheduler jobs describe "$DISPATCHER_JOB_NAME" \
    --project="$PROJECT_ID" \
    --location="$REGION" &>/dev/null; then
    echo "  Updating existing dispatcher job..."
    gcloud scheduler jobs update http "$DISPATCHER_JOB_NAME" \
        --project="$PROJECT_ID" \
        --location="$REGION" \
        --schedule="$DISPATCHER_SCHEDULE" \
        --time-zone="UTC" \
        --uri="${CLOUD_RUN_URL}/api/v1/scheduled-jobs/process" \
        --http-method=POST \
        --oidc-service-account-email="$SERVICE_ACCOUNT_EMAIL" \
        --oidc-token-audience="$CLOUD_RUN_URL" \
        --quiet
    echo "  ✓ Updated dispatcher job: $DISPATCHER_JOB_NAME"
else
    echo "  Creating new dispatcher job..."
    gcloud scheduler jobs create http "$DISPATCHER_JOB_NAME" \
        --project="$PROJECT_ID" \
        --location="$REGION" \
        --schedule="$DISPATCHER_SCHEDULE" \
        --time-zone="UTC" \
        --uri="${CLOUD_RUN_URL}/api/v1/scheduled-jobs/process" \
        --http-method=POST \
        --oidc-service-account-email="$SERVICE_ACCOUNT_EMAIL" \
        --oidc-token-audience="$CLOUD_RUN_URL" \
        --quiet
    echo "  ✓ Created dispatcher job: $DISPATCHER_JOB_NAME"
fi
echo ""

# Output configuration
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Dispatcher job created: $DISPATCHER_JOB_NAME"
echo "  Schedule: Every minute"
echo "  Target:   ${CLOUD_RUN_URL}/api/v1/scheduled-jobs/process"
echo ""
echo "The dispatcher will:"
echo "  1. Run every minute"
echo "  2. Query Firestore for enabled scheduled jobs"
echo "  3. Check which jobs are due based on their cron schedule"
echo "  4. Execute each due job"
echo ""
echo "Environment variables for Cloud Run (if not already set):"
echo ""
echo "  CLOUD_RUN_URL=$CLOUD_RUN_URL"
echo "  CLOUD_SCHEDULER_SERVICE_ACCOUNT=$SERVICE_ACCOUNT_EMAIL"
echo ""
echo "To test the dispatcher manually:"
echo "  gcloud scheduler jobs run $DISPATCHER_JOB_NAME --location=$REGION"
echo ""
echo "To view dispatcher logs:"
echo "  gcloud logging read 'resource.type=cloud_scheduler_job AND resource.labels.job_id=$DISPATCHER_JOB_NAME' --limit=10"
echo ""
echo "======================================"
