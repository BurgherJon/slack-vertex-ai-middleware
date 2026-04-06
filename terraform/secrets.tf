# Secret Manager Configuration

# Slack Signing Secret
resource "google_secret_manager_secret" "slack_signing_secret" {
  secret_id = "slack-signing-secret"

  replication {
    auto {}
  }

  depends_on = [
    google_project_service.secretmanager
  ]
}

# Note: Secret values must be added manually using:
# echo -n "YOUR_SECRET_VALUE" | gcloud secrets versions add slack-signing-secret --data-file=- --project=YOUR_PROJECT_ID

# Growth Coach Service Account Credentials
resource "google_secret_manager_secret" "growth_coach_credentials" {
  secret_id = "growth-coach-credentials"

  replication {
    auto {}
  }

  depends_on = [
    google_project_service.secretmanager
  ]
}

# Note: Populate with service account JSON:
# gcloud secrets versions add growth-coach-credentials --data-file=growth-coach-sa-key.json --project=YOUR_PROJECT_ID

# Sommelier Service Account Credentials
resource "google_secret_manager_secret" "sommelier_credentials" {
  secret_id = "sommelier-credentials"

  replication {
    auto {}
  }

  depends_on = [
    google_project_service.secretmanager
  ]
}

# Note: Populate with service account JSON:
# gcloud secrets versions add sommelier-credentials --data-file=sommelier-sa-key.json --project=YOUR_PROJECT_ID
