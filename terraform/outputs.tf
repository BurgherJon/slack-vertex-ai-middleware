# Terraform Outputs

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

output "cloud_run_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.middleware.uri
}

output "gcs_bucket_name" {
  description = "GCS bucket name for Slack files"
  value       = google_storage_bucket.slack_files.name
}

output "growth_coach_service_account_email" {
  description = "Growth Coach service account email (share Google Drive files with this)"
  value       = google_service_account.growth_coach.email
}

output "sommelier_service_account_email" {
  description = "Sommelier service account email (share Google Drive files with this)"
  value       = google_service_account.sommelier.email
}

output "scheduler_service_account_email" {
  description = "Scheduler service account email"
  value       = google_service_account.scheduler.email
}

output "slack_webhook_url" {
  description = "Slack webhook URL (use in Slack app Event Subscriptions)"
  value       = "${google_cloud_run_v2_service.middleware.uri}/api/v1/slack/events"
}

output "google_chat_webhook_url" {
  description = "Google Chat webhook URL (use in Google Chat bot configuration)"
  value       = "${google_cloud_run_v2_service.middleware.uri}/api/v1/google-chat/events"
}

output "next_steps" {
  description = "Next steps after Terraform apply"
  value       = <<-EOT

    ==================== NEXT STEPS ====================

    1. Generate service account keys:
       gcloud iam service-accounts keys create growth-coach-sa-key.json \
         --iam-account=${google_service_account.growth_coach.email}

       gcloud iam service-accounts keys create sommelier-sa-key.json \
         --iam-account=${google_service_account.sommelier.email}

    2. Store service account keys in Secret Manager:
       gcloud secrets versions add growth-coach-credentials \
         --data-file=growth-coach-sa-key.json --project=${var.project_id}

       gcloud secrets versions add sommelier-credentials \
         --data-file=sommelier-sa-key.json --project=${var.project_id}

       rm -f growth-coach-sa-key.json sommelier-sa-key.json

    3. Add Slack signing secret to Secret Manager:
       echo -n "YOUR_SLACK_SECRET" | gcloud secrets versions add slack-signing-secret \
         --data-file=- --project=${var.project_id}

    4. Share Google Drive files with service accounts:
       - ${google_service_account.growth_coach.email}
       - ${google_service_account.sommelier.email}

    5. Update Slack app webhook URL:
       ${google_cloud_run_v2_service.middleware.uri}/api/v1/slack/events

    6. Configure Google Chat bots with webhook URL:
       ${google_cloud_run_v2_service.middleware.uri}/api/v1/google-chat/events

    ====================================================
  EOT
}
