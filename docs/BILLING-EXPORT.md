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

## What the model calls carry

Every Vertex AI request burritbot makes carries the same two labels, so
model spend sums by `burritbot-io_delivery` like the cluster's. There
are three call sites:

- **Unguarded BurritBot** (`apps/burritbot/app.py`) sets `labels` on each
  `generateContent` request. It reads the slug from `BURRITBOT_DELIVERY`.
  If that is unset or is not a label value, `/chat` returns `502` naming
  it, and no unlabelled call is sent.
- **The AI gateway** carries guarded BurritBot's call. Its OpenAI →
  Vertex AI translator has no `labels` field, so the `vertex-ai-gemini`
  AIServiceBackend sets them with a `bodyMutation`, which runs on the
  translated body.
- **NeMo Guardrails** passes each `vertexai` model's `parameters` to
  LangChain's `ChatVertexAI`, which sends `labels`. NeMo does not expand
  `${VAR}` in `config.yaml`, so the slug is written in.

The platform tree names no delivery. The gateway and NeMo manifests
carry a placeholder that is too long to be a label value. Each delivery
has a Kustomize overlay under `presentations/<event>/deploy/`
(`burritbot/` and `ai-gateway/`) that writes its slug into all three
places. The ArgoCD `burritbot` and `ai-gateway` Applications sync the
active delivery's overlay. A sync of the bare platform has its guarded
model calls refused and its unguarded `/chat` answered with a `502`, so
no call is ever billed under the wrong delivery. The slug in the overlay
must be the one Terraform applies with. `tests/test_delivery_overlay.py`
holds the overlay to the runbook's `-var delivery=`.

To present at a new delivery, copy the two overlay directories to
`presentations/<new-event>/deploy/`, change the slug in their three
patches, and point the two Applications at them. The NeMo patch holds
the whole `config.yaml`, so when `ai-gateway/nemo-guardrails/config.yaml`
changes, the patch must change with it. The test fails until they match.

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
-- GKE: everything labelled for this delivery except the model calls, by namespace.
SELECT
  (SELECT value FROM UNNEST(labels) WHERE key = 'k8s-namespace') AS namespace,
  service.description AS service,
  ROUND(SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)), 2) AS net_cost
FROM `PROJECT_ID.billing_export.gcp_billing_export_resource_v1_BILLING_ACCOUNT_ID`
WHERE EXISTS (
    SELECT 1 FROM UNNEST(labels)
    WHERE key = 'burritbot-io_delivery' AND value = 'DELIVERY_SLUG')
  AND service.description != 'Vertex AI'
  AND usage_start_time >= TIMESTAMP('PROVISIONING_START')
  AND usage_start_time <  TIMESTAMP('TEARDOWN_COMPLETE')
GROUP BY namespace, service
ORDER BY net_cost DESC;

-- Vertex AI: the model calls labelled for this delivery, by SKU. Other
-- Vertex AI users of the shared project carry no burritbot label, so they
-- are not counted.
SELECT
  sku.description AS sku,
  ROUND(SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)), 2) AS net_cost
FROM `PROJECT_ID.billing_export.gcp_billing_export_resource_v1_BILLING_ACCOUNT_ID`
WHERE EXISTS (
    SELECT 1 FROM UNNEST(labels)
    WHERE key = 'burritbot-io_delivery' AND value = 'DELIVERY_SLUG')
  AND service.description = 'Vertex AI'
  AND usage_start_time >= TIMESTAMP('PROVISIONING_START')
  AND usage_start_time <  TIMESTAMP('TEARDOWN_COMPLETE')
GROUP BY sku
ORDER BY net_cost DESC;
```

Write the GKE total (first query) and the Vertex AI total (second query)
into the Cost row separately, as the runbook asks. Both split on the
service name `Vertex AI`. If the second query returns nothing while the
model was in use, look for the model's rows under another service name
in the first query's output.

Labels on the model calls start with the first delivery whose overlay
carries them. For spend from before then, read Vertex AI by project and
window instead (`project.id = 'PROJECT_ID'` in place of the label
filter). Other Vertex AI users of the project in that window count too.
