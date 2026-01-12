#!/bin/bash
# Cygnet Energy - Project Status Checker
# Run this from cygnet-energy/ directory

echo "════════════════════════════════════════════════════════════"
echo "CYGNET ENERGY - PROJECT STATUS CHECK"
echo "════════════════════════════════════════════════════════════"
echo ""

# Check 1: Current directory
echo "📍 Current Directory:"
pwd
echo ""

# Check 2: Is this the right folder?
echo "📁 Project Root Check:"
if [ -f "pyproject.toml" ]; then
    echo "   ✅ Found pyproject.toml (correct directory)"
else
    echo "   ❌ No pyproject.toml (wrong directory - cd to cygnet-energy/)"
    exit 1
fi
echo ""

# Check 3: Virtual environment
echo "🐍 Virtual Environment:"
if [ -n "$VIRTUAL_ENV" ]; then
    echo "   ✅ Activated: $VIRTUAL_ENV"
else
    echo "   ❌ NOT activated - Run: source venv/bin/activate"
fi
echo ""

# Check 4: Dependencies installed
echo "📦 Dependencies:"
if python -c "import fastapi" 2>/dev/null; then
    echo "   ✅ FastAPI installed"
else
    echo "   ❌ FastAPI missing - Run: poetry install"
fi

if python -c "import psycopg2" 2>/dev/null; then
    echo "   ✅ psycopg2 installed"
else
    echo "   ❌ psycopg2 missing - Run: poetry install"
fi

if python -c "import pandas" 2>/dev/null; then
    echo "   ✅ pandas installed"
else
    echo "   ❌ pandas missing - Run: poetry install"
fi
echo ""

# Check 5: CSV data
echo "📊 CSV Data:"
if [ -f "data/samples/time_series_60min_singleindex.csv" ]; then
    echo "   ✅ CSV downloaded"
    ls -lh data/samples/time_series_60min_singleindex.csv
else
    echo "   ❌ CSV missing - Download first"
fi
echo ""

# Check 6: Configuration
echo "⚙️  Configuration:"
if [ -f "config/config.yaml" ]; then
    echo "   ✅ config.yaml exists"
else
    echo "   ⚠️  config.yaml missing - Run: cp config/config.yaml.example config/config.yaml"
fi
echo ""

# Check 7: Database
echo "🗄️  PostgreSQL:"
if command -v psql &> /dev/null; then
    echo "   ✅ psql installed"
    if psql -lqt | cut -d \| -f 1 | grep -qw cygnet_energy; then
        echo "   ✅ Database 'cygnet_energy' exists"
    else
        echo "   ⚠️  Database missing - Run: createdb cygnet_energy"
    fi
else
    echo "   ❌ PostgreSQL not found"
fi
echo ""

# Check 8: Required scripts
echo "📝 Required Scripts:"
if [ -f "scripts/init_db.py" ]; then
    echo "   ✅ init_db.py exists"
else
    echo "   ❌ init_db.py MISSING - Need to create"
fi

if [ -f "scripts/load_csv_to_db.py" ]; then
    echo "   ✅ load_csv_to_db.py exists"
else
    echo "   ❌ load_csv_to_db.py MISSING - Need to create"
fi
echo ""

# Check 9: Core modules
echo "🔧 Core Modules:"
if [ -f "src/db/connection.py" ]; then
    echo "   ✅ connection.py exists"
else
    echo "   ❌ connection.py MISSING - Need to create"
fi

if [ -f "src/db/schema.py" ]; then
    echo "   ✅ schema.py exists"
else
    echo "   ❌ schema.py MISSING - Need to create"
fi

if [ -f "src/models/generation.py" ]; then
    echo "   ✅ generation.py exists"
else
    echo "   ❌ generation.py MISSING - Need to create"
fi
echo ""

# Summary
echo "════════════════════════════════════════════════════════════"
echo "NEXT IMMEDIATE ACTION:"
echo "════════════════════════════════════════════════════════════"

if [ ! -n "$VIRTUAL_ENV" ]; then
    echo "→ source venv/bin/activate"
elif ! python -c "import fastapi" 2>/dev/null; then
    echo "→ poetry install"
elif [ ! -f "config/config.yaml" ]; then
    echo "→ cp config/config.yaml.example config/config.yaml && nano config/config.yaml"
elif ! psql -lqt | cut -d \| -f 1 | grep -qw cygnet_energy; then
    echo "→ createdb cygnet_energy"
elif [ ! -f "scripts/init_db.py" ]; then
    echo "→ Tell assistant: 'Create database files'"
else
    echo "→ python scripts/init_db.py"
fi
echo ""
