#!/bin/bash
set -e

# Load env vars
set -a
source "$(dirname "$0")/../.env"
set +a

PROJECT_ID="${GCP_PROJECT_ID:-autoroad-479522}"
REGION="${GCP_REGION:-us-west1}"
SERVICE_NAME="autoroad-worker-slow"
IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "=== Nuking existing service and failed revisions ==="
# Delete the service entirely - this removes all revisions including failed ones
gcloud run services delete "$SERVICE_NAME" --region="$REGION" --quiet 2>/dev/null || true

# Also delete any orphaned revisions that might be hanging around
for rev in $(gcloud run revisions list --region="$REGION" --filter="metadata.name~$SERVICE_NAME" --format="value(name)" 2>/dev/null); do
  echo "  Deleting orphaned revision: $rev"
  gcloud run revisions delete "$rev" --region="$REGION" --quiet 2>/dev/null || true
done

echo "Waiting for quota to release..."
sleep 5

echo ""
echo "=== Building Docker image ==="
cd "$(dirname "$0")/.."
docker build --platform linux/amd64 -f cloudrun_worker/Dockerfile -t "$IMAGE" .

echo ""
echo "=== Pushing to GCR ==="
docker push "$IMAGE"

echo ""
echo "=== Deploying to Cloud Run ==="
gcloud run deploy "$SERVICE_NAME" \
  --image "$IMAGE" \
  --platform managed \
  --region "$REGION" \
  --cpu 8 \
  --memory 4Gi \
  --timeout 120 \
  --concurrency 1 \
  --max-instances 2 \
  --cpu-boost \
  --set-secrets "REDIS_URL=redis-url:latest" \
  --allow-unauthenticated

echo "Done! Service URL:"
gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format 'value(status.url)'
