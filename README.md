# Legal Graph RAG

A **Graph-Augmented Retrieval system** for legal contract intelligence. Upload contracts, extract a knowledge graph of parties, clauses, obligations, and risk flags, then ask complex questions that require traversing relationships across documents.

## What Makes This Different from Standard RAG

Standard RAG cannot answer:
> *"Which contracts have unlimited indemnification but a liability cap — creating a legal conflict?"*

This requires graph traversal: `Clause{type:indemnification}` → `CONFLICTS_WITH` → `Clause{type:limitation_of_liability}`.

This project builds that graph automatically from any uploaded contract.

## Novel Features vs Original Neo4j Contract Review Demo

| Feature | Original (neo4j-product-examples) | This Project |
|---|---|---|
| UI | Streamlit | React + D3.js interactive graph |
| Metadata storage | Neo4j only | Neo4j + PostgreSQL |
| Processing | Synchronous | Async Celery workers |
| LLM | OpenAI GPT-4o | Ollama Gemma3:12b (local, free) |
| Retrieval strategies | 3 | 5 + keyword rerank |
| Answer modes | Single | 3-way: Graph + Baseline + Extractive |
| **CONFLICTS_WITH edges** | ✗ | ✓ Auto-detects contradicting clauses |
| **RiskFlag nodes** | ✗ | ✓ LLM extracts risks as queryable nodes |
| **Cross-contract RELATED_TO** | ✗ | ✓ Links contracts sharing parties |
| **Risk dashboard** | ✗ | ✓ Dedicated risks page with severity filter |
| Query history | ✗ | ✓ PostgreSQL persistent history |
| Deployment | Manual | Docker Compose one-command |

## Architecture

```
Contract Upload (PDF/TXT)
        │
        ▼
Celery Worker (async background)
        │
        ├── Text Extraction (PyPDF2)
        ├── Chunking (512 words, 64 overlap)
        ├── Embedding (sentence-transformers, local)
        ├── LLM Entity Extraction (Ollama Gemma3:12b)
        │     └── Parties, Clauses, Obligations, Risk Flags → JSON
        └── Neo4j Graph Build
              ├── Contract, Party, Clause, Obligation, Jurisdiction nodes
              ├── RiskFlag nodes (novel)
              ├── CONFLICTS_WITH edges (novel: indemnification vs liability cap)
              ├── RELATED_TO edges (novel: same parties across contracts)
              └── SIMILAR_TO semantic edges on chunks

Query
  │
  ├── Query Classification (Ollama)
  ├── 5-Strategy Retrieval
  │     ├── Vector Search (semantic similarity)
  │     ├── Clause Search (graph: Clause → Contract → Chunk)
  │     ├── Graph Expansion (SIMILAR_TO traversal)
  │     ├── Structured Cypher (risk, party, conflict queries)
  │     └── Sequential Context (NEXT edge neighbors)
  │
  ├── Graph RAG Answer (Gemma3:12b)
  ├── Flat Baseline (vector-only, for comparison)
  └── Extractive QA (RoBERTa, zero hallucination)
```

## Knowledge Graph Schema

```
Nodes:
  Contract     {id, title, contract_type, effective_date, jurisdiction}
  Party        {name, type}
  Clause       {id, type, summary, risk_level}
  Obligation   {description, party, deadline}
  Jurisdiction {name}
  RiskFlag     {type, severity, description, clause_ref}  ← novel
  Chunk        {id, text, embedding}

Relationships:
  (Contract)-[:HAS_PARTY {role}]->(Party)
  (Party)-[:PARTY_TO]->(Contract)
  (Contract)-[:CONTAINS]->(Clause)
  (Contract)-[:GOVERNED_BY]->(Jurisdiction)
  (Contract)-[:RELATED_TO {shared_party}]->(Contract)   ← novel
  (Contract)-[:HAS_RISK]->(RiskFlag)                    ← novel
  (Clause)-[:CONFLICTS_WITH {reason}]->(Clause)         ← novel
  (Clause)-[:SIMILAR_TO {score}]->(Clause)
  (Chunk)-[:SIMILAR_TO {score}]->(Chunk)
  (Chunk)-[:NEXT]->(Chunk)
```

## Queries That Demonstrate Graph Value

These are impossible with flat vector search:

```
"Which contracts have indemnification clauses but no limitation of liability?"
→ Contract-[CONTAINS]->Clause{type:indemnification}
  AND NOT Contract-[CONTAINS]->Clause{type:limitation_of_liability}

"Find all contracts where CloudBase is a party"
→ Party{name:CloudBase}-[PARTY_TO]->Contract

"Which clauses conflict with each other?"
→ Clause-[CONFLICTS_WITH]->Clause (CONFLICTS_WITH edges, cross-contract)

"What are the riskiest contracts we have?"
→ Contract-[HAS_RISK]->RiskFlag{severity:high}

"Which contracts auto-renew and what are their notice periods?"
→ Clause{type:termination} containing auto-renewal terms
```

## Dataset

Includes 3 sample contracts designed to demonstrate cross-contract graph traversal:
- `nda_acme_zenith.txt` — NDA between Acme and Zenith
- `software_services_acme_cloudbase.txt` — Services agreement (Acme + CloudBase)
- `ip_license_zenith_meridian.txt` — IP license (Zenith + Meridian + CloudBase, intentional conflicts)

Shared parties (Acme, Zenith, CloudBase) create `RELATED_TO` edges between contracts.
The IP license has deliberate `CONFLICTS_WITH` edges between indemnification and liability cap.

### Use Real CUAD Dataset (510 contracts)

```bash
cd data
pip install datasets
python download_cuad.py
```

## Quick Start

```bash
# 1. Prerequisites
ollama serve          # keep running
ollama pull gemma3:12b

# 2. Setup
git clone https://github.com/yourusername/legal-graph-rag
cd legal-graph-rag
cp .env.example .env
docker-compose up --build

# 3. Create Neo4j vector indexes (http://localhost:7474, login neo4j/legalrag)
CALL db.index.vector.createNodeIndex('chunk_vector','Chunk','embedding',768,'cosine')
CALL db.index.vector.createNodeIndex('clause_vector','Clause','embedding',768,'cosine')

# 4. Open UI: http://localhost:3000
# 5. Upload contracts from data/sample_contracts/
```

## Run Without Docker

```bash
# Start dependencies
docker run -d -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/legalrag neo4j:5.13.0
docker run -d -p 5432:5432 -e POSTGRES_DB=legalrag -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=legalrag postgres:15-alpine
docker run -d -p 6379:6379 redis:7-alpine

# Backend (terminal 1)
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Celery worker (terminal 2)
cd backend && celery -A celery_app worker --loglevel=info

# Frontend (terminal 3)
cd frontend && npm install && npm start
```

## Project Structure

```
legal-graph-rag/
├── backend/
│   ├── main.py           FastAPI REST API
│   ├── ingestion.py      Contract processing pipeline
│   ├── retrieval.py      5-strategy graph retrieval
│   ├── celery_app.py     Async task queue
│   ├── graph_db.py       Neo4j schema + connection
│   ├── postgres_db.py    PostgreSQL operations
│   ├── ollama_utils.py   LLM interface
│   ├── embeddings.py     Local embeddings
│   ├── baseline.py       Flat vector baseline
│   ├── extractive.py     RoBERTa extractive QA
│   └── init.sql          PostgreSQL schema
├── frontend/src/pages/
│   ├── Query.jsx         3-way answer comparison
│   ├── Contracts.jsx     Upload + processing status
│   ├── Graph.jsx         D3.js knowledge graph
│   ├── Risks.jsx         Risk dashboard (novel)
│   ├── History.jsx       Query history
│   └── Stats.jsx         Live statistics
├── data/
│   ├── sample_contracts/ 3 sample contracts
│   └── download_cuad.py  Download real CUAD dataset
└── docker-compose.yml
```

## License
MIT
