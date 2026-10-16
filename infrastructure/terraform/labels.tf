# ABOUTME: Cost labels every labelled burritbot GCP resource carries into the billing export.
# ABOUTME: burritbot-io_delivery names the delivery, so one talk's spend sums by label.

locals {
  # GCP label keys allow no dots, so `burritbot.io/x` is spelled
  # `burritbot-io_x`, as on the Secret Manager secret. Query these in the
  # Cloud Billing export; see docs/BILLING-EXPORT.md.
  cost_labels = {
    "burritbot-io_owner"    = "burritbot"
    "burritbot-io_delivery" = var.delivery
  }
}
