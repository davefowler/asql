# Password Protection for Netlify

This directory contains a Basic Auth edge function to protect your Netlify site.

## Option 1: Netlify Built-in Password Protection (Easiest!)

**This is the simplest option** - no code needed:

1. Go to your Netlify site dashboard
2. Navigate to **Site settings** → **Access & security** → **Visitor access** → **Password Protection**
3. Click **Configure Password Protection**
4. Choose **Basic password protection** and set a password
5. Choose scope:
   - **Non-production deploys only** (for previews/branches)
   - **All deploys** (for everything including production)
6. Save

That's it! No code changes needed.

## Option 2: Basic Auth Edge Function (Current Implementation)

If you prefer Basic Auth (username + password) or need more control:

### Setup

1. **Set Environment Variables in Netlify:**
   - Go to your Netlify site dashboard
   - Navigate to **Site settings** → **Environment variables**
   - Add the following variables:
     - `NETLIFY_AUTH_USER` - Your desired username (defaults to "admin" if not set)
     - `NETLIFY_AUTH_PASS` - Your desired password (defaults to "password" if not set)

2. **Deploy:**
   - The edge function is automatically configured in `netlify.toml`
   - On deploy, Netlify will use this function to protect all routes

### How It Works

- The edge function intercepts all requests (`/*`)
- If no Authorization header is present, it returns a 401 with a Basic Auth challenge
- The browser will prompt for username/password
- Credentials are verified against the environment variables
- If valid, the request proceeds to the site

### Security Note

Basic Auth sends credentials in base64 encoding (not encrypted). For production use:
- HTTPS is required (which Netlify provides by default)
- Consider using Netlify's built-in password protection for better security
- Or implement a more secure authentication method for sensitive content

