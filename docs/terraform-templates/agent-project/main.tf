# Google Chat Bot - Dedicated GCP Project Terraform Template
#
# This template creates a dedicated GCP project for a Google Chat bot.
# Each Google Chat bot requires its own GCP project due to API restrictions.
#
# INSTRUCTIONS:
# 1. Copy this entire directory to your agent repository
# 2. Update terraform.tfvars with your specific values
# 3. Run: terraform init && terraform apply
# 4. Follow the "next_steps" output for completing configuration

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  billing_project = var.project_id
  region          = var.region
}

# Create the GCP Project for your Google Chat bot
resource "google_project" "chat_project" {
  name            = var.project_name
  project_id      = var.project_id
  org_id          = var.organization_id
  billing_account = var.billing_account

  # Prevent accidental deletion
  lifecycle {
    prevent_destroy = false  # Set to true in production
  }
}

# Use the created project for subsequent resources
provider "google" {
  alias   = "chat"
  project = google_project.chat_project.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "chat" {
  project = google_project.chat_project.project_id
  service = "chat.googleapis.com"

  disable_on_destroy = false
}

# OPTIONAL: Enable additional APIs if your agent needs them
# Uncomment the ones your agent requires

# resource "google_project_service" "drive" {
#   project = google_project.chat_project.project_id
#   service = "drive.googleapis.com"
#   disable_on_destroy = false
# }

# resource "google_project_service" "sheets" {
#   project = google_project.chat_project.project_id
#   service = "sheets.googleapis.com"
#   disable_on_destroy = false
# }

# Service Account for your Google Chat bot
# This SA will be used for Google Chat API calls (sending messages)
resource "google_service_account" "chat_bot" {
  project      = google_project.chat_project.project_id
  account_id   = var.bot_account_id
  display_name = var.bot_name
  description  = "Service account for ${var.bot_name} Google Chat bot"

  depends_on = [
    google_project_service.chat
  ]
}

# Grant Google Chat bot permissions
resource "google_project_iam_member" "chat_owner" {
  project = google_project.chat_project.project_id
  role    = "roles/chat.owner"
  member  = "serviceAccount:${google_service_account.chat_bot.email}"
}

# Allow service account key creation for this project
# This overrides the organization policy that blocks key creation
resource "google_project_organization_policy" "allow_sa_key_creation" {
  project    = google_project.chat_project.project_id
  constraint = "constraints/iam.disableServiceAccountKeyCreation"

  boolean_policy {
    enforced = false
  }

  depends_on = [
    google_project.chat_project
  ]
}

# Output the service account email for use in other configurations
output "service_account_email" {
  description = "Service account email for the Google Chat bot"
  value       = google_service_account.chat_bot.email
}

output "project_id" {
  description = "GCP Project ID for the Google Chat bot"
  value       = var.project_id
}

output "next_steps" {
  description = "Instructions for completing the setup"
  value       = <<EOT

==================== NEXT STEPS ====================

1. Create a service account key:
   gcloud iam service-accounts keys create ${var.bot_account_id}-sa-key.json \
     --iam-account=${google_service_account.chat_bot.email} \
     --project=${var.project_id}

2. Store the key in the middleware project's Secret Manager:
   # Replace YOUR_MIDDLEWARE_PROJECT with your actual middleware project ID
   gcloud secrets versions add ${var.secret_name} \
     --data-file=${var.bot_account_id}-sa-key.json \
     --project=YOUR_MIDDLEWARE_PROJECT

   # Securely delete the key file
   rm -f ${var.bot_account_id}-sa-key.json

3. OPTIONAL: If your agent needs Google Sheets/Drive access:
   Share Google Sheets with the service account:
   ${google_service_account.chat_bot.email}

4. Configure Google Chat bot in Console:
   - Go to: https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat
   - Project: ${var.project_id}
   - Click "Configuration"
   - Bot name: ${var.bot_name}
   - Avatar URL: ${var.bot_avatar_url}
   - Description: ${var.bot_description}
   - Functionality: "Receive 1:1 messages" and "Join spaces and group conversations"
   - Connection settings: "HTTPS"
   - Bot URL: YOUR_MIDDLEWARE_URL/api/v1/google-chat/events
   - Permissions: "Specific people and groups" (add test users)

5. Enable Google Chat for your agent in Firestore:
   python scripts/enable_google_chat_agent.py \
     --project YOUR_MIDDLEWARE_PROJECT \
     --agent-id YOUR_AGENT_ID \
     --secret-name ${var.secret_name} \
     --google-chat-project-id ${var.project_id}

6. Test the bot:
   - Open Google Chat
   - Search for "${var.bot_name}"
   - Send a test message

====================================================

EOT
}
