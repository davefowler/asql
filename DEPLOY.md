# Deploying asql

The docs site is on Netlify; the playground is on Railway. Both deploy on push to `main`.

| What | Runs on | Does |
|---|---|---|
| Netlify (`netlify.toml`) | pushes to `main`, PR deploy previews | Builds the mkdocs site and publishes it to `analyticsql.com` |
| `ci.yml` | PRs, pushes to `main` | `just test`, `just smoke`, `just lint` (ruff, mypy, ESLint), and a build-only `docker build` |
| `docs.yml` | PRs, pushes to `main` | Build-only check of the mkdocs site |
| Railway (`railway.json`) | pushes to `main` touching `asql/`, `Dockerfile`, or the lockfile | Builds the `Dockerfile` and deploys the playground to `play.analyticsql.com` |

## Docs site (Netlify)

The Netlify site `asql` is linked to this repo and builds with the command in
`netlify.toml` (uv provisions Python 3.13). Every PR gets a deploy preview.

Custom domain `analyticsql.com` is set on the Netlify site. DNS (GoDaddy):

- apex `analyticsql.com`: `A 75.2.60.5` (Netlify's load balancer)
- `www.analyticsql.com`: `CNAME asql.netlify.app`

Netlify issues the Let's Encrypt certificate once DNS resolves to it.

`mkdocs.yml` keeps `use_directory_urls: false`, so page URLs stay in the
`/syntax/pipe.html` form every existing link uses.

## Playground (Railway)

Railway builds the `Dockerfile` (config in `railway.json`) and sets `$PORT`.
The healthcheck is `GET /`.

One-time setup:

1. railway.com → **New Project → Deploy from GitHub repo → `davefowler/asql`**.
2. Service → **Settings → Networking → Generate Domain** to get a
   `*.up.railway.app` URL, then **Custom Domain → `play.analyticsql.com`**
   (port 8080) and add the `CNAME` it shows at GoDaddy.

The playground links to `https://analyticsql.com` and
`https://play.analyticsql.com` by default; override with the `DOCS_URL` and
`PLAYGROUND_URL` service variables.

## Releases

Version lives in `pyproject.toml`. Tag `vX.Y.Z` on `main`; publishing to PyPI
is a manual step.
