#!/bin/bash
set -e

PROJECT_ID="autoroad-479522"

echo "This script sets up secrets for the autoroad worker."
echo "Only run this once, or to rotate secrets."
echo ""

# Enable Secret Manager API
echo "Enabling Secret Manager API..."
gcloud services enable secretmanager.googleapis.com --project="$PROJECT_ID"

# Generate worker secret
WORKER_SECRET=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
echo "Generated worker secret: $WORKER_SECRET"
echo ""
echo "Save this! You'll need it for your server config:"
echo "  WORKER_SECRET=$WORKER_SECRET"
echo ""

# Prompt for Redis URL
read -p "Enter Redis URL (redis://user:pass@host:port): " REDIS_URL

# Create or update secrets
echo "Creating worker-secret..."
if gcloud secrets describe worker-secret --project="$PROJECT_ID" &>/dev/null; then
  printf '%s' "$WORKER_SECRET" | gcloud secrets versions add worker-secret --data-file=- --project="$PROJECT_ID"
else
  printf '%s' "$WORKER_SECRET" | gcloud secrets create worker-secret --data-file=- --project="$PROJECT_ID"
fi

echo "Creating redis-url..."
if gcloud secrets describe redis-url --project="$PROJECT_ID" &>/dev/null; then
  printf '%s' "$REDIS_URL" | gcloud secrets versions add redis-url --data-file=- --project="$PROJECT_ID"
else
  printf '%s' "$REDIS_URL" | gcloud secrets create redis-url --data-file=- --project="$PROJECT_ID"
fi

# Grant Cloud Run access
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
SERVICE_ACCOUNT="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

echo "Granting Cloud Run access to secrets..."
gcloud secrets add-iam-policy-binding worker-secret \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID" \
  --quiet

gcloud secrets add-iam-policy-binding redis-url \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor" \
  --project="$PROJECT_ID" \
  --quiet

echo ""
echo "Done! Secrets configured."
echo ""
echo "For your server, set these environment variables:"
echo "  WORKER_URL=https://autoroad-worker-$PROJECT_NUMBER.$REGION.run.app"
echo "  WORKER_SECRET=$WORKER_SECRET"
echo "  USE_WORKERS=true"
