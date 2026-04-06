# Terraform Provider Configuration

terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Backend configuration for state storage
  # Uncomment and configure after initial project setup
  # backend "gcs" {
  #   bucket = "YOUR_PROJECT_ID-terraform-state"
  #   prefix = "middleware/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
