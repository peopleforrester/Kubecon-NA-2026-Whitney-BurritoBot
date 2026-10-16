# Billing Export — Costing a Delivery by Label

How a burritbot delivery is costed: what Terraform labels, what an
operator sets up once by hand, and the query that fills the runbook's
Cost row.

## What Terraform labels

`infrastructure/terraform/labels.tf` defines `local.cost_labels`:

| Label key | Value |
|---|---|
| `burritbot-io_owner` | `burritbot` |
| `burritbot-io_delivery` | `var.delivery`, the delivery's slug (required, no default) |

The GKE cluster (`resource_labels`) and the Secret Manager secret carry
them. GKE copies cluster labels onto the node VMs and disks it creates,
including Node Auto-Provisioning pools. `gke.tf` also enables GKE cost
allocation (`cost_management_config`), which adds `k8s-namespace`,
`k8s-label/*`, `k8s-workload-name` and `goog-k8s-cluster-name` to the
export. That splits `burritbot-guarded` from `burritbot-unguarded`.

Each delivery applies with its own slug, so spend never mixes across
deliveries:

```bash
terraform -chdir=infrastructure/terraform apply -var delivery=<event>-<year>
```

## One-time setup, out of band

Do not put the export dataset in the Terraform module. `scripts/teardown.sh`
runs `terraform destroy` within hours of a delivery. Billing rows land
hours later and GKE cost allocation rows up to three days later, so the
dataset must outlive teardown. It is created once per billing account,
like the state bucket in `infrastructure/terraform/backend.tf.example`.

1. **Check for an existing export.** A billing account has one detailed
   usage cost export. In the console, open *Billing → Billing export →
   BigQuery export*. If *Detailed usage cost* is already on, use that
   dataset and skip to the query.

2. **Create the dataset.** This needs BigQuery User on the project that
   holds it. A multi-region (`US`) dataset gets billing data back to the
   start of the previous month the first time the export is enabled. A
   regional dataset gets nothing earlier.
   ```bash
   PROJECT_ID="REPLACE_WITH_PROJECT"
   bq mk --dataset \
     --location=US \
     --label=burritbot-io_owner:burritbot \
     --description="Cloud Billing detailed usage cost export" \
     "${PROJECT_ID}:billing_export"
   ```

3. **Enable the export.** Cloud Billing export can only be turned on in
   the console. There is no API, `gcloud` or Terraform resource for it.
   Billing Account Administrator or Billing Account Costs Manager on the
   billing account: *Billing → Billing export → BigQuery export →
   Detailed usage cost → Edit settings*, pick the project and
   `billing_export`, save. GKE cost allocation data appears only in the
   detailed export, not the standard one.

4. **Enable it before the first Night Before.** Rows are written only for
   usage after the export is on (except the multi-region backfill in
   step 2), and only for usage after cost allocation is on.

## The Cost row query

Read the Cost row at least three days after teardown, once the GKE cost
allocation rows have landed. Fill in the billing account ID, the
delivery slug, and the two times the runbook records: provisioning start
(Night Before) and teardown complete. Usage windows in the export are
hourly, so round the start down and the end up to the hour.

```sql
-- GKE: everything the cluster labelled for this delivery, by namespace.
SELECT
  (SELECT value FROM UNNEST(labels) WHERE key = 'k8s-namespace') AS namespace,
  service.description AS service,
  ROUND(SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)), 2) AS net_cost
FROM `PROJECT_ID.billing_export.gcp_billing_export_resource_v1_BILLING_ACCOUNT_ID`
WHERE EXISTS (
    SELECT 1 FROM UNNEST(labels)
    WHERE key = 'burritbot-io_delivery' AND value = 'DELIVERY_SLUG')
  AND usage_start_time >= TIMESTAMP('PROVISIONING_START')
  AND usage_start_time <  TIMESTAMP('TEARDOWN_COMPLETE')
GROUP BY namespace, service
ORDER BY net_cost DESC;

-- Vertex AI and the rest of the project in the same window, by service.
-- Model calls carry no delivery label, so this reads the project and the
-- window; other Vertex AI users of the project in that window count too.
SELECT
  service.description AS service,
  ROUND(SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)), 2) AS net_cost
FROM `PROJECT_ID.billing_export.gcp_billing_export_resource_v1_BILLING_ACCOUNT_ID`
WHERE project.id = 'PROJECT_ID'
  AND usage_start_time >= TIMESTAMP('PROVISIONING_START')
  AND usage_start_time <  TIMESTAMP('TEARDOWN_COMPLETE')
GROUP BY service
ORDER BY net_cost DESC;
```

Write the GKE total (first query) and the Vertex AI row (second query)
into the Cost row separately, as the runbook asks.
