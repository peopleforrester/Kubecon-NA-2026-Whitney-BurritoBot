# ABOUTME: GKE Standard cluster with Node Auto-Provisioning and Workload Identity.
# ABOUTME: Autopilot is explicitly off — Falco DaemonSet requires privileged containers.

resource "google_container_cluster" "burritbot" {
  name     = var.cluster_name
  location = var.region

  # GKE Standard: Autopilot is intentionally NOT enabled. Falco DaemonSet
  # needs privileged containers, which Autopilot forbids. The
  # `enable_autopilot` field is deliberately omitted — google provider v7
  # treats any presence of that field (even `= false`) as Autopilot-aware
  # and flags conflicts with network_policy / remove_default_node_pool /
  # addons_config.network_policy_config. Standard is the default.

  # Cluster labels propagate to the node VMs, boot disks and persistent
  # disks GKE creates, so the delivery's GKE spend sums by label in the
  # billing export (docs/BILLING-EXPORT.md).
  resource_labels = merge(local.cost_labels, {
    "burritbot-io_layer" = "foundation"
  })

  # GKE cost allocation adds k8s-namespace and k8s-label/* to the export's
  # labels, which splits burritbot-guarded spend from burritbot-unguarded.
  cost_management_config {
    enabled = true
  }

  network    = google_compute_network.burritbot.id
  subnetwork = google_compute_subnetwork.burritbot.id

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  # Workload Identity Federation — no JSON service-account keys anywhere.
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Node Auto-Provisioning with resource limits (required, otherwise NAP is
  # inert). These limits are conservative demo-day budgets.
  cluster_autoscaling {
    enabled = true

    auto_provisioning_defaults {
      service_account = google_service_account.nodes.email
      oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]

      management {
        auto_repair  = true
        auto_upgrade = true
      }

      shielded_instance_config {
        enable_secure_boot          = true
        enable_integrity_monitoring = true
      }
    }

    resource_limits {
      resource_type = "cpu"
      minimum       = 4
      maximum       = 32
    }

    resource_limits {
      resource_type = "memory"
      minimum       = 16
      maximum       = 128
    }
  }

  release_channel {
    channel = "REGULAR"
  }

  # GKE owns the Gateway API CRDs (the #57 GKE Gateway needs its controller);
  # crds.gatewayAPI.enabled is false in gitops/apps/envoy-gateway-crds.yaml.
  # GKE installs the standard channel only, at the bundle its version ships.
  gateway_api_config {
    channel = "CHANNEL_STANDARD"
  }

  # 1.35.2-gke.1842000 is the first GKE with the Gateway API v1.5.0 bundle,
  # the newest GKE ships. The floor the manifests need is 1.34.1-gke.1822000
  # (v1.4.0, BackendTLSPolicy v1; tests/test_gateway_api_crd_owner.py). The
  # Envoy Gateway v1.9 matrix lists Gateway API v1.6.1, so this runs off the
  # matrix by decision (decisions.md, question 206); the live CRD checks
  # cover what the cluster actually installs.
  min_master_version = "1.35.2-gke.1842000"

  # Private nodes: workers get no public IPs (egress via Cloud NAT in vpc.tf).
  # enable_private_endpoint = false leaves the control-plane API reachable
  # from the operator's allow-listed CIDRs via master_authorized_networks
  # below. Flipping to true would lock the control plane to the VPC only.
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.master_ipv4_cidr_block
  }

  # Restrict who can hit the control plane API. Default keeps it closed
  # to literally nothing; operator overrides via terraform.tfvars before
  # the first apply.
  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.master_authorized_cidrs
      content {
        cidr_block   = cidr_blocks.value.cidr_block
        display_name = cidr_blocks.value.display_name
      }
    }
  }

  # Initial node pool is removed — NAP provisions the real pools. GKE
  # requires a default pool exist at creation, so we create a minimal one
  # and then remove it in a follow-up.
  initial_node_count       = 1
  remove_default_node_pool = true

  # Dataplane V2 (Cilium-based) enforces NetworkPolicy natively. Do not add
  # a network_policy {} block or addons_config.network_policy_config: the
  # legacy Calico path is mutually exclusive with ADVANCED_DATAPATH and the
  # GKE API rejects the combination at apply time (plan stays green).
  datapath_provider = "ADVANCED_DATAPATH"

  addons_config {
    http_load_balancing {
      disabled = false
    }
    horizontal_pod_autoscaling {
      disabled = false
    }
  }

  logging_config {
    enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"]
  }

  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
    managed_prometheus {
      enabled = true
    }
  }

  deletion_protection = false
}
