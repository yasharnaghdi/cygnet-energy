#!/bin/bash
# Cygnet Energy - Complete Integration Script
# This script automates the setup from folder rename to GitHub push

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║       CYGNET ENERGY - COMPLETE SETUP AUTOMATION              ║"
echo "║     European Grid Intelligence Platform - Phase 0              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
PROJECT_DIR="cygnet-energy"
GITHUB_USER="yasharnaghdi"
GITHUB_REPO="cygnet-energy"
PYTHON_VERSION="3.11"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Step 1: Verify Directory
log_info "Step 1: Verifying directory structure..."
if [ ! -d "$PROJECT_DIR" ]; then
    log_error "Directory '$PROJECT_DIR' not found!"
    echo "Please rename your folder to '$PROJECT_DIR' and try again."
    exit 1
fi
log_success "Directory verified: $PROJECT_DIR"

# Step 2: Navigate to project directory
cd "$PROJECT_DIR"
log_success "Navigated to $PROJECT_DIR"

# Step 3: Initialize Git (if not already done)
log_info "Step 2: Initializing Git repository..."
if [ ! -d ".git" ]; then
    git init
    log_success "Git repository initialized"
else
    log_warn "Git repository already exists"
fi

# Step 4: Configure Git
log_info "Step 3: Configuring Git..."
read -p "Enter your email for Git commits: " GIT_EMAIL
read -p "Enter your name for Git commits: " GIT_NAME

git config user.email "$GIT_EMAIL"
git config user.name "$GIT_NAME"
log_success "Git configured"

# Step 5: Create directory structure
log_info "Step 4: Creating directory structure..."
mkdir -p src/{api,collector,models,db}
mkdir -p tests/{unit,integration}
mkdir -p config
mkdir -p scripts
mkdir -p logs
mkdir -p docs

log_success "Directory structure created"

# Step 6: Create __init__.py files
log_info "Step 5: Creating Python package files..."
for dir in src src/api src/collector src/models src/db tests tests/unit tests/integration; do
    touch "$dir/__init__.py"
done
log_success "Python package files created"

# Step 7: Create config example if not exists
log_info "Step 6: Creating configuration template..."
if [ ! -f "config/config.yaml.example" ]; then
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
  rate_limit: 10

# Service Configuration
service:
  log_level: INFO
  api_port: 8000
  api_workers: 4
  scheduler_enabled: true

# Countries to collect
countries:
  - DE

# Data retention policy
retention:
  keep_years: 5
  compression_threshold_days: 14
EOF
    log_success "Configuration template created"
else
    log_warn "Configuration template already exists"
fi

# Step 8: Check if .gitignore exists
log_info "Step 7: Checking .gitignore..."
if [ ! -f ".gitignore" ]; then
    log_warn ".gitignore not found - please create it manually"
else
    log_success ".gitignore present"
fi

# Step 9: Check if pyproject.toml exists
log_info "Step 8: Checking pyproject.toml..."
if [ ! -f "pyproject.toml" ]; then
    log_warn "pyproject.toml not found - please create it manually"
else
    log_success "pyproject.toml present"
fi

# Step 10: Check if README exists
log_info "Step 9: Checking README.md..."
if [ ! -f "README.md" ]; then
    log_warn "README.md not found - please create it manually"
else
    log_success "README.md present"
fi

# Step 11: Git status
log_info "Step 10: Checking Git status..."
git status
echo ""

# Step 12: Add all files
log_info "Step 11: Adding files to Git..."
git add .
log_success "Files added"

# Step 13: Commit
log_info "Step 12: Creating initial commit..."
git commit -m "Initial commit: Cygnet Energy project setup

- pyproject.toml: Poetry dependencies & configuration
- README.md: Comprehensive project documentation
- .gitignore: Standard Python exclusions
- Dockerfile: Container configuration
- SETUP_GUIDE.md: Integration guide
- Project structure: src/, tests/, config/, docs/, scripts/
- Example configuration: config/config.yaml.example"

log_success "Initial commit created"

# Step 14: GitHub setup instructions
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           NEXT: GITHUB REPOSITORY CREATION                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
log_info "Please follow these steps to create the GitHub repository:"
echo ""
echo "1. Go to: https://github.com/new"
echo "2. Repository name: $GITHUB_REPO"
echo "3. Description: European grid intelligence platform - Real-time electricity data"
echo "4. Visibility: Choose Public or Private"
echo "5. ⚠️  DO NOT initialize with README, .gitignore, or LICENSE"
echo "6. Click 'Create repository'"
echo ""
echo "Once created, run these commands:"
echo ""
echo "  git remote add origin https://github.com/$GITHUB_USER/$GITHUB_REPO.git"
echo "  git branch -M main"
echo "  git push -u origin main"
echo ""

read -p "Press Enter once you've created the GitHub repository and are ready to continue..."

# Step 15: Add remote and push
log_info "Step 13: Adding GitHub remote..."
git remote add origin "https://github.com/$GITHUB_USER/$GITHUB_REPO.git" 2>/dev/null || log_warn "Remote may already exist"

log_info "Step 14: Setting default branch to main..."
git branch -M main

log_info "Step 15: Pushing to GitHub..."
git push -u origin main

log_success "Code pushed to GitHub!"

# Step 16: Verify
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              SETUP COMPLETE - NEXT STEPS                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

log_success "Project initialized and pushed to GitHub"
echo ""
echo "📍 Repository: https://github.com/$GITHUB_USER/$GITHUB_REPO"
echo ""
echo "Next steps:"
echo "  1. Create Python virtual environment:"
echo "     python3.11 -m venv venv"
echo "     source venv/bin/activate"
echo ""
echo "  2. Install Poetry:"
echo "     pip install poetry"
echo ""
echo "  3. Install dependencies:"
echo "     poetry install"
echo ""
echo "  4. Setup PostgreSQL & TimescaleDB (see README.md)"
echo ""
echo "  5. Start development:"
echo "     python -m uvicorn src.api:app --reload"
echo ""
echo "For detailed instructions, see: README.md and SETUP_GUIDE.md"
echo ""
