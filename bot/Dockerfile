# Use official Python 3.11 image as base
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies (build tools, PostgreSQL headers, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Copy python project config first for dependency caching
COPY pyproject.toml README.md ./

# Install dependencies using pip
RUN pip install --no-cache-dir .

# Copy the rest of the bot code into the image
COPY src ./src
COPY alembic ./alembic
COPY locales ./locales

# Expose port for webhook usage (if needed)
EXPOSE 8080

# Default command to run the bot
CMD ["python", "-m", "src.bot"]
