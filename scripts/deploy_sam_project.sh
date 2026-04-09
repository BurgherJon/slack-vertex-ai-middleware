#!/bin/bash
# Deploy Sam the Sommelier's dedicated GCP project using Terraform via Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SAM_TF_DIR="$PROJECT_DIR/terraform/sam-sommelier-project"

echo "=== Deploying Sam the Sommelier's GCP Project ==="
echo ""

# Check if terraform.tfvars exists
if [ ! -f "$SAM_TF_DIR/terraform.tfvars" ]; then
    echo "ERROR: terraform.tfvars not found in $SAM_TF_DIR"
    echo "Please create it from terraform.tfvars.example"
    exit 1
fi

# Use Docker to run Terraform (works on ARM64 via emulation)
TERRAFORM_IMAGE="hashicorp/terraform:1.5"

echo "Step 1: Terraform init"
docker run --rm \
    -v "$SAM_TF_DIR:/workspace" \
    -v "$HOME/.config/gcloud:/root/.config/gcloud" \
    -w /workspace \
    $TERRAFORM_IMAGE init

echo ""
echo "Step 2: Terraform plan"
docker run --rm \
    -v "$SAM_TF_DIR:/workspace" \
    -v "$HOME/.config/gcloud:/root/.config/gcloud" \
    -w /workspace \
    $TERRAFORM_IMAGE plan

echo ""
echo "Step 3: Terraform apply"
docker run --rm -it \
    -v "$SAM_TF_DIR:/workspace" \
    -v "$HOME/.config/gcloud:/root/.config/gcloud" \
    -w /workspace \
    $TERRAFORM_IMAGE apply

echo ""
echo "=== Deployment Complete ==="
