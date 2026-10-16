# ABOUTME: Terraform outputs — exposes cluster endpoint, WIF pool, and SA emails.
# ABOUTME: Consumed by downstream ArgoCD bootstrap and the Phase 1 live tests.

output "cluster_name" {
  description = "Name of the deployed GKE cluster."
  value       = google_container_cluster.burritbot.name
}

output "cluster_endpoint" {
  description = "GKE cluster API endpoint."
  value       = google_container_cluster.burritbot.endpoint
  sensitive   = true
}

output "cluster_location" {
  description = "Regional location of the GKE cluster."
  value       = google_container_cluster.burritbot.location
}

output "workload_identity_pool" {
  description = "Workload Identity Federation pool for the cluster."
  value       = google_container_cluster.burritbot.workload_identity_config[0].workload_pool
}

output "workload_service_account_email" {
  description = "Email of the WIF-bound workload service account."
  value       = google_service_account.workload.email
}

output "ai_gateway_service_account_email" {
  description = "Email of the WIF-bound Envoy AI Gateway service account that calls Vertex AI."
  value       = google_service_account.ai_gateway.email
}

output "node_service_account_email" {
  description = "Email of the node service account attached to the GKE nodes."
  value       = google_service_account.nodes.email
}

output "vertex_secret_name" {
  description = "Fully-qualified Secret Manager secret name for Vertex AI metadata."
  value       = google_secret_manager_secret.vertex_ai.name
}
