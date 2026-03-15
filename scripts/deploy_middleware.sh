#!/usr/bin/env bash
#
# Deploy the Slack-to-Vertex AI middleware to Cloud Run via Cloud Build.
#
# Usage:
#   ./scripts/deploy_middleware.sh                  # deploy from current commit
#   ./scripts/deploy_middleware.sh --project my-id  # override GCP project
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Defaults (override with flags or environment) ---
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_LOCATION:-us-central1}"
CONFIG="cloudbuild.yaml"

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --project)  PROJECT_ID="$2"; shift 2 ;;
        --region)   REGION="$2";     shift 2 ;;
        --config)   CONFIG="$2";     shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--project PROJECT_ID] [--region REGION] [--config cloudbuild.yaml]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Validate prerequisites ---
if [[ -z "$PROJECT_ID" ]]; then
    # Try .env file as fallback
    if [[ -f "$REPO_ROOT/.env" ]]; then
        PROJECT_ID=$(grep -E '^GCP_PROJECT_ID=' "$REPO_ROOT/.env" | cut -d= -f2 | tr -d ' "'"'"'')
    fi
    if [[ -z "$PROJECT_ID" ]]; then
        echo "Error: GCP project ID not set. Use --project, GCP_PROJECT_ID env var, or .env file."
        exit 1
    fi
fi

if ! command -v gcloud &>/dev/null; then
    echo "Error: gcloud CLI not found. Install it from https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    echo "Error: Not inside a git repository."
    exit 1
fi

# --- Check for uncommitted changes ---
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Warning: You have uncommitted changes. The deployed image will not match your working tree."
    read -rp "Continue anyway? [y/N] " answer
    if [[ ! "$answer" =~ ^[Yy]$ ]]; then
        echo "Aborted. Commit your changes first, then re-run."
        exit 1
    fi
fi

# --- Gather build info ---
COMMIT_SHA=$(git rev-parse HEAD)
COMMIT_SHORT=$(git rev-parse --short HEAD)
COMMIT_MSG=$(git log -1 --pretty=%s)

echo "=== Middleware Deployment ==="
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"
echo "  Commit:   $COMMIT_SHORT ($COMMIT_MSG)"
echo "  Config:   $CONFIG"
echo ""

# --- Submit build ---
echo "Submitting Cloud Build..."
gcloud builds submit "$REPO_ROOT" \
    --config="$REPO_ROOT/$CONFIG" \
    --project="$PROJECT_ID" \
    --substitutions="COMMIT_SHA=$COMMIT_SHA"

echo ""

# --- Route traffic to latest revision ---
SERVICE_NAME="slack-vertex-middleware"
echo "Routing 100% traffic to latest revision..."
gcloud run services update-traffic "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --to-latest

# --- Clean up old revisions (keep only the latest) ---
echo ""
echo "Cleaning up old revisions..."
LATEST_REVISION=$(gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(status.traffic[0].revisionName)")

OLD_REVISIONS=$(gcloud run revisions list \
    --service="$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(metadata.name)" \
    | grep -v "^${LATEST_REVISION}$" || true)

if [[ -n "$OLD_REVISIONS" ]]; then
    while IFS= read -r rev; do
        echo "  Deleting revision: $rev"
        gcloud run revisions delete "$rev" \
            --project="$PROJECT_ID" \
            --region="$REGION" \
            --quiet 2>/dev/null || echo "  (could not delete $rev — may still be draining traffic)"
    done <<< "$OLD_REVISIONS"
    echo "Cleanup complete."
else
    echo "  No old revisions to clean up."
fi

echo ""
echo "=== Deployment complete ==="
echo "Service URL:"
gcloud run services describe "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(status.url)" 2>/dev/null || echo "  (could not retrieve — check Cloud Console)"
