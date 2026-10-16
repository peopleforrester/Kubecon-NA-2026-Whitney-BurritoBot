# ABOUTME: Phase 1 Foundation tests for GKE Standard + NAP, VPC, WIF, Secret Manager.
# ABOUTME: Mix of static HCL assertions and live GCP / cluster checks (marked @pytest.mark.live).

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import (
    CLUSTER_NAME,
    EXPECTED_NAMESPACES,
    GCP_PROJECT_ID,
    GCP_REGION,
    TERRAFORM_DIR,
)
from helpers.gcp_helpers import (
    cluster_has_node_auto_provisioning,
    cluster_has_workload_identity,
    cluster_is_standard,
    gke_cluster_name,
)


pytestmark = pytest.mark.phase1


# --- Static HCL assertions — run without Terraform installed ----------------


def _tf_files() -> list[Path]:
    return sorted(TERRAFORM_DIR.glob("*.tf")) if TERRAFORM_DIR.exists() else []


@pytest.mark.static
def test_terraform_directory_exists() -> None:
    """infrastructure/terraform/ exists."""
    assert TERRAFORM_DIR.is_dir(), f"{TERRAFORM_DIR} does not exist"


@pytest.mark.static
def test_terraform_files_present() -> None:
    """Terraform scaffold contains main/variables/outputs/gke/vpc/iam/secret-manager."""
    names = {p.name for p in _tf_files()}
    required = {
        "main.tf",
        "variables.tf",
        "outputs.tf",
        "gke.tf",
        "vpc.tf",
        "iam.tf",
        "secret-manager.tf",
    }
    missing = required - names
    assert not missing, f"Missing Terraform files: {sorted(missing)}"


@pytest.mark.static
def test_terraform_uses_gcp_provider() -> None:
    """main.tf references the google provider, not aws."""
    main = TERRAFORM_DIR / "main.tf"
    assert main.exists(), "main.tf is missing"
    text = main.read_text(encoding="utf-8")
    assert 'source  = "hashicorp/google"' in text or '"hashicorp/google"' in text, (
        "main.tf does not reference the hashicorp/google provider"
    )
    assert "hashicorp/aws" not in text, "main.tf still references hashicorp/aws"


@pytest.mark.static
def test_gke_is_standard_not_autopilot() -> None:
    """gke.tf declares GKE Standard with node auto-provisioning (not Autopilot)."""
    gke = TERRAFORM_DIR / "gke.tf"
    assert gke.exists(), "gke.tf is missing"
    text = gke.read_text(encoding="utf-8")
    assert "google_container_cluster" in text, "gke.tf has no google_container_cluster"
    assert "enable_autopilot = true" not in text, (
        "gke.tf enables Autopilot — must be Standard for Falco DaemonSet support"
    )
    assert "cluster_autoscaling" in text, (
        "gke.tf does not configure node auto-provisioning via cluster_autoscaling"
    )
    assert "workload_identity_config" in text, (
        "gke.tf does not configure Workload Identity Federation"
    )


@pytest.mark.static
def test_vpc_uses_gcp_network_resources() -> None:
    """vpc.tf uses google_compute_network + google_compute_subnetwork."""
    vpc = TERRAFORM_DIR / "vpc.tf"
    assert vpc.exists(), "vpc.tf is missing"
    text = vpc.read_text(encoding="utf-8")
    assert "google_compute_network" in text, "vpc.tf does not declare a google_compute_network"
    assert "google_compute_subnetwork" in text, "vpc.tf does not declare a google_compute_subnetwork"
    assert "aws_vpc" not in text, "vpc.tf still references aws_vpc"


@pytest.mark.static
def test_iam_uses_workload_identity_federation() -> None:
    """iam.tf wires Workload Identity Federation, not service-account keys."""
    iam = TERRAFORM_DIR / "iam.tf"
    assert iam.exists(), "iam.tf is missing"
    text = iam.read_text(encoding="utf-8")
    assert "google_service_account" in text, "iam.tf has no google_service_account"
    assert "google_project_iam_member" in text, "iam.tf has no google_project_iam_member"
    assert "google_service_account_key" not in text, (
        "iam.tf creates a service-account key — WIF only, no JSON keys"
    )


@pytest.mark.static
def test_secret_manager_resource() -> None:
    """secret-manager.tf declares at least one google_secret_manager_secret."""
    sm = TERRAFORM_DIR / "secret-manager.tf"
    assert sm.exists(), "secret-manager.tf is missing"
    text = sm.read_text(encoding="utf-8")
    assert "google_secret_manager_secret" in text, (
        "secret-manager.tf declares no google_secret_manager_secret resources"
    )


@pytest.mark.static
def test_tfvars_example_has_no_real_secrets() -> None:
    """terraform.tfvars.example uses placeholder project_id, not a live ID."""
    example = TERRAFORM_DIR / "terraform.tfvars.example"
    assert example.exists(), "terraform.tfvars.example is missing"
    text = example.read_text(encoding="utf-8")
    assert "project_id" in text, "terraform.tfvars.example must declare project_id"
    assert "region" in text, "terraform.tfvars.example must declare region"


# --- Live Terraform checks (fail when terraform is not installed) -----------


@pytest.mark.live
def test_terraform_validate() -> None:
    """`terraform validate` passes with no errors."""
    if shutil.which("terraform") is None:
        pytest.fail("terraform is not on PATH; the live Terraform checks need it installed")
    result = subprocess.run(
        ["terraform", "validate"],
        cwd=TERRAFORM_DIR,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"terraform validate failed: {result.stderr}"


@pytest.mark.live
def test_terraform_plan() -> None:
    """`terraform plan` produces no errors (exit 0 or 2)."""
    if shutil.which("terraform") is None:
        pytest.fail("terraform is not on PATH; the live Terraform checks need it installed")
    result = subprocess.run(
        ["terraform", "plan", "-detailed-exitcode"],
        cwd=TERRAFORM_DIR,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode in (0, 2), f"terraform plan failed: {result.stderr}"


# --- Live GCP and cluster assertions ----------------------------------------


@pytest.mark.live
def test_gke_cluster_is_standard_with_wif_and_nap(gcp_container_client) -> None:
    """GKE cluster is Standard with Workload Identity and node auto-provisioning."""
    cluster_path = gke_cluster_name(GCP_PROJECT_ID, GCP_REGION, CLUSTER_NAME)
    cluster = gcp_container_client.get_cluster(name=cluster_path)
    assert cluster_is_standard(cluster), "Cluster is Autopilot — must be Standard"
    assert cluster_has_workload_identity(cluster), "Cluster has no Workload Identity pool"
    assert cluster_has_node_auto_provisioning(cluster), "Node auto-provisioning not enabled"


@pytest.mark.live
def test_nodes_ready(k8s_core_v1) -> None:
    """At least 2 nodes are in Ready state."""
    nodes = k8s_core_v1.list_node()
    ready = [
        node.metadata.name
        for node in nodes.items
        for cond in (node.status.conditions or [])
        if cond.type == "Ready" and cond.status == "True"
    ]
    assert len(ready) >= 2, f"Expected 2+ Ready nodes, got {len(ready)}: {ready}"


@pytest.mark.live
def test_namespaces_exist(k8s_core_v1) -> None:
    """All expected burritbot namespaces exist."""
    namespaces = k8s_core_v1.list_namespace()
    ns_names = {ns.metadata.name for ns in namespaces.items}
    missing = [ns for ns in EXPECTED_NAMESPACES if ns not in ns_names]
    assert not missing, f"Missing namespaces: {missing}"
