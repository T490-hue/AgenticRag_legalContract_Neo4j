import os
import sys
import time
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from graph_db   import Neo4jConnection, setup_schema, get_stats
from embeddings import EmbeddingModel
from ollama_utils import OllamaLLM
from retrieval  import LegalRetriever
from postgres_db import PostgresDB
from baseline    import BaselineRAG
from celery_app  import process_contract_task
from evaluation  import RAGEvaluator

app = FastAPI(title="Legal Graph RAG API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

conn      = None
embedder  = None
llm       = None
retriever = None
baseline  = None
pg        = None
evaluator = None

UPLOAD_DIR = "/tmp/legal_rag_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.on_event("startup")
async def startup():
    global conn, embedder, llm, retriever, baseline, pg, evaluator
    print("Starting Legal Graph RAG...")
    pg        = PostgresDB()
    conn      = Neo4jConnection()
    setup_schema(conn)
    embedder  = EmbeddingModel()
    llm       = OllamaLLM()
    retriever = LegalRetriever(conn, embedder)
    baseline  = BaselineRAG(embedder, llm)
    evaluator = RAGEvaluator(llm)

    # Preload existing chunks into baseline memory store
    try:
        chunks = conn.run("MATCH (c:Chunk) RETURN c.text AS text, c.id AS id")
        for row in chunks:
            if row["text"]:
                emb = embedder.embed(row["text"])
                baseline.store.add(row["text"], emb, {"id": row["id"]})
        print(f" Baseline preloaded: {baseline.store.size()} chunks")
    except Exception as e:
        print(f" Baseline preload skipped: {e}")
    print(" Ready")


class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    question:           str
    graph_answer:       str
    baseline_answer:    str
    graph_chunks:       int
    graph_only_chunks:  int
    graph_latency:      float
    baseline_latency:   float
    sources:            List[dict]
    graph_chunk_texts:  List[str] = []
    baseline_chunk_texts: List[str] = []


@app.post("/contracts/upload")
async def upload_contract(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise HTTPException(400, f"Unsupported: {suffix}")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Empty file")

    contract_id = pg.create_contract(file.filename, len(content))
    file_path   = os.path.join(UPLOAD_DIR, f"{contract_id}{suffix}")
    with open(file_path, "wb") as f:
        f.write(content)

    task = process_contract_task.delay(contract_id, file_path, file.filename)
    return {
        "contract_id": contract_id,
        "task_id":     task.id,
        "status":      "processing",
        "message":     "Processing in background — poll /contracts/{id}/status",
    }


@app.get("/contracts")
def list_contracts():
    return pg.get_contracts()


@app.get("/contracts/{contract_id}/status")
def contract_status(contract_id: str):
    contract = pg.get_contract(contract_id)
    if not contract:
        raise HTTPException(404, "Not found")

    # Auto-reload baseline when contract finishes processing
    # Fixes: baseline store not updated after new uploads
    if contract.get("status") == "complete" and baseline:
        try:
            chunks = conn.run(
                "MATCH (c:Chunk {contract_id: $cid}) RETURN c.text AS text, c.id AS id",
                {"cid": contract_id}
            )
            existing_ids = {m.get("id") for m in baseline.store.metadata}
            added = 0
            for row in chunks:
                if row["text"] and row["id"] not in existing_ids:
                    emb = embedder.embed(row["text"])
                    baseline.store.add(row["text"], emb, {"id": row["id"]})
                    added += 1
            if added:
                print(f" Baseline updated: +{added} chunks (total {baseline.store.size()})")
        except Exception as e:
            print(f" Baseline update failed: {e}")

    return {
        **contract,
        "processing_log": pg.get_log(contract_id),
        "risk_flags":     pg.get_risk_flags(contract_id),
    }


@app.delete("/contracts/{contract_id}")
def delete_contract(contract_id: str):
    conn.run("""
        MATCH (c:Contract {id: $id})
        OPTIONAL MATCH (c)-[:HAS_CHUNK]->(ch:Chunk)
        OPTIONAL MATCH (c)-[:CONTAINS]->(cl:Clause)
        OPTIONAL MATCH (c)-[:IMPOSES]->(o:Obligation)
        OPTIONAL MATCH (c)-[:HAS_RISK]->(r:RiskFlag)
        DETACH DELETE c, ch, cl, o, r
    """, {"id": contract_id})
    pg.delete_contract(contract_id)
    return {"message": f"Deleted {contract_id}"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(400, "Empty question")

    query_type = llm.classify_query(req.question)

    # ── Graph RAG ─────────────────────────────────────────────
    t0           = time.time()
    graph_chunks, debug = retriever.retrieve(req.question, query_type)
    graph_texts  = [c.text for c in graph_chunks[:6]]
    graph_answer = (
        llm.generate_answer(req.question, graph_texts)
        if graph_texts
        else "No relevant contract passages found."
    )
    graph_time   = round(time.time() - t0, 2)

    t1             = time.time()
    base_resp      = baseline.query(req.question)
    baseline_time  = round(time.time() - t1, 2)

    graph_only = sum(
        1 for c in graph_chunks
        if c.retrieval_method != "vector"
    )

    sources = [
        {
            "text":           c.text[:300],
            "method":         c.retrieval_method,
            "score":          round(c.score, 3),
            "contract_title": c.contract_title,
            "clause_context": c.clause_context,
        }
        for c in graph_chunks[:6]
    ]

    # ── RAGAS Evaluation ──────────────────────────────────────
    baseline_texts = base_resp.retrieved_texts if hasattr(base_resp, "retrieved_texts") else []

    graph_eval    = evaluator.evaluate(req.question, graph_answer, graph_texts)
    baseline_eval = evaluator.evaluate(req.question, base_resp.answer, baseline_texts)

    print("\n" + "="*70)
    print(f"  RAGAS EVALUATION — \"{req.question[:60]}\"")
    print("="*70)
    print(f"  {'Metric':<22} {'Graph RAG':>10} {'Baseline':>10}  {'Winner':>10}")
    print(f"  {'-'*22} {'-'*10} {'-'*10}  {'-'*10}")
    for name, g, b in [
        ("Faithfulness",      graph_eval.faithfulness,      baseline_eval.faithfulness),
        ("Answer Relevancy",  graph_eval.answer_relevancy,  baseline_eval.answer_relevancy),
        ("Context Precision", graph_eval.context_precision,  baseline_eval.context_precision),
        ("Context Recall",    graph_eval.context_recall,     baseline_eval.context_recall),
    ]:
        winner = "Graph" if g > b else "Baseline" if b > g else "Tie"
        print(f"  {name:<22} {g:>10.3f} {b:>10.3f}  {winner:>10}")
    print(f"  {'-'*22} {'-'*10} {'-'*10}  {'-'*10}")
    print(f"  {'OVERALL':<22} {graph_eval.overall():>10.3f} {baseline_eval.overall():>10.3f}  "
          f"{'Graph' if graph_eval.overall() > baseline_eval.overall() else 'Baseline' if baseline_eval.overall() > graph_eval.overall() else 'Tie':>10}")
    print("="*70 + "\n")

    pg.save_query({
        "question":              req.question,
        "graph_answer":          graph_answer,
        "baseline_answer":       base_resp.answer,
        "extractive_answer":     "",
        "extractive_confidence": 0.0,
        "graph_chunks":          len(graph_chunks),
        "graph_only_chunks":     graph_only,
        "graph_latency":         graph_time,
        "baseline_latency":      baseline_time,
        "graph_faithfulness":    graph_eval.faithfulness,
        "graph_relevancy":       graph_eval.answer_relevancy,
        "graph_precision":       graph_eval.context_precision,
        "graph_recall":          graph_eval.context_recall,
        "baseline_faithfulness": baseline_eval.faithfulness,
        "baseline_relevancy":    baseline_eval.answer_relevancy,
        "baseline_precision":    baseline_eval.context_precision,
        "baseline_recall":       baseline_eval.context_recall,
    })

    return QueryResponse(
        question=req.question,
        graph_answer=graph_answer,
        baseline_answer=base_resp.answer,
        graph_chunks=len(graph_chunks),
        graph_only_chunks=graph_only,
        graph_latency=graph_time,
        baseline_latency=baseline_time,
        sources=sources,
        graph_chunk_texts=[c.text for c in graph_chunks[:6]],
        baseline_chunk_texts=baseline_texts,
    )


@app.get("/history")
def get_history(limit: int = 50):
    return pg.get_history(limit)


@app.get("/risks")
def get_risks():
    return pg.get_risk_flags()


@app.get("/graph/entities")
def graph_entities(limit: int = 120):
    nodes = conn.run("""
        MATCH (n)
        WHERE n:Contract OR n:Party OR n:Clause
           OR n:Jurisdiction OR n:RiskFlag
        RETURN id(n) AS id, labels(n)[0] AS type,
               COALESCE(n.name, n.title, n.type, n.id) AS label,
               n.risk_level AS risk_level,
               n.severity AS severity
        LIMIT $limit
    """, {"limit": limit})

    edges = conn.run("""
        MATCH (a)-[r]->(b)
        WHERE (a:Contract OR a:Party OR a:Clause OR a:Jurisdiction)
          AND (b:Contract OR b:Party OR b:Clause OR b:Jurisdiction OR b:RiskFlag)
          AND type(r) IN [
            'HAS_PARTY','PARTY_TO','CONTAINS','GOVERNED_BY',
            'CONFLICTS_WITH','RELATED_TO','HAS_RISK','IMPOSES'
          ]
        RETURN id(a) AS source, id(b) AS target, type(r) AS relation
        LIMIT $limit
    """, {"limit": limit * 2})

    return {"nodes": nodes, "edges": edges}


@app.get("/graph/stats")
def graph_stats():
    return {
        "neo4j":    get_stats(conn),
        "postgres": {
            "contracts": len(pg.get_contracts()),
            "queries":   len(pg.get_history(10000)),
            "risks":     len(pg.get_risk_flags()),
        },
        "baseline_chunks": baseline.store.size() if baseline else 0,
    }


class EvalRequest(BaseModel):
    question: str
    answer:   str
    contexts: List[str]


@app.post("/evaluate")
def evaluate_endpoint(req: EvalRequest):
    """Standalone evaluation — score any question/answer/context triple."""
    metrics = evaluator.evaluate(req.question, req.answer, req.contexts)
    return {
        **metrics.to_dict(),
        "overall": metrics.overall(),
    }


@app.get("/health")
def health():
    return {
        "status":          "ok",
        "neo4j":           "connected" if conn     else "disconnected",
        "postgres":        "connected" if pg       else "disconnected",
        "baseline_chunks": baseline.store.size()   if baseline else 0,
    }


@app.get("/reload-baseline")
def reload_baseline():
    """Full reload — clears and rebuilds baseline store from all Neo4j chunks."""
    baseline.store.texts     = []
    baseline.store.embeddings = []
    baseline.store.metadata  = []
    chunks = conn.run("MATCH (c:Chunk) RETURN c.text AS text, c.id AS id")
    count = 0
    for row in chunks:
        if row["text"]:
            emb = embedder.embed(row["text"])
            baseline.store.add(row["text"], emb, {"id": row["id"]})
            count += 1
    print(f" Baseline reloaded: {count} chunks")
    return {"loaded": count}
