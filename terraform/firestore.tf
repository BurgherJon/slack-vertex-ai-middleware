# Firestore Database Configuration

# Note: Firestore database must be created manually or via gcloud
# Terraform cannot currently create Firestore Native databases
# Run this command before applying Terraform:
# gcloud firestore databases create --location=us-central1 --type=firestore-native --project=YOUR_PROJECT_ID

# This is a placeholder to document the requirement
resource "null_resource" "firestore_database" {
  provisioner "local-exec" {
    command = <<-EOT
      echo "Firestore database should be created manually:"
      echo "gcloud firestore databases create --location=${var.region} --type=firestore-native --project=${var.project_id}"
    EOT
  }

  depends_on = [
    google_project_service.firestore
  ]
}
