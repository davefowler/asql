FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY asql/ ./asql/
COPY docs/ ./docs/
COPY static/ ./static/
COPY docs_server.py ./
COPY playground.py ./

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[docs,playground]"

# Expose ports
# 5000 for docs server, 5001 for playground
EXPOSE 5000 5001

# Copy startup script
COPY start_servers.py ./

# Use the startup script
CMD ["python", "start_servers.py"]
