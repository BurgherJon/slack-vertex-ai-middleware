# Organization policy to allow public access to Cloud Run services
# This overrides the organization-level domain restriction for this project

resource "google_project_organization_policy" "domain_restriction_override" {
  project    = var.project_id
  constraint = "constraints/iam.allowedPolicyMemberDomains"

  list_policy {
    allow {
      all = true
    }
  }
}
