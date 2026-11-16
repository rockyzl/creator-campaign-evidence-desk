#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${CLOUD_PROJECT:?Set CLOUD_PROJECT}"
: "${REPORT_BUCKET:?Set REPORT_BUCKET}"
DEPLOY_REGION="${DEPLOY_REGION:-us-central1}"
SERVICE="creator-campaign-evidence-desk"
IMAGE="$DEPLOY_REGION-docker.pkg.dev/$CLOUD_PROJECT/evidence-desk/$SERVICE:$(date -u +%Y%m%d%H%M%S)"
uv run pytest -q
test -f app/data/example-rtx-students.json
test -f app/data/example-shield-launch.json
gcloud builds submit --project "$CLOUD_PROJECT" --tag "$IMAGE" --quiet
gcloud run deploy "$SERVICE" --project "$CLOUD_PROJECT" --region "$DEPLOY_REGION" \
  --image "$IMAGE" --service-account "creator-desk@$CLOUD_PROJECT.iam.gserviceaccount.com" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$CLOUD_PROJECT,GOOGLE_CLOUD_LOCATION=global,MODEL_ID=google/gemini-3.8-flash,REPORT_BUCKET=$REPORT_BUCKET,DAILY_RUN_LIMIT=60" \
  --allow-unauthenticated --min-instances 0 --max-instances 1 --memory 512Mi --cpu 1 \
  --concurrency 8 --timeout 300 --port 8080 --quiet
