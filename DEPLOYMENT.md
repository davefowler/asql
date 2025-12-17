# Deployment

This project deploys to:
- **Docs**: Netlify (static site from MkDocs)
- **Playground**: Railway (Flask application)

## Quick Start

### 1. Deploy Playground to Railway

1. Go to https://railway.app and create a new project
2. Connect your GitHub repository
3. Railway will automatically detect:
   - `Procfile` → runs `python playground.py`
   - `requirements.txt` → installs dependencies
4. Railway provides a public URL (e.g., `https://asql-playground-production.up.railway.app`)

### 2. Update Netlify Configuration

Update `netlify.toml` with your Railway playground URL:

```toml
[build.environment]
  PLAYGROUND_URL = "https://your-actual-railway-url.railway.app"
```

### 3. Deploy Docs to Netlify

1. Go to https://app.netlify.com
2. Connect your GitHub repository
3. Netlify automatically runs:
   - `pip install -r requirements-docs.txt && python scripts/prepare_docs.py && mkdocs build`
   - Replaces playground URLs and deploys static site

## Files Used

| File | Purpose |
|------|---------|
| `Procfile` | Railway entry point (`web: python playground.py`) |
| `requirements.txt` | Railway dependencies |
| `requirements-docs.txt` | Netlify MkDocs dependencies |
| `netlify.toml` | Netlify build config |
| `scripts/prepare_docs.py` | URL replacement for docs |

## Environment Variables

### Railway
- `PORT` - Automatically set by Railway
- `FLASK_ENV` - Set to `production` for production mode

### Netlify
- `PLAYGROUND_URL` - Your Railway playground URL

## Troubleshooting

### Playground not accessible from docs
- Verify `PLAYGROUND_URL` in `netlify.toml` matches your Railway URL
- Check Railway logs to ensure playground is running

### Docs build fails
- Check Netlify build logs for errors
- Verify `PLAYGROUND_URL` is set in `netlify.toml`

### Railway deployment fails
- Check Railway logs for dependency errors
- Verify `Procfile` and `requirements.txt` exist

## Custom Domain (Railway)

1. Go to your Railway project settings → Domains
2. Add your custom domain (e.g., `playground.asql.dev`)
3. Configure DNS as instructed by Railway
