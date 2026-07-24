#!/usr/bin/env bash
# Bootstrap GCP infrastructure for finsight STAGING (Cloud Run).
#
# Provisions: required APIs, an Artifact Registry repo, a GCS bucket for object
# storage + an HMAC key (so the app's S3 client can talk to GCS), a GitHub
# Actions deployer service account + IAM, and the Secret Manager entries the
# Cloud Run service reads at runtime.
#
# Data services live OUTSIDE GCP by design (see docs/DEPLOY-staging.md):
#   • Postgres  → Supabase (managed, pgvector)
# Sessions + rate limiting also live in that Postgres (no Redis). This script
# only asks you to paste the DB password; it does not create the database.
#
# Run interactively the FIRST time. Re-running is safe — create steps that hit
# an existing resource just warn and continue.
#
# Prereqs: gcloud CLI installed + logged in (`gcloud auth login`), openssl.

set -euo pipefail

# ─── Variables ──────────────────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:?set PROJECT_ID=your-gcp-project-id}"
REGION="asia-southeast1"
AR_REPO="finsight"
SA_NAME="github-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
BUCKET="${PROJECT_ID}-finsight-staging"   # globally unique → project-prefixed

echo "Using project: ${PROJECT_ID}"
gcloud config set project "${PROJECT_ID}" >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# ─── Helper: create-or-update a secret from stdin ───────────────────
put_secret() {
  local name="$1"
  if gcloud secrets describe "${name}" >/dev/null 2>&1; then
    gcloud secrets versions add "${name}" --data-file=- >/dev/null
    echo "  updated secret ${name}"
  else
    gcloud secrets create "${name}" --data-file=- --replication-policy=automatic >/dev/null
    echo "  created secret ${name}"
  fi
}

# ─── 1. Enable APIs ─────────────────────────────────────────────────
echo "→ Enabling APIs…"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  iamcredentials.googleapis.com

# ─── 2. Artifact Registry ───────────────────────────────────────────
echo "→ Creating Artifact Registry repo…"
gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="finsight container images" \
  || echo "  (already exists, skipping)"

# ─── 3. GCS bucket for object storage ───────────────────────────────
echo "→ Creating GCS bucket gs://${BUCKET}…"
gcloud storage buckets create "gs://${BUCKET}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --default-storage-class=STANDARD \
  || echo "  (already exists, skipping)"

# ─── 4. Deployer service account (for GitHub Actions) ───────────────
echo "→ Creating deployer service account…"
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="GitHub Actions deployer for finsight" \
  || echo "  (already exists, skipping)"

echo "→ Granting project roles to ${SA_EMAIL}…"
for ROLE in \
  roles/run.admin \
  roles/iam.serviceAccountUser \
  roles/artifactregistry.writer \
  roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" --role="${ROLE}" \
    --condition=None --quiet >/dev/null
done

# ─── 5. Runtime SA (default compute) — reach secrets + the bucket ───
echo "→ Granting runtime roles to ${RUNTIME_SA}…"
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" --condition=None --quiet >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${RUNTIME_SA}" --role="roles/storage.objectAdmin" >/dev/null

# ─── 6. GCS HMAC key (S3-compatible creds for the app's boto3 client) ─
echo "→ Creating GCS HMAC key for ${RUNTIME_SA}…"
if [[ -z "${HMAC_ACCESS_ID:-}" ]]; then
  HMAC_JSON="$(gcloud storage hmac create "${RUNTIME_SA}" --format=json)"
  HMAC_ACCESS_ID="$(echo "${HMAC_JSON}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["metadata"]["accessId"])')"
  HMAC_SECRET="$(echo "${HMAC_JSON}" | python3 -c 'import json,sys;print(json.load(sys.stdin)["secret"])')"
  echo "  created HMAC access id ${HMAC_ACCESS_ID}"
else
  echo "  (HMAC_ACCESS_ID provided via env — reusing)"
fi
printf '%s' "${HMAC_ACCESS_ID}" | put_secret finsight-staging-gcs-hmac-key
printf '%s' "${HMAC_SECRET}"    | put_secret finsight-staging-gcs-hmac-secret

# ─── 7. App secrets ─────────────────────────────────────────────────
echo "→ Generating JWT + admin secrets…"
openssl rand -base64 48 | tr -d '\n' | put_secret finsight-staging-jwt-access-secret
openssl rand -base64 48 | tr -d '\n' | put_secret finsight-staging-jwt-refresh-secret
openssl rand -base64 24 | tr -d '/+=\n' | put_secret finsight-staging-admin-password

echo ""
echo "→ Paste the Supabase DB password (input hidden):"
read -r -s -p "  Supabase DB password (PGPASSWORD): " PGPASSWORD; echo
printf '%s' "${PGPASSWORD}" | put_secret finsight-staging-pgpassword
# Sessions + rate limiting live in Postgres now — no Redis to provision.

# ─── 8. GitHub Actions deployer key ─────────────────────────────────
KEY_FILE="$(pwd)/github-deployer-key.json"
echo "→ Creating deployer SA key at ${KEY_FILE}…"
gcloud iam service-accounts keys create "${KEY_FILE}" --iam-account="${SA_EMAIL}"

cat <<EOF

═══════════════════════════════════════════════════════════════
✅ finsight staging bootstrap complete.

GCS bucket:  gs://${BUCKET}   (set STAGING_GCS_BUCKET=${BUCKET})

Next steps — GitHub → Settings → Secrets and variables → Actions:

  Secrets:
    GCP_PROJECT_ID = ${PROJECT_ID}
    GCP_SA_KEY     = (paste full contents of ${KEY_FILE})

  Variables (staging):
    STAGING_GCS_BUCKET        = ${BUCKET}
    STAGING_PGHOST            = <aws-0-<region>.pooler.supabase.com>
    STAGING_PGPORT            = 5432
    STAGING_PGUSER            = postgres.<project-ref>
    STAGING_PGDATABASE        = postgres
    STAGING_CLIENT_URL        = <frontend URL — fill after first deploy>
    STAGING_VITE_API_URL      = <backend URL — fill after first deploy>
    STAGING_VITE_GOOGLE_CLIENT_ID = <optional>
    STAGING_GOOGLE_CLIENT_ID  = <optional>

Then DELETE the local key file:
    rm ${KEY_FILE}

See docs/DEPLOY-staging.md for the two-pass URL step and how to seed the admin.
═══════════════════════════════════════════════════════════════
EOF
