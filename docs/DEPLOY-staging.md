# Deploying finsight to GCP Cloud Run (staging)

Modelled on `Exakairos/code/mirai-platform`. Compute runs on **Cloud Run**;
the data services are managed and live outside GCP:

| Concern | Staging choice |
|---|---|
| Frontend / Backend compute | Cloud Run (2 services) |
| Container images | Artifact Registry (`asia-southeast1`) |
| Postgres (+pgvector) | **Supabase** (managed) |
| Sessions + rate limiting | **Postgres** (same Supabase DB — no separate Redis) |
| Object storage | **GCS bucket** via its S3-compatible endpoint + HMAC key |
| Secrets | Secret Manager |
| CI/CD | GitHub Actions (`.github/workflows/deploy.yml`) |

The backend runs DB migrations and ensures the storage bucket **on boot**
(`app/main.py` lifespan), so there's no separate migrate step.

---

## One-time setup

### 1. Create the managed data services
- **Supabase**: new project → Connect → **Session pooler**. Note the host
  (`aws-0-<region>.pooler.supabase.com`), user (`postgres.<project-ref>`),
  db (`postgres`), and the database password. pgvector is available; the
  boot migration enables it.

> No Redis to set up: revocable sessions and rate-limit counters live in
> Postgres (`sessions` / `rate_limits` tables, created by the boot migration).
> If you later outgrow that, reintroduce Redis for just those two paths.

### 2. Bootstrap GCP
```bash
gcloud auth login
PROJECT_ID=your-gcp-project ./scripts/bootstrap-gcp.sh
```
This enables APIs, creates the Artifact Registry repo, a GCS bucket + HMAC key,
the `github-deployer` service account, and the Secret Manager entries. It will
prompt you to paste the Supabase database password. It prints the
exact GitHub secrets/variables to set — then delete the emitted key file.

### 3. Configure GitHub
Repo → Settings → Secrets and variables → Actions.
- **Secrets**: `GCP_PROJECT_ID`, `GCP_SA_KEY` (the deployer key JSON).
- **Variables** (`STAGING_*`): `GCS_BUCKET`, `PGHOST`, `PGPORT`, `PGUSER`,
  `PGDATABASE`, and (after the first deploy) `CLIENT_URL`, `VITE_API_URL`.
  Optional: `VITE_GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_ID`.

### 4. First deploy (two-pass, because URLs aren't known until services exist)
1. Push to `main` (or run the workflow manually). The frontend build will bake
   an empty `VITE_API_URL` on this first pass — that's expected.
2. The deploy step prints both service URLs. Set:
   - `STAGING_VITE_API_URL` = backend URL
   - `STAGING_CLIENT_URL`   = frontend URL
3. Re-run the workflow. Now the frontend points at the real API and the
   backend's CORS + refresh-cookie origin match the real frontend.

> **Custom domains** avoid the two-pass dance: map stable domains to both
> services, set the two Variables to those, and you never touch them again.

### 5. Seed the admin user
Migrations create the schema but not the admin login. Run the existing seed
against Supabase once (locally, with staging PG env pointing at Supabase):
```bash
# from backend/, with staging PG* + ADMIN_EMAIL/ADMIN_PASSWORD exported
./infrastructure/scripts/seed.sh   # or the seed entrypoint the repo uses
```

---

## How config flows
- **Non-secret** values → GitHub **Variables** → `envsubst` into
  `infra/cloudrun/backend-staging.yaml` at deploy time.
- **Secrets** → Secret Manager, referenced by `secretKeyRef` in the manifest,
  mounted at container start.
- **Frontend** `VITE_*` are **build-time** args baked into the JS bundle (they
  reach every browser — never put a secret there).

## The cross-site refresh cookie
Frontend and backend are different Cloud Run domains, so the httpOnly refresh
cookie is cross-site. The manifest sets `COOKIE_SAMESITE=none` and the backend
auto-forces `Secure` (browser requirement). Locally the default stays `lax`.

## Object storage (GCS via S3 API)
The app's boto3 client is pointed at `https://storage.googleapis.com` with
path-style addressing and the HMAC key/secret as `MINIO_ROOT_USER/PASSWORD`.
No code change — GCS's interoperability API speaks S3.

## Add OpenAI later (optional)
The news→insight pipeline's LLM steps are skipped without a key. To enable:
```bash
printf '%s' "$OPENAI_API_KEY" | gcloud secrets create finsight-staging-openai-api-key --data-file=- --replication-policy=automatic
gcloud run services update finsight-backend-staging --region=asia-southeast1 \
  --update-secrets OPENAI_API_KEY=finsight-staging-openai-api-key:latest
```

## Cost note
Cloud Run scales to zero (pay per request). Supabase has a free tier. The only
always-on cost is Artifact Registry storage (cents) + the GCS bucket. No Redis
bill — sessions and rate limits share the Postgres you already have.

## Hard cost cap (`infra/budget-guard/`)

A GCP budget is only an **alert** — it never stops spending. `infra/budget-guard/`
is a Cloud Function that makes the cap real: a **$10** Cloud Billing budget on the
project publishes to the `finsight-budget-alerts` Pub/Sub topic, and when actual
cost reaches the budget the function **unlinks the billing account**, which halts
every billable resource (Cloud Run stops serving). The function's runtime SA has
`roles/billing.projectManager` so it can do this.

If the cap ever trips, staging goes offline (by design). Investigate, then
re-enable:

```bash
gcloud billing projects link finsight-staging --billing-account=<ACCOUNT_ID>
```

Change the cap amount by editing the budget:
`gcloud billing budgets list --billing-account=<ID>` → `budgets update …`.
