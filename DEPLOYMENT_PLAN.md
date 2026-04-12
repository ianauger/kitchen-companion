# Kitchen Companion Deployment Pipeline - Project Plan

## Overview
Build a complete CI/CD pipeline: local dev → GitHub → Docker → Homelab

---

## Phase 1: Local Development Setup (30 min)

### 1.1 Git Repository Structure
```
kitchen-companion-app/
├── .github/
│   └── workflows/
│       └── build-and-deploy.yml    # GitHub Actions workflow
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes.py
│   ├── image_utils.py
│   └── templates/
├── migrations/                      # Flask-Migrate
├── static/
│   └── uploads/
├── .dockerignore
├── .gitignore
├── Dockerfile
├── docker-compose.yml               # For local testing
├── manage.py
├── config.py
├── app.py
├── requirements.txt
└── README.md
```

### 1.2 Files to Create
- [ ] `.gitignore` - Python/Flask specific ignores
- [ ] `.dockerignore` - Minimize build context
- [ ] `requirements.txt` - Freeze dependencies
- [ ] `Dockerfile` - Multi-stage build
- [ ] `docker-compose.yml` - Local testing
- [ ] `entrypoint.sh` - Container startup script

---

## Phase 2: Docker Containerization (45 min)

### 2.1 Dockerfile Strategy
```dockerfile
# Multi-stage build for smaller image
# Stage 1: Builder
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

# Copy only necessary artifacts
COPY --from=builder /root/.local /root/.local
COPY . .

# Environment
ENV PATH=/root/.local/bin:$PATH
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# Create upload directory
RUN mkdir -p /app/static/uploads/recipes

EXPOSE 5000
CMD ["python", "app.py"]
```

### 2.2 Docker Compose (Local Testing)
```yaml
version: '3.8'
services:
  kitchen-companion:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./kitchen_companion.db:/app/kitchen_companion.db
      - ./static/uploads:/app/static/uploads
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=${SECRET_KEY}
```

---

## Phase 3: GitHub Actions Pipeline (45 min)

### 3.1 Workflow Trigger Strategy
```yaml
on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]
```

### 3.2 Workflow Jobs

#### Job 1: Test & Lint (5 min)
- [ ] Run Python linter (flake8/pylint)
- [ ] Check code formatting (black)
- [ ] Run unit tests (pytest) if we add them

#### Job 2: Build & Push Docker Image (10 min)
- [ ] Set up QEMU for multi-arch builds
- [ ] Set up Docker Buildx
- [ ] Log in to GitHub Container Registry (ghcr.io)
- [ ] Build multi-arch image (amd64, arm64)
- [ ] Push to GHCR: `ghcr.io/USERNAME/kitchen-companion:TAG`

#### Job 3: Security Scan (optional but recommended)
- [ ] Trivy vulnerability scanner
- [ ] Snyk container scan

---

## Phase 4: Homelab Deployment (30 min)

### 4.1 Deployment Options

#### Option A: Docker Compose on Homelab (Recommended for start)
```yaml
# docker-compose.prod.yml on homelab
version: '3.8'
services:
  kitchen-companion:
    image: ghcr.io/USERNAME/kitchen-companion:latest
    container_name: kitchen-companion
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - /opt/kitchen-companion/data:/app/data
      - /opt/kitchen-companion/uploads:/app/static/uploads
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=sqlite:///data/kitchen_companion.db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### Option B: Kubernetes (Future enhancement)
- Deployment + Service + PVC for persistence
- Ingress for external access

### 4.2 Homelab Update Script
```bash
#!/bin/bash
# update.sh - Run on homelab to pull latest image

docker pull ghcr.io/USERNAME/kitchen-companion:latest
docker-compose up -d
```

---

## Phase 5: Secrets & Configuration (20 min)

### 5.1 GitHub Secrets Required
| Secret Name | Purpose |
|-------------|---------|
| `GHCR_TOKEN` | GitHub Container Registry push access |
| `HOMELAB_SSH_KEY` | For deployment via SSH (optional) |

### 5.2 Homelab Environment File
```bash
# /opt/kitchen-companion/.env (not in git!)
SECRET_KEY=your-production-secret-key-here
```

---

## Implementation Timeline

| Phase | Estimated Time | Priority |
|-------|---------------|----------|
| Phase 1: Git Setup | 30 min | P1 |
| Phase 2: Docker | 45 min | P1 |
| Phase 3: GitHub Actions | 45 min | P1 |
| Phase 4: Homelab Deploy | 30 min | P2 |
| Phase 5: Secrets Config | 20 min | P1 |
| **Total** | **~3 hours** | |

---

## Open Questions for You

1. **GitHub Account**: What's your GitHub username? (for image naming)
2. **Homelab Setup**: What hardware/OS? (Pi, x86, NAS, etc.)
3. **Domain/Access**: Do you want external access or just local network?
4. **Reverse Proxy**: Using Traefik, Nginx Proxy Manager, or something else?
5. **SSL**: Self-signed, Let's Encrypt, or behind Cloudflare?
6. **Database**: Stick with SQLite or want PostgreSQL for production?
7. **Backups**: How important is recipe data backup?

---

## Next Steps (Ready When You Are)

1. Initialize git repo and first commit
2. Create Dockerfile and test locally
3. Set up GitHub repo and push
4. Configure GitHub Actions workflow
5. Deploy to homelab

**Want me to start implementing Phase 1 & 2 while you're at the store?** I can:
- Set up the git repo structure
- Create Dockerfile and docker-compose
- Write the GitHub Actions workflow
- Have it ready for you to review when you get back!
