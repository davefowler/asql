# Docker Deployment for ASQL Documentation and Playground

This guide explains how to deploy the ASQL documentation and playground using Docker.

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Build and start both services
docker-compose up --build

# Run in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Once running, access:
- **Documentation**: http://localhost:5000
- **Playground**: http://localhost:5001

### Using Docker Directly

```bash
# Build the image
docker build -t asql-docs .

# Run the container
docker run -p 5000:5000 -p 5001:5001 asql-docs
```

## Features

### Documentation Server (Port 5000)
- Serves all documentation from `docs/` directory
- Automatically processes ASQL code blocks with dialect tabs
- Pre-compiles queries to all supported SQL dialects
- Tracks user dialect preferences via localStorage

### Playground (Port 5001)
- Interactive ASQL query editor
- Real-time SQL compilation
- Multiple dialect support

## Dialect Tabs

The documentation automatically adds tabs above each ASQL code example:
- **ASQL** tab (always first) - Shows the original ASQL query
- **Top 4 dbt dialects** - PostgreSQL, Snowflake, BigQuery, Redshift
- **⋯ (More)** tab - Access to other dialects (MySQL, SQLite, Oracle, etc.)

### Tab Ordering
- Tabs are ordered by view count (most viewed first)
- User preferences are saved in localStorage
- Tab order updates on page load based on usage statistics

## Development

### Local Development (without Docker)

```bash
# Install dependencies
pip install -e ".[docs,playground]"

# Start documentation server
python docs_server.py

# In another terminal, start playground
python playground.py
```

### Making Changes

The Docker setup mounts the `docs/` and `static/` directories as read-only volumes, so you can edit documentation files and see changes by refreshing the browser (if using volumes). For code changes, rebuild the image.

## Configuration

### Environment Variables

- `FLASK_ENV`: Set to `production` for production mode (default in docker-compose)

### Ports

- `5000`: Documentation server
- `5001`: Playground

To change ports, modify `docker-compose.yml`:

```yaml
ports:
  - "8080:5000"  # Documentation on port 8080
  - "8081:5001"  # Playground on port 8081
```

## Troubleshooting

### Port Already in Use

If ports 5000 or 5001 are already in use:

```bash
# Change ports in docker-compose.yml
ports:
  - "5002:5000"
  - "5003:5001"
```

### Container Won't Start

Check logs:
```bash
docker-compose logs
```

### Documentation Not Loading

Ensure the `docs/` directory exists and contains markdown files.

## Production Deployment

For production deployment:

1. Set `FLASK_ENV=production` in docker-compose.yml
2. Use a reverse proxy (nginx, traefik) in front of the services
3. Enable HTTPS
4. Consider using a process manager like supervisor if not using Docker

Example nginx configuration:

```nginx
server {
    listen 80;
    server_name docs.asql.example.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name playground.asql.example.com;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
