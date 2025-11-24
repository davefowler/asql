# Railway Deployment Guide

This guide explains how to deploy the ASQL Playground to Railway.

## Prerequisites

- A Railway account (sign up at https://railway.app)
- Git repository connected to Railway

## Deployment Steps

### 1. Create a New Railway Project

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo" (or use Railway CLI)
4. Select your repository

### 2. Configure the Service

Railway will automatically detect the `Procfile` and `requirements.txt` files.

### 3. Set Environment Variables (Optional)

Railway will automatically:
- Set `PORT` environment variable (required)
- Set `FLASK_ENV=production` in production

You can optionally set:
- `FLASK_ENV`: Set to `production` for production mode (defaults to development)

### 4. Deploy

Railway will automatically:
1. Install dependencies from `requirements.txt`
2. Run the web process from `Procfile` (which runs `python playground.py`)
3. Expose the service on a public URL

### 5. Get Your Playground URL

After deployment, Railway will provide a public URL like:
- `https://asql-playground-production.up.railway.app`

Or if you set a custom domain:
- `https://playground.asql.dev`

### 6. Update Netlify Docs

Update the `PLAYGROUND_URL` in `netlify.toml` to point to your Railway playground URL:

```toml
[build.environment]
  PLAYGROUND_URL = "https://your-playground-url.railway.app"
```

Then redeploy your docs on Netlify.

## File Structure

The following files are used for Railway deployment:

- `Procfile`: Defines the web process (`web: python playground.py`)
- `requirements.txt`: Python dependencies for the playground
- `playground.py`: The Flask application

## Troubleshooting

### Port Issues

Railway automatically sets the `PORT` environment variable. The playground code reads this:
```python
port = int(os.environ.get('PORT', 5001))
```

If you see port errors, make sure Railway is setting `PORT` correctly.

### Dependencies Not Installing

Make sure `requirements.txt` includes all necessary dependencies:
- `flask>=2.0.0`
- `sqlglot>=24.0.0`

### Playground Not Loading

1. Check Railway logs for errors
2. Verify the service is running (green status)
3. Check that the public URL is accessible
4. Verify CORS settings if accessing from a different domain

## Custom Domain

To set up a custom domain:

1. Go to your Railway project settings
2. Click "Domains"
3. Add your custom domain (e.g., `playground.asql.dev`)
4. Configure DNS records as instructed by Railway

## Environment Variables

Railway automatically provides:
- `PORT`: The port the app should listen on (required)
- `RAILWAY_ENVIRONMENT`: Environment name (production, preview, etc.)

You can set custom variables in Railway dashboard:
- `FLASK_ENV`: Set to `production` for production mode

## Monitoring

Railway provides:
- Real-time logs
- Metrics (CPU, memory, network)
- Deployment history

Access these from your Railway project dashboard.

