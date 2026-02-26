
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://admin:legalrag@localhost:5432/legalrag")


class PostgresDB:
    def __init__(self):
        try:
            self.engine = create_engine(POSTGRES_URL, pool_pre_ping=True)
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            console.print("[green]✓ Connected to PostgreSQL[/green]")
        except Exception as e:
            console.print(f"[red]✗ PostgreSQL failed: {e}[/red]")
            raise

    def _exec(self, query: str, params: dict = None) -> list:
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            try:
                return [dict(row._mapping) for row in result]
            except Exception:
                return []

    # ── Contracts ─────────────────────────────────────────────
    def create_contract(self, filename: str, file_size: int) -> str:
        cid = str(uuid.uuid4())
        self._exec("""
            INSERT INTO contracts (id, filename, file_size, status, created_at)
            VALUES (:id, :filename, :file_size, 'pending', NOW())
        """, {"id": cid, "filename": filename, "file_size": file_size})
        return cid

    def update_contract(self, cid: str, **kwargs):
        if not kwargs:
            return
        sets = ", ".join([f"{k} = :{k}" for k in kwargs])
        kwargs["id"] = cid
        self._exec(f"UPDATE contracts SET {sets}, updated_at = NOW() WHERE id = :id", kwargs)

    def get_contracts(self) -> List[Dict]:
        return self._exec("""
            SELECT id, filename, title, contract_type, effective_date,
                   jurisdiction, parties, status, chunk_count, clause_count,
                   risk_score, file_size, created_at, error_msg
            FROM contracts ORDER BY created_at DESC
        """)

    def get_contract(self, cid: str) -> Optional[Dict]:
        rows = self._exec("SELECT * FROM contracts WHERE id = :id", {"id": cid})
        return rows[0] if rows else None

    def delete_contract(self, cid: str):
        self._exec("DELETE FROM contracts WHERE id = :id", {"id": cid})

    # ── Query History ─────────────────────────────────────────
    def save_query(self, data: Dict) -> str:
        qid = str(uuid.uuid4())
        self._exec("""
            INSERT INTO query_history (
                id, question, graph_answer, baseline_answer,
                extractive_answer, extractive_confidence,
                graph_chunks, graph_only_chunks,
                graph_latency, baseline_latency, created_at
            ) VALUES (
                :id, :question, :graph_answer, :baseline_answer,
                :extractive_answer, :extractive_confidence,
                :graph_chunks, :graph_only_chunks,
                :graph_latency, :baseline_latency, NOW()
            )
        """, {"id": qid, **data})
        return qid

    def get_history(self, limit: int = 50) -> List[Dict]:
        return self._exec("""
            SELECT id, question, graph_answer, baseline_answer,
                   extractive_answer, extractive_confidence,
                   graph_latency, baseline_latency, created_at
            FROM query_history
            ORDER BY created_at DESC LIMIT :limit
        """, {"limit": limit})

    # ── Processing Log ────────────────────────────────────────
    def log_stage(self, cid: str, stage: str, status: str,
                  message: str = "", duration_ms: int = 0):
        self._exec("""
            INSERT INTO processing_log
                (id, contract_id, stage, status, message, duration_ms, created_at)
            VALUES (:id, :cid, :stage, :status, :message, :duration_ms, NOW())
        """, {
            "id": str(uuid.uuid4()), "cid": cid,
            "stage": stage, "status": status,
            "message": message, "duration_ms": duration_ms,
        })

    def get_log(self, cid: str) -> List[Dict]:
        return self._exec("""
            SELECT stage, status, message, duration_ms, created_at
            FROM processing_log WHERE contract_id = :cid
            ORDER BY created_at ASC
        """, {"cid": cid})

    # ── Clauses ───────────────────────────────────────────────
    def save_clauses(self, cid: str, clauses: List[Dict]):
        for c in clauses:
            self._exec("""
                INSERT INTO clauses_extracted
                    (id, contract_id, clause_type, clause_text, risk_level, risk_reason)
                VALUES (:id, :cid, :type, :text, :risk, :reason)
            """, {
                "id":     str(uuid.uuid4()),
                "cid":    cid,
                "type":   c.get("type", ""),
                "text":   c.get("summary", ""),
                "risk":   c.get("risk_level", "low"),
                "reason": c.get("risk_reason", ""),
            })

    # ── Risk Flags ────────────────────────────────────────────
    def save_risk_flags(self, cid: str, flags: List[Dict]):
        for f in flags:
            self._exec("""
                INSERT INTO risk_flags
                    (id, contract_id, flag_type, severity, description, clause_ref)
                VALUES (:id, :cid, :type, :severity, :desc, :clause_ref)
            """, {
                "id":         str(uuid.uuid4()),
                "cid":        cid,
                "type":       f.get("type", ""),
                "severity":   f.get("severity", "low"),
                "desc":       f.get("description", ""),
                "clause_ref": f.get("clause_ref", ""),
            })

    def get_risk_flags(self, cid: str = None) -> List[Dict]:
        if cid:
            return self._exec("""
                SELECT * FROM risk_flags WHERE contract_id = :cid
                ORDER BY severity DESC
            """, {"cid": cid})
        return self._exec("""
            SELECT r.*, c.filename, c.title
            FROM risk_flags r JOIN contracts c ON r.contract_id = c.id
            ORDER BY r.severity DESC, r.created_at DESC
            LIMIT 100
        """)
