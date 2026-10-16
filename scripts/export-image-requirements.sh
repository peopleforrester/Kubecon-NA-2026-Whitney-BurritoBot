#!/usr/bin/env bash
# ABOUTME: Writes each image's hashed requirements.txt from uv.lock, one image-* dependency group per image.
# ABOUTME: Run after `uv lock` changes; tests/test_image_dependency_lock.py fails on a stale export.
set -euo pipefail

cd "$(dirname "$0")/.."

# group:requirements path; keep in step with tests/helpers/image_requirements.py IMAGES.
IMAGES=(
  "image-burritbot:apps/burritbot/requirements.txt"
  "image-audience-frontend:apps/audience-frontend/backend/requirements.txt"
  "image-extproc:ai-gateway/extproc/requirements.txt"
)

for entry in "${IMAGES[@]}"; do
  group="${entry%%:*}"
  path="${entry#*:}"
  # stdout, not --output-file, so the header uv writes is the command the test runs.
  uv export --frozen --only-group "$group" --no-emit-project > "$path"
  echo "export-image-requirements: $group -> $path"
done
