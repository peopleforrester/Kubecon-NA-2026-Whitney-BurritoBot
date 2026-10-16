# Phase 1: Foundation

**Goal:** GKE Standard cluster running with VPC, WIF, Secret Manager,
and a working kubeconfig.

**Inputs:** Empty GCP project `burritbot-kubecon-2026` (placeholder) in
region `us-west1` with admin credentials and the Vertex AI + GKE +
Container Registry APIs enabled.

**Outputs:**

- `infrastructure/terraform/main.tf` — provider block pinning `hashicorp/google`
- `infrastructure/terraform/variables.tf` — `project_id`, `region`, `cluster_name`
- `infrastructure/terraform/outputs.tf`
- `infrastructure/terraform/vpc.tf` — `google_compute_network` + `google_compute_subnetwork`
- `infrastructure/terraform/gke.tf` — GKE **Standard** cluster, not
  Autopilot, with `cluster_autoscaling` (NAP) and `workload_identity_config`
- `infrastructure/terraform/iam.tf` — `google_service_account` + bindings,
  no `google_service_account_key` resources
- `infrastructure/terraform/secret-manager.tf` — at least one
  `google_secret_manager_secret` resource
- `infrastructure/terraform/terraform.tfvars.example` — placeholder
  `project_id` / `region` values only

**Test Criteria (tests/test_phase_01_foundation.py):**

Static (must pass offline):

- `test_terraform_directory_exists`
- `test_terraform_files_present`
- `test_terraform_uses_gcp_provider`
- `test_gke_is_standard_not_autopilot`
- `test_vpc_uses_gcp_network_resources`
- `test_iam_uses_workload_identity_federation`
- `test_secret_manager_resource`
- `test_tfvars_example_has_no_real_secrets`

Live (fail, naming what is missing, when terraform / GCP auth absent):

- `test_terraform_validate` — `terraform init -backend=false` then
  `terraform validate` exit 0
- `test_terraform_plan` — `terraform plan -detailed-exitcode
  -var delivery=$BURRITBOT_DELIVERY` returns 0 or 2 and the plan labels
  the cluster and the Secret Manager secret with that slug (needs ADC,
  the GCS state bucket, and `project_id` from `terraform.tfvars` or
  `TF_VAR_project_id`)
- `test_gke_cluster_is_standard_with_wif_and_nap` — cluster API reports
  Standard mode, WIF pool set, NAP enabled
- `test_nodes_ready` — at least 2 nodes Ready
- `test_namespaces_exist` — `argocd`, `monitoring`, `security`,
  `burritbot-net`, `burritbot-unguarded`, `burritbot-guarded`, `audience`

**Key Technology Decisions:**

- GKE: **Standard** with node auto-provisioning (Autopilot is rejected
  by test — Falco DaemonSet needs privileged containers)
- Region: `us-west1` (close to SLC venue, Vertex AI + Gemini 3 Pro
  available)
- Workload Identity Federation, no JSON keys
- Secret Manager for Vertex AI credentials and Gemini API quota
- Terraform `google` provider, pinned

**Known Risk:** GKE Standard + NAP + WIF + auto-provisioning-profiles
is the exact combination Google's docs rarely show together. The NAP
`resource_limits` block is required or the cluster falls back to zero
autoscaling.

**Completion Promise:** `<promise>PHASE1_DONE</promise>`

**Skill:** none — Terraform HCL is not burritbot-specific. Refer to
the Google provider docs.

**Commits:** 3 expected (Terraform scaffold; GKE + VPC; IAM + Secret
Manager + tfvars example)
