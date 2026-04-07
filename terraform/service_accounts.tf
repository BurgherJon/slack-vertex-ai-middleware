# Service Accounts Configuration

# Growth Coach Service Account
resource "google_service_account" "growth_coach" {
  account_id   = "growth-coach-sheets"
  display_name = "Growth Coach Sheets"
  description  = "Service account for Growth Coach agent (Google Drive/Sheets and Google Chat access)"

  depends_on = [
    google_project_service.chat
  ]
}

# Grant Google Chat bot permissions to Growth Coach
resource "google_project_iam_member" "growth_coach_chat_owner" {
  project = var.project_id
  role    = "roles/chat.owner"
  member  = "serviceAccount:${google_service_account.growth_coach.email}"
}

# Sam the Sommelier Service Account
resource "google_service_account" "sommelier" {
  account_id   = "sommelier-sheets"
  display_name = "Sommelier Sheets"
  description  = "Service account for Sam the Sommelier agent (Google Drive/Sheets and Google Chat access)"

  depends_on = [
    google_project_service.chat
  ]
}

# Grant Google Chat bot permissions to Sommelier
resource "google_project_iam_member" "sommelier_chat_owner" {
  project = var.project_id
  role    = "roles/chat.owner"
  member  = "serviceAccount:${google_service_account.sommelier.email}"
}

# Cloud Scheduler Service Account
resource "google_service_account" "scheduler" {
  account_id   = "scheduler-sa"
  display_name = "Cloud Scheduler Service Account"
  description  = "Service account for Cloud Scheduler to invoke Cloud Run"

  depends_on = [
    google_project_service.cloudscheduler
  ]
}

# Grant Cloud Run invoker permission to Scheduler SA
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  service  = google_cloud_run_v2_service.middleware.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# Default Compute Service Account Permissions
# Note: The default compute service account is automatically created by GCP
# Format: PROJECT_NUMBER-compute@developer.gserviceaccount.com

data "google_project" "project" {}

locals {
  default_compute_sa = "${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Grant Firestore access to default compute SA (used by Cloud Run)
resource "google_project_iam_member" "compute_firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${local.default_compute_sa}"
}

# Grant Secret Manager access to default compute SA
resource "google_secret_manager_secret_iam_member" "compute_slack_signing_secret" {
  secret_id = google_secret_manager_secret.slack_signing_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.default_compute_sa}"
}

resource "google_secret_manager_secret_iam_member" "compute_growth_coach_creds" {
  secret_id = google_secret_manager_secret.growth_coach_credentials.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.default_compute_sa}"
}

resource "google_secret_manager_secret_iam_member" "compute_sommelier_creds" {
  secret_id = google_secret_manager_secret.sommelier_credentials.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.default_compute_sa}"
}

# Grant GCS access to default compute SA
resource "google_storage_bucket_iam_member" "compute_storage_admin" {
  bucket = google_storage_bucket.slack_files.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.default_compute_sa}"
}

# Grant Vertex AI access to default compute SA (via project-level IAM)
resource "google_project_iam_member" "compute_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${local.default_compute_sa}"
}

# Grant Cloud Build/deployment permissions to default compute SA
# (Cloud Build uses compute SA for builds and deployments)
resource "google_project_iam_member" "compute_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${local.default_compute_sa}"
}

resource "google_project_iam_member" "compute_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${local.default_compute_sa}"
}

resource "google_project_iam_member" "compute_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${local.default_compute_sa}"
}

# Grant service account user role (needed for actAs during Cloud Run deployment)
resource "google_service_account_iam_member" "compute_sa_user" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.default_compute_sa}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.default_compute_sa}"
}

# Grant Artifact Registry writer role for pushing Docker images to GCR
# Note: GCR (gcr.io) is managed by Artifact Registry under the hood
resource "google_artifact_registry_repository_iam_member" "compute_artifact_writer" {
  project    = var.project_id
  location   = "us"
  repository = "gcr.io"
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${local.default_compute_sa}"
}
