# Google Cloud Storage Configuration

# GCS Bucket for Slack file uploads
resource "google_storage_bucket" "slack_files" {
  name     = "${var.project_id}-slack-files"
  location = var.region

  # Uniform bucket-level access
  uniform_bucket_level_access = true

  # Lifecycle rule to auto-delete files after specified days
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = var.gcs_bucket_lifecycle_days
    }
  }

  # Enable versioning for safety (optional)
  versioning {
    enabled = false
  }

  # Force destroy to allow Terraform to delete bucket even if not empty
  # Set to false in production if you want to prevent accidental deletion
  force_destroy = true

  depends_on = [
    google_project_service.storage
  ]
}
