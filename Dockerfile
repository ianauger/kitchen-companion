# ============================================================================
# Kitchen Companion - Multi-stage Docker Build
# ============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build dependencies
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies (gcc etc. for C extensions)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Create virtual environment and install Python packages
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install exact pinned versions first, then extras used by the app
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir \
        Flask-Migrate==4.0.5 \
        Flask-Limiter==3.5.1 \
        flask-jwt-extended==4.6.0 \
        Flask-Bcrypt==1.0.1 \
        Flask-WTF==1.2.1 \
        gunicorn==21.2.0

# ---------------------------------------------------------------------------
# Stage 2: Runtime image (minimal footprint)
# ---------------------------------------------------------------------------
FROM python:3.11-slim

# Hardening: no interactive frontend
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r appuser && \
    useradd -r -g appuser -d /app -s /sbin/nologin -c "Kitchen Companion app user" appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Ensure upload directory exists with correct ownership
RUN mkdir -p /app/static/uploads/recipes && \
    mkdir -p /app/instance && \
    chown -R appuser:appuser /app && \
    chmod +x /app/scripts/entrypoint.sh

# Switch to non-root user
USER appuser

# Expose Flask port
EXPOSE 5000

# Health-friendly default: gunicorn for production, falls back to Flask dev server
# via docker-compose override if needed
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:create_app('development')"]