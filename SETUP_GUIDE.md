# Cygnet Energy Project - Integration Checklist

## QUICK COMMAND REFERENCE

### Initial Setup (One-Time)

```bash
# Navigate to project
cd cygnet-energy

# Initialize git (if not already done)
git init
git config user.email "your.email@domain.com"
git config user.name "Your Name"

# Add all files
git add .

# Commit initial state
git commit -m "Initial project setup: structure, dependencies, documentation"
```

### Create GitHub Repository

1. Go to https://github.com/new
2. **Repository name:** `cygnet-energy`
3. **Description:** `European grid intelligence platform - Real-time electricity system data`
4. **Visibility:** Choose Private or Public
5. **Important:** DO NOT initialize with README, .gitignore, or LICENSE
6. Click "Create repository"

### Link & Push to GitHub

```bash
# Add remote origin
git remote add origin https://github.com/yasharnaghdi/cygnet-energy.git

# Rename branch to main (if needed)
git branch -M main

# Push initial commit
git push -u origin main

# Verify
git remote -v
```

---

## FILE CHECKLIST

### ✅ Created (Ready to Commit)

- [x] `.gitignore` - Git exclusions
- [x] `pyproject.toml` - Poetry dependencies & config
- [x] `README.md` - Project documentation
- [x] `Dockerfile` - Container configuration
- [x] `SETUP_GUIDE.md` - This integration guide

### ⏭️ Create Before First Run

**Directory Structure:**

```
cygnet-energy/
├── src/
│   ├── __init__.py
│   ├── api/
│   │   └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   ├── services/
│   │   └── __init__.py
│   ├── utils/
│   │   └── __init__.py
│   └── db/
│       └── __init__.py
├── tests/
│   ├── __init__.py
├── config/
│   └── config.yaml.example
├── scripts/
│   ├── init_db.py
│   ├── load_csv_to_db.py
│   └── smoke_check.py
└── data/
    └── samples/
```

**Create Empty __init__.py Files:**

```bash
# From cygnet-energy directory
touch src/__init__.py
touch src/api/__init__.py
touch src/models/__init__.py
touch src/services/__init__.py
touch src/utils/__init__.py
touch src/db/__init__.py
touch tests/__init__.py
```

**Create Example Config:**

```bash
mkdir -p config
cat > config/config.yaml.example << 'EOF'
# Database Configuration
database:
  host: localhost
  port: 5432
  name: cygnet_energy
  user: postgres
  password: your_password

# ENTSO-E API Configuration
entso_e:
  api_key: your_api_key_here
  base_url: https://web-api.tp.entsoe.eu/api
  max_retries: 5
  rate_limit: 10  # requests per second

# Service Configuration
service:
  log_level: INFO
  api_port: 8000
  api_workers: 4
  scheduler_enabled: true

# Countries to collect (Phase 1: Germany only)
countries:
  - DE  # Germany
  # Add more in Phase 2

# Data retention policy
retention:
  keep_years: 5
  compression_threshold_days: 14
EOF

# Copy as actual config
cp config/config.yaml.example config/config.yaml
```

---

## SETUP EXECUTION ORDER

### ✅ Phase 0: Local Folder Rename (Already Done)
- [x] Renamed folder to `cygnet-energy`

### ⏳ Phase 1: Git & GitHub (Next)

**Commands:**
```bash
cd cygnet-energy

# Initialize git
git init
git config user.email "your.email@domain.com"
git config user.name "Your Name"

# Create GitHub repo at https://github.com/new
# (Repository name: cygnet-energy, NO initialization)

# Link to GitHub
git remote add origin https://github.com/yasharnaghdi/cygnet-energy.git
git branch -M main

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: project structure, dependencies, documentation

- pyproject.toml: Poetry config with all dependencies
- README.md: Complete project documentation
- .gitignore: Standard Python exclusions
- Dockerfile: Container setup
- config/: Example configuration files"

# Push to GitHub
git push -u origin main
```

### ⏳ Phase 2: Python Environment

**Commands:**
```bash
# Create virtual environment
python3.11 -m venv venv

# Activate
source venv/bin/activate          # macOS/Linux
# OR
venv\Scripts\activate            # Windows

# Install poetry
pip install poetry

# Install project dependencies
poetry install

# Verify
poetry show  # List installed packages
python --version
```

### ⏳ Phase 3: Database Setup (Local Development)

**Commands:**
```bash
# Install PostgreSQL (if not already installed)
# macOS: brew install postgresql@14
# Linux: sudo apt-get install postgresql postgresql-contrib
# Windows: Download from https://www.postgresql.org/download/windows/

# Create database
createdb cygnet_energy

# Create TimescaleDB extension
psql -d cygnet_energy -c "CREATE EXTENSION timescaledb;"

# Verify
psql -d cygnet_energy -c "\dx"  # Should show timescaledb
```

### ⏳ Phase 4: Create Initial Python Modules

**api/__init__.py:**
```python
"""API module for Cygnet Energy platform."""
from fastapi import FastAPI

app = FastAPI(
    title="Cygnet Energy API",
    version="1.0.1",
    description="European grid intelligence platform"
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.1"}
```

**models/__init__.py:**
```python
"""Data models and Pydantic schemas."""
from pydantic import BaseModel
from datetime import datetime

class GenerationReading(BaseModel):
    time: datetime
    bidding_zone_mrid: str
    psr_type: str
    actual_generation_mw: float
    quality_code: str = 'A'

__all__ = ['GenerationReading']
```

**db/__init__.py:**
```python
"""Database connection and queries."""
__version__ = "1.0.1"
```

### ⏳ Phase 5: First Test Run

**Start API Server:**
```bash
python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

**In another terminal, test:**
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"1.0.1"}
```

---

## GIT WORKFLOW FOR FUTURE COMMITS

### Feature Development

```bash
# Create feature branch
git checkout -b feature/short-description

# Make changes, then commit
git add .
git commit -m "Implement baseline improvement"

# Push feature branch
git push -u origin feature/short-description

# Create Pull Request on GitHub
# (Merge to main after review)
```

### Daily Development

```bash
# Before starting work
git pull origin main

# During work (frequent commits)
git add .
git commit -m "WIP: Add database insertion logic"

# Publish work
git push origin main
```

---

## VERIFICATION CHECKLIST

### After Initial Setup

- [ ] Folder renamed to `cygnet-energy`
- [ ] Git initialized (`git init`)
- [ ] GitHub repository created (https://github.com/yasharnaghdi/cygnet-energy)
- [ ] Remote configured (`git remote -v` shows origin)
- [ ] Initial commit pushed (`git log` shows commits on GitHub)
- [ ] Virtual environment created & activated (`which python` shows venv path)
- [ ] Dependencies installed (`poetry show` lists packages)
- [ ] PostgreSQL & TimescaleDB set up locally
- [ ] API starts without errors (`http://localhost:8000/health` responds)

### Files Present

```bash
# From cygnet-energy directory
ls -la

# Should show:
# .git/
# .gitignore
# README.md
# pyproject.toml
# Dockerfile
# src/
# tests/
# config/
```

---

## TROUBLESHOOTING

### "fatal: not a git repository"
```bash
cd cygnet-energy
git init
```

### "Permission denied" on GitHub push
```bash
# Use SSH instead of HTTPS
git remote set-url origin git@github.com:yasharnaghdi/cygnet-energy.git

# Or set up personal access token for HTTPS
# https://github.com/settings/tokens
```

### Poetry dependency conflicts
```bash
# Clear cache
poetry cache clear pypi --all

# Reinstall
poetry install --no-cache
```

### PostgreSQL connection refused
```bash
# Check if running
brew services list          # macOS
sudo systemctl status postgresql  # Linux

# Start service
brew services start postgresql  # macOS
sudo systemctl start postgresql  # Linux
```

---

## NEXT STEPS AFTER SETUP

1. **Expand ETL scripts** → `scripts/fetch_entsoe_data.py` and scheduler integration
2. **Create Database Models** → `src/db/schema.py` with migrations if adopted
3. **Build API Endpoints** → `src/api/` as needed
4. **Write Tests** → `tests/`
5. **Docker Build & Test** → `docker build -t cygnet-energy .`
6. **Push to Registry** → Docker Hub or GitHub Container Registry (Phase 3)

---

**Status:** Ready for Phase 1 MVP Development  
**Last Updated:** January 2025
