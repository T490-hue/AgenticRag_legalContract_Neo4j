
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery("legal_rag", broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
)


@celery.task(bind=True, name="process_contract")
def process_contract_task(self, contract_id: str, file_path: str, filename: str):
    from graph_db import Neo4jConnection
    from embeddings import EmbeddingModel
    from ollama_utils import OllamaLLM
    from postgres_db import PostgresDB
    from ingestion import LegalIngestion

    pg       = PostgresDB()
    conn     = Neo4jConnection()
    embedder = EmbeddingModel()
    llm      = OllamaLLM()

    try:
        pg.update_contract(contract_id, status="processing")
        self.update_state(state="PROGRESS", meta={"stage": "starting", "progress": 0})

        ingestion = LegalIngestion(conn, embedder, llm, pg)
        stats = ingestion.ingest(
            contract_id=contract_id,
            file_path=file_path,
            filename=filename,
            progress_callback=lambda stage, pct: self.update_state(
                state="PROGRESS",
                meta={"stage": stage, "progress": pct}
            ),
        )

        pg.update_contract(
            contract_id,
            status="complete",
            chunk_count=stats["chunks"],
            clause_count=stats["clauses"],
            risk_score=stats["risk_score"],
            title=stats.get("title", filename),
            contract_type=stats.get("contract_type", "Unknown"),
            jurisdiction=stats.get("jurisdiction", ""),
            effective_date=stats.get("effective_date", ""),
            parties=stats.get("parties", []),
        )
        return {"contract_id": contract_id, "status": "complete", **stats}

    except Exception as e:
        pg.update_contract(contract_id, status="failed", error_msg=str(e))
        raise
    finally:
        conn.close()
