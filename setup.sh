#!/bin/bash
# setup.sh - Organizes all files into correct project structure
# Run from: /mnt/c/Users/Lenovo/Downloads/Neo4jRAG/
# Usage: bash setup.sh

set -e

echo "======================================"
echo "  Legal Graph RAG - Project Setup"
echo "======================================"

BASE=$(pwd)
echo "Working in: $BASE"

# ── Create folder structure ───────────────────────────────────
echo ""
echo "Creating folder structure..."
mkdir -p backend
mkdir -p frontend/src/pages
mkdir -p frontend/public
mkdir -p data/sample_contracts

# ── Move backend files ────────────────────────────────────────
echo "Moving backend files..."
for f in main.py ingestion.py retrieval.py celery_app.py graph_db.py \
          postgres_db.py ollama_utils.py embeddings.py baseline.py \
          extractive.py init.sql requirements.txt; do
  if [ -f "$BASE/$f" ]; then
    mv "$BASE/$f" "$BASE/backend/$f"
    echo "  ✓ backend/$f"
  else
    echo "  ⚠ MISSING: $f"
  fi
done

# Backend Dockerfile
if [ -f "$BASE/Dockerfile" ]; then
  mv "$BASE/Dockerfile" "$BASE/backend/Dockerfile"
  echo "  ✓ backend/Dockerfile"
fi

# ── Move frontend files ───────────────────────────────────────
echo "Moving frontend files..."
for f in Query.jsx Contracts.jsx Graph.jsx Risks.jsx History.jsx Stats.jsx App.jsx; do
  if [ -f "$BASE/$f" ]; then
    mv "$BASE/$f" "$BASE/frontend/src/pages/$f"
    echo "  ✓ frontend/src/pages/$f"
  else
    echo "  ⚠ MISSING: $f"
  fi
done

# App.jsx goes in src/ not pages/
if [ -f "$BASE/frontend/src/pages/App.jsx" ]; then
  mv "$BASE/frontend/src/pages/App.jsx" "$BASE/frontend/src/App.jsx"
  echo "  ✓ frontend/src/App.jsx (moved from pages)"
fi

# index files
if [ -f "$BASE/index.js" ]; then
  mv "$BASE/index.js" "$BASE/frontend/src/index.js"
  echo "  ✓ frontend/src/index.js"
fi
if [ -f "$BASE/index.html" ]; then
  mv "$BASE/index.html" "$BASE/frontend/public/index.html"
  echo "  ✓ frontend/public/index.html"
fi
if [ -f "$BASE/package.json" ]; then
  mv "$BASE/package.json" "$BASE/frontend/package.json"
  echo "  ✓ frontend/package.json"
fi

# Frontend Dockerfile - create a new one since there's only one Dockerfile
cat > "$BASE/frontend/Dockerfile" << 'DOCKEREOF'
FROM node:18-alpine
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
DOCKEREOF
echo "  ✓ frontend/Dockerfile (created)"

# ── Move data files ───────────────────────────────────────────
echo "Moving contract files..."
for f in nda_acme_zenith.txt software_services_acme_cloudbase.txt ip_license_zenith_meridian.txt; do
  if [ -f "$BASE/$f" ]; then
    mv "$BASE/$f" "$BASE/data/sample_contracts/$f"
    echo "  ✓ data/sample_contracts/$f"
  else
    echo "  ⚠ MISSING: $f"
  fi
done

if [ -f "$BASE/download_cuad.py" ]; then
  mv "$BASE/download_cuad.py" "$BASE/data/download_cuad.py"
  echo "  ✓ data/download_cuad.py"
fi

# ── Create .env from example ──────────────────────────────────
if [ ! -f "$BASE/.env" ]; then
  if [ -f "$BASE/.env.example" ]; then
    cp "$BASE/.env.example" "$BASE/.env"
    echo "  ✓ .env created from .env.example"
  else
    cat > "$BASE/.env" << 'ENVEOF'
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=legalrag
POSTGRES_URL=postgresql://admin:legalrag@localhost:5432/legalrag
POSTGRES_PASSWORD=legalrag
REDIS_URL=redis://localhost:6379/0
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:12b
MAX_CHUNK_SIZE=512
CHUNK_OVERLAP=64
SIMILARITY_THRESHOLD=0.55
TOP_K_RETRIEVAL=5
ENVEOF
    echo "  ✓ .env created"
  fi
fi

# ── Final structure check ─────────────────────────────────────
echo ""
echo "======================================"
echo "  Final Structure"
echo "======================================"
find "$BASE" -not -path "*/node_modules/*" -not -path "*/.git/*" \
             -not -path "*/mnt/*" -not -name "*.pyc" \
             -not -path "*/__pycache__/*" \
             -type f | sort | sed "s|$BASE/||"

echo ""
echo "======================================"
echo "  DONE! Next steps:"
echo "======================================"
echo ""
echo "1. Make sure Ollama is running:"
echo "   ollama serve   (in another terminal)"
echo "   ollama list    (verify gemma3:12b)"
echo ""
echo "2. Start all services:"
echo "   docker-compose up --build"
echo ""
echo "3. Create Neo4j vector indexes"
echo "   Open: http://localhost:7474"
echo "   Login: neo4j / legalrag"
echo "   Run:"
echo "   CALL db.index.vector.createNodeIndex('chunk_vector','Chunk','embedding',768,'cosine')"
echo "   CALL db.index.vector.createNodeIndex('clause_vector','Clause','embedding',768,'cosine')"
echo ""
echo "4. Open the app: http://localhost:3000"
echo ""
echo "5. Upload the 3 contracts from data/sample_contracts/"
echo ""
