# =============================================================================
# Discord Worker VM (multi-tenant)
#
# Discord cannot deliver DMs over HTTP webhooks — only over a long-lived
# Gateway WebSocket. The Forum's Cloud Run service is request-driven and
# scales to zero, which is the wrong fit for a long-lived socket. So when
# var.use_discord is true, we provision a small Compute Engine VM that
# holds Gateway connections open — ONE connection per Discord-enabled
# agent — and forwards each DM to the Forum's
# /api/v1/discord/events/{agent_id} endpoint.
#
# The worker is multi-tenant: it queries the Forum's Firestore `agents`
# collection on startup (and on a refresh interval) for any agent that
# has a `discord` platform block with `enabled: true`, then opens one
# Gateway connection per such agent in a single Python process. Bot
# tokens live in the AGENTS' projects, not the Forum's project. The
# Agent-Template repo (github.com/Comites-ai/Agent-Template) provisions
# each agent's `discord-bot-token` secret (SECTION 5 of its
# terraform/main.tf) and the cross-project secretAccessor grant to the
# Forum's worker SA.
#
# COST NOTE:
#   The default machine_type (e2-micro) in us-central1, us-west1, or
#   us-east1 is included in GCP's Always Free tier — one VM per billing
#   account. If your free-tier e2-micro is already in use, or you pick a
#   region outside that list, expect ~$6-7/month for the instance. Verify
#   your billing console before applying.
#
# OS PATCHING:
#   The VM runs Container-Optimized OS (cos-stable) with automatic updates
#   enabled, so the host OS patches itself. The discord-worker container
#   image, however, is pinned and must be rebuilt and redeployed manually
#   when discord.py, the Python base image, or any other dependency ships
#   a security fix. See docs/DISCORD_WORKER.md for the redeploy runbook;
#   review and rebuild quarterly or sooner if a CVE is reported.
#
# CONTAINER LAUNCH MECHANISM:
#   The container is started by a cloud-init (`user-data`) systemd unit,
#   NOT the legacy `gce-container-declaration` metadata key. Google
#   discontinued the container startup agent (konlet) behind that key:
#   new VMs using it are blocked from July 31, 2026 and existing ones
#   are unsupported after July 31, 2027.
#     Deprecation notice: https://cloud.google.com/compute/docs/deprecations/container-startup-agent-on-compute
#     Migration guide:    https://cloud.google.com/compute/docs/containers/migrate-containers
# =============================================================================

# Artifact Registry repo that holds the worker container image. Cloud
# Build pushes here when you run
#   gcloud builds submit discord-worker --tag=us-central1-docker.pkg.dev/<project>/discord-worker/worker:latest
# and the VM pulls from here at boot. Kept separate from
# cloud-run-source-deploy (which holds the Forum image) so the two have
# independent lifecycles and access policies.
resource "google_artifact_registry_repository" "discord_worker" {
  count         = var.use_discord ? 1 : 0
  location      = var.region
  repository_id = "discord-worker"
  format        = "DOCKER"
  description   = "Container images for the Discord Gateway worker VM"

  depends_on = [google_project_service.artifactregistry[0]]
}

# Dedicated service account for the worker VM. Each agent's Firestore
# document sets `discord_worker_service_account` to this SA's email so
# the Forum's /api/v1/discord/events/{agent_id} handler will accept
# events forwarded by this worker. With a single multi-tenant worker,
# the same email goes in every Discord-enabled agent's document.
resource "google_service_account" "discord_worker" {
  count        = var.use_discord ? 1 : 0
  account_id   = "discord-worker"
  display_name = "Discord Gateway Worker"
  description  = "Holds Discord Gateway WebSockets and forwards DMs to the Forum."

  depends_on = [google_project_service.compute[0]]
}

# The VM pulls the worker container image from this Artifact Registry repo
# at boot. COS uses the attached service account for the pull.
resource "google_artifact_registry_repository_iam_member" "discord_worker_reader" {
  count      = var.use_discord ? 1 : 0
  project    = var.project_id
  location   = google_artifact_registry_repository.discord_worker[0].location
  repository = google_artifact_registry_repository.discord_worker[0].name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.discord_worker[0].email}"
}

# Cloud Build's runtime SA needs writer access to push the worker image
# into this AR repo. `gcloud builds submit discord-worker --tag=...` is
# the canonical build command (see docs/DISCORD_WORKER.md).
#
# In projects created after Dec 2024, Cloud Build defaults to running
# under the Compute Engine default service account
# (<project_number>-compute@developer.gserviceaccount.com), NOT the
# legacy <project_number>@cloudbuild.gserviceaccount.com. We grant both
# so this works on either project vintage.
data "google_project" "this" {
  project_id = var.project_id
}

resource "google_artifact_registry_repository_iam_member" "discord_worker_writer_legacy" {
  count      = var.use_discord ? 1 : 0
  project    = var.project_id
  location   = google_artifact_registry_repository.discord_worker[0].location
  repository = google_artifact_registry_repository.discord_worker[0].name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.this.number}@cloudbuild.gserviceaccount.com"
}

resource "google_artifact_registry_repository_iam_member" "discord_worker_writer_compute" {
  count      = var.use_discord ? 1 : 0
  project    = var.project_id
  location   = google_artifact_registry_repository.discord_worker[0].location
  repository = google_artifact_registry_repository.discord_worker[0].name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.this.number}-compute@developer.gserviceaccount.com"
}

# The worker calls Cloud Run with an OIDC bearer token. We grant invoker
# explicitly so the audience check on the token passes cleanly even if
# the service ever moves to restricted ingress.
resource "google_cloud_run_v2_service_iam_member" "discord_worker_invoker" {
  count    = var.use_discord ? 1 : 0
  location = google_cloud_run_v2_service.forum.location
  name     = google_cloud_run_v2_service.forum.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.discord_worker[0].email}"
}

# The worker queries the agents collection in Firestore to discover which
# bots to maintain Gateway connections for. `datastore.user` is the right
# role for Firestore Native (Cloud Datastore is the legacy name).
resource "google_project_iam_member" "discord_worker_firestore" {
  count   = var.use_discord ? 1 : 0
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.discord_worker[0].email}"
}

# Standard observability roles so the VM and its container can write logs
# and metrics under their own identity.
resource "google_project_iam_member" "discord_worker_logging" {
  count   = var.use_discord ? 1 : 0
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.discord_worker[0].email}"
}

resource "google_project_iam_member" "discord_worker_monitoring" {
  count   = var.use_discord ? 1 : 0
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.discord_worker[0].email}"
}

# cloud-init config that runs the worker container as a systemd unit.
# This replaces the deprecated gce-container-declaration / container
# startup agent (konlet) and reproduces its behavior: authenticate to
# Artifact Registry with the VM's service account, pull the pinned image
# on every unit start (so `instances reset` picks up a repushed tag,
# same as konlet did), and restart the container on failure.
#
# COS re-runs cloud-init on every boot, so the unit file — which lives
# on the stateless /etc — is rewritten and started each time the VM
# comes up. Deprecation notice:
# https://cloud.google.com/compute/docs/deprecations/container-startup-agent-on-compute
locals {
  # Registry host (e.g. us-central1-docker.pkg.dev) extracted from the
  # image URL so docker-credential-gcr targets the right endpoint.
  discord_worker_registry = split("/", var.discord_worker_image)[0]

  discord_worker_cloud_init = <<-EOT
    #cloud-config

    write_files:
    - path: /etc/systemd/system/discord-worker.service
      permissions: "0644"
      owner: root
      content: |
        [Unit]
        Description=Discord Gateway worker container
        Wants=gcr-online.target
        After=gcr-online.target

        [Service]
        Environment="HOME=/home/discord-worker"
        ExecStartPre=/usr/bin/docker-credential-gcr configure-docker --registries=${local.discord_worker_registry}
        ExecStartPre=-/usr/bin/docker rm -f discord-worker
        ExecStartPre=/usr/bin/docker pull ${var.discord_worker_image}
        ExecStart=/usr/bin/docker run --rm --name=discord-worker \
          -e FORUM_URL=${google_cloud_run_v2_service.forum.uri} \
          -e FIRESTORE_PROJECT_ID=${var.project_id} \
          -e LOG_LEVEL=INFO \
          ${var.discord_worker_image}
        ExecStop=/usr/bin/docker stop discord-worker
        Restart=always
        RestartSec=10

    runcmd:
    # Remove any leftover konlet-era container (klt-*). Konlet baked
    # restartPolicy=Always into the container it created, so on a VM
    # migrated from gce-container-declaration the old container survives
    # on the boot disk and the docker daemon happily restarts it on
    # every boot — alongside ours, doubling every Gateway connection
    # and DM forward. Observed in prod during the 2026-07 migration.
    # TODO(2026-09): remove this cleanup step and comment once every
    # operator VM has been through the migration — it is a no-op after
    # the first post-migration boot.
    - docker ps -aq --filter name=klt- | xargs -r docker rm -f
    - systemctl daemon-reload
    - systemctl start discord-worker.service
  EOT
}

# The VM itself. Container-Optimized OS (COS) runs the worker container
# via the cloud-init systemd unit above. COS receives automatic
# security updates from Google for the OS; the container image is pinned
# and is YOUR responsibility to rebuild — see docs/DISCORD_WORKER.md.
resource "google_compute_instance" "discord_worker" {
  count        = var.use_discord ? 1 : 0
  name         = "discord-worker"
  machine_type = var.discord_worker_machine_type
  zone         = var.discord_worker_zone

  # COS auto-updates the host OS; auto-restart and live migration keep the
  # worker available through maintenance events.
  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
    preemptible         = false
  }

  boot_disk {
    initialize_params {
      # cos-stable: actively maintained Container-Optimized OS image
      # family. New images are released by Google ~monthly and this
      # config picks the latest at instance-creation time.
      image = "cos-cloud/cos-stable"
      size  = 10
      type  = "pd-standard"
    }
  }

  network_interface {
    network = "default"
    access_config {
      # Ephemeral public IP. The worker needs outbound HTTPS to
      # discord.com (Gateway) and *.run.app (Forum). It does NOT accept
      # inbound traffic; if you want to lock that down further, attach
      # a firewall tag and a deny-all-ingress rule.
    }
  }

  metadata = {
    # cloud-init runs the worker container via the systemd unit in
    # locals above. No per-agent env vars here — the worker discovers
    # its bot list from Firestore at runtime.
    user-data = local.discord_worker_cloud_init

    google-logging-enabled    = "true"
    google-monitoring-enabled = "true"
  }

  service_account {
    email = google_service_account.discord_worker[0].email
    # cloud-platform is the standard scope for service-account-driven
    # auth; the actual capabilities are constrained by the SA's IAM roles.
    scopes = ["cloud-platform"]
  }

  lifecycle {
    precondition {
      condition     = length(var.discord_worker_image) > 0
      error_message = "When use_discord is true, discord_worker_image must be set. Build the image with `gcloud builds submit discord-worker --tag=...` and pass the resulting URL."
    }
  }

  depends_on = [
    google_project_service.compute[0],
    google_project_iam_member.discord_worker_firestore[0],
    # The project denies external IPs by default. The targeted allow-list
    # entry for this VM is created via google_project_organization_policy
    # — but org policy changes propagate asynchronously and can take a
    # few minutes to take effect. The wait below forces terraform to
    # delay the VM create call until the policy has had time to settle.
    time_sleep.wait_for_discord_external_ip_policy[0],
  ]
}

# Org policies are eventually consistent — the API returns "policy created"
# immediately, but the policy isn't enforced project-wide for ~1-2 minutes.
# Without this wait, the very next google_compute_instance.create call
# fails with "Constraint constraints/compute.vmExternalIpAccess violated"
# because the new allow-list entry hasn't propagated yet.
resource "time_sleep" "wait_for_discord_external_ip_policy" {
  count           = var.use_discord ? 1 : 0
  depends_on      = [google_project_organization_policy.discord_worker_external_ip[0]]
  create_duration = "120s"
}
