variable "project_id" {
  description = "GCP Project ID for the Google Chat bot (must be globally unique)"
  type        = string
}

variable "project_name" {
  description = "Human-readable project name"
  type        = string
}

variable "organization_id" {
  description = "GCP Organization ID"
  type        = string
}

variable "billing_account" {
  description = "GCP Billing Account ID"
  type        = string
}

variable "region" {
  description = "Default region for resources"
  type        = string
  default     = "us-central1"
}

variable "bot_name" {
  description = "Display name for the Google Chat bot"
  type        = string
}

variable "bot_account_id" {
  description = "Service account ID (lowercase, hyphens only, max 30 chars)"
  type        = string
}

variable "bot_description" {
  description = "Description of what the bot does"
  type        = string
}

variable "bot_avatar_url" {
  description = "URL for the bot's avatar image (optional)"
  type        = string
  default     = ""
}

variable "secret_name" {
  description = "Name for the secret in Secret Manager (in middleware project)"
  type        = string
}
