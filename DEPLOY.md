# Deploying asql

Three GitHub Actions workflows own everything:

| Workflow | Runs on | Does |
|---|---|---|
| `ci.yml` | PRs, pushes to `main` | `just test`, `just smoke`, `just lint` (ruff, mypy, ESLint), and a build-only `docker build` |
| `docs.yml` | PRs (build only), pushes to `main` (build + publish) | Builds the mkdocs site and publishes it to GitHub Pages |
| `deploy-playground.yml` | pushes to `main`, manual | Builds the playground image, pushes it to Artifact Registry, deploys it to Cloud Run. Skipped until `GCP_PROJECT_ID` is set |

## Docs site (GitHub Pages)

One-time setup:

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. Push to `main` (or run `docs.yml` manually). The site appears at
   `https://davefowler.github.io/asql/`.
3. Custom domain: **Settings → Pages → Custom domain → `analyticsql.com`**,
   then point DNS at GitHub Pages:
   - apex `analyticsql.com`: `A` records `185.199.108.153`, `185.199.109.153`,
     `185.199.110.153`, `185.199.111.153` (and `AAAA` `2606:50c0:8000::153`,
     `2606:50c0:8001::153`, `2606:50c0:8002::153`, `2606:50c0:8003::153`)
   - `www.analyticsql.com`: `CNAME davefowler.github.io`
4. Once the certificate is issued, tick **Enforce HTTPS**.

`mkdocs.yml` keeps `use_directory_urls: false`, so page URLs stay in the
`/syntax/pipe.html` form every existing link uses.

## Playground (Cloud Run)

The workflow authenticates with Workload Identity Federation (no JSON keys)
and reads only repository **variables** (Settings → Secrets and variables →
Actions → Variables). None of these values is a secret.

| Variable | Example |
|---|---|
| `GCP_PROJECT_ID` | `my-asql-project` |
| `GCP_REGION` | `us-west1` |
| `CLOUD_RUN_SERVICE` | `asql-playground` |
| `ARTIFACT_REPO` | `asql` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/123456789/locations/global/workloadIdentityPools/github/providers/github` |
| `GCP_SERVICE_ACCOUNT` | `asql-deployer@my-asql-project.iam.gserviceaccount.com` |

One-time GCP setup (replace the placeholders):

```bash
PROJECT=my-asql-project
REGION=us-west1
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')

gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  iamcredentials.googleapis.com --project "$PROJECT"

gcloud artifacts repositories create asql --repository-format docker \
  --location "$REGION" --project "$PROJECT"

gcloud iam service-accounts create asql-deployer --project "$PROJECT"
SA="asql-deployer@$PROJECT.iam.gserviceaccount.com"
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member "serviceAccount:$SA" --role "$role"
done

gcloud iam workload-identity-pools create github --location global --project "$PROJECT"
gcloud iam workload-identity-pools providers create-oidc github \
  --location global --workload-identity-pool github --project "$PROJECT" \
  --issuer-uri https://token.actions.githubusercontent.com \
  --attribute-mapping 'google.subject=assertion.sub,attribute.repository=assertion.repository' \
  --attribute-condition "assertion.repository == 'davefowler/asql'"

gcloud iam service-accounts add-iam-policy-binding "$SA" --project "$PROJECT" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/davefowler/asql"
```

Then set the six variables and run **Actions → Deploy playground → Run
workflow**. The service is deployed with `--allow-unauthenticated` (the
playground is public).

Custom domain `play.analyticsql.com`: map it to the service
(`gcloud beta run domain-mappings create --service asql-playground
--domain play.analyticsql.com --region "$REGION"`, or a load balancer in
regions without domain mappings) and add the DNS record it prints.

The playground links to `https://analyticsql.com` and
`https://play.analyticsql.com` by default; override with the `DOCS_URL` and
`PLAYGROUND_URL` environment variables on the Cloud Run service.

## Releases

Version lives in `pyproject.toml`. Tag `vX.Y.Z` on `main`; publishing to PyPI
is a manual step.
