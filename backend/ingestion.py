
import os
import re
import uuid
import time
import numpy as np
from pathlib import Path
from typing import List, Dict, Callable, Optional
from rich.console import Console

console = Console()

CHUNK_SIZE    = int(os.getenv("MAX_CHUNK_SIZE", 200))   # words, reduced from 512
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP",  40))    # words overlap
SIM_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.55))


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        import PyPDF2
        text = []
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text.append(t)
        return "\n".join(text)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def split_text(text: str,
               chunk_size: int = CHUNK_SIZE,
               overlap: int    = CHUNK_OVERLAP) -> List[str]:

    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    chunks  = []
    current = []
    current_words = 0

    for sentence in sentences:
        words = sentence.split()
        w     = len(words)

        # Force new chunk on article/section headers
        is_header = bool(re.match(
            r'^(ARTICLE\s+\d+|Section\s+\d+|\d+\.\d+\s+[A-Z])',
            sentence.strip()
        ))

        if is_header and current_words > 50:
            # Save current chunk, start fresh at header
            chunk_text = " ".join(current).strip()
            if len(chunk_text) > 80:
                chunks.append(chunk_text)
            current       = words
            current_words = w
            continue

        if current_words + w > chunk_size and current_words > 50:
            # Save chunk
            chunk_text = " ".join(current).strip()
            if len(chunk_text) > 80:
                chunks.append(chunk_text)
            # Overlap: keep last `overlap` words
            overlap_words = current[-overlap:] if len(current) > overlap else current
            current       = overlap_words + words
            current_words = len(current)
        else:
            current.extend(words)
            current_words += w

    # Last chunk
    if current:
        chunk_text = " ".join(current).strip()
        if len(chunk_text) > 80:
            chunks.append(chunk_text)

    return chunks


class LegalIngestion:
    def __init__(self, conn, embedder, llm, pg):
        self.conn     = conn
        self.embedder = embedder
        self.llm      = llm
        self.pg       = pg

    def ingest(self, contract_id: str, file_path: str,
               filename: str, progress_callback: Optional[Callable] = None) -> Dict:

        def progress(stage: str, pct: int):
            if progress_callback:
                progress_callback(stage, pct)

        t0 = time.time()

        progress("Extracting text", 5)
        self.pg.log_stage(contract_id, "text_extraction", "started")
        text = extract_text(file_path)
        if not text.strip():
            raise ValueError("No text could be extracted")
        self.pg.log_stage(contract_id, "text_extraction", "complete",
                          f"{len(text)} chars")

        progress("Chunking text", 15)
        chunks = split_text(text)
        self.pg.log_stage(contract_id, "chunking", "complete",
                          f"{len(chunks)} chunks")
        console.print(f"[cyan]Chunked into {len(chunks)} chunks "
                      f"(avg {len(text)//max(len(chunks),1)//5} words each)[/cyan]")

        progress("Embedding chunks", 25)
        embeddings = self.embedder.embed_batch(chunks)
        self.pg.log_stage(contract_id, "embedding", "complete")

        progress("Extracting legal entities", 45)
        self.pg.log_stage(contract_id, "entity_extraction", "started")
        entities = self.llm.extract_legal_entities(text)

        self.pg.save_clauses(contract_id, entities.get("clauses", []))
        self.pg.save_risk_flags(contract_id, entities.get("risk_flags", []))
        self.pg.log_stage(
            contract_id, "entity_extraction", "complete",
            f"{len(entities.get('clauses', []))} clauses, "
            f"{len(entities.get('risk_flags', []))} risk flags"
        )

        progress("Building knowledge graph", 65)
        self.pg.log_stage(contract_id, "graph_build", "started")
        chunk_ids = self._build_graph(contract_id, filename, entities,
                                      chunks, embeddings)

        progress("Building graph edges", 85)
        edge_count = self._build_similarity_edges(chunk_ids, embeddings)
        self._build_conflict_edges(
            contract_id,
            entities.get("clauses", []),
            entities.get("relationships", [])
        )
        self._link_related_contracts(contract_id, entities.get("parties", []))

        self.pg.log_stage(contract_id, "graph_build", "complete",
                          f"{len(chunk_ids)} chunks, {edge_count} edges")

        flags      = entities.get("risk_flags", [])
        risk_score = (sum(1 for f in flags if f.get("severity") == "high")
                      / max(len(flags), 1))

        progress("Complete", 100)
        duration = int((time.time() - t0) * 1000)

        console.print(
            f"[green] Ingested {filename}: "
            f"{len(chunks)} chunks, {edge_count} edges, "
            f"{len(flags)} risk flags, {duration}ms[/green]"
        )

        return {
            "chunks":        len(chunks),
            "edges":         edge_count,
            "clauses":       len(entities.get("clauses", [])),
            "risk_flags":    len(flags),
            "risk_score":    round(risk_score, 2),
            "title":         entities.get("title", filename),
            "contract_type": entities.get("contract_type", "Unknown"),
            "parties":       [p.get("name","") for p in entities.get("parties",[])],
            "jurisdiction":  entities.get("jurisdiction", ""),
            "effective_date": entities.get("effective_date", ""),
        }

    def _build_graph(self, contract_id, filename, entities,
                     chunks, embeddings) -> List[str]:

        self.conn.run("""
            MERGE (c:Contract {id: $id})
            SET c.filename       = $filename,
                c.title          = $title,
                c.contract_type  = $type,
                c.effective_date = $eff_date,
                c.expiry_date    = $exp_date,
                c.jurisdiction   = $jurisdiction,
                c.created        = datetime()
        """, {
            "id":          contract_id,
            "filename":    filename,
            "title":       entities.get("title", filename),
            "type":        entities.get("contract_type", "Unknown"),
            "eff_date":    entities.get("effective_date", ""),
            "exp_date":    entities.get("expiry_date", ""),
            "jurisdiction": entities.get("jurisdiction", ""),
        })

        if entities.get("jurisdiction"):
            self.conn.run("""
                MERGE (j:Jurisdiction {name: $name})
                WITH j
                MATCH (c:Contract {id: $cid})
                MERGE (c)-[:GOVERNED_BY]->(j)
            """, {"name": entities["jurisdiction"], "cid": contract_id})

        for party in entities.get("parties", []):
            name = party.get("name", "").strip()
            if not name:
                continue
            self.conn.run("""
                MERGE (p:Party {name: $name})
                SET p.type = $type
                WITH p
                MATCH (c:Contract {id: $cid})
                MERGE (c)-[:HAS_PARTY {role: $role}]->(p)
                MERGE (p)-[:PARTY_TO]->(c)
            """, {
                "name": name,
                "type": party.get("type", ""),
                "role": party.get("role", ""),
                "cid":  contract_id,
            })

        for i, clause in enumerate(entities.get("clauses", [])):
            clause_id   = f"{contract_id}_clause_{i}"
            clause_text = clause.get("summary", "")
            clause_emb  = self.embedder.embed(clause_text) if clause_text else []

            self.conn.run("""
                CREATE (cl:Clause {
                    id:          $id,
                    type:        $type,
                    name:        $name,
                    summary:     $summary,
                    risk_level:  $risk,
                    embedding:   $emb,
                    contract_id: $cid
                })
                WITH cl
                MATCH (c:Contract {id: $cid})
                MERGE (c)-[:CONTAINS]->(cl)
            """, {
                "id":      clause_id,
                "type":    clause.get("type", "other"),
                "name":    clause.get("name", ""),
                "summary": clause_text,
                "risk":    clause.get("risk_level", "low"),
                "emb":     clause_emb,
                "cid":     contract_id,
            })

        for i, obl in enumerate(entities.get("obligations", [])):
            desc = obl.get("description", "").strip()
            if not desc:
                continue
            self.conn.run("""
                CREATE (o:Obligation {
                    id:          $id,
                    description: $desc,
                    party:       $party,
                    deadline:    $deadline,
                    evidence:    $evidence,
                    contract_id: $cid
                })
                WITH o
                MATCH (c:Contract {id: $cid})
                MERGE (c)-[:IMPOSES]->(o)
            """, {
                "id":       f"{contract_id}_obl_{i}",
                "desc":     desc,
                "party":    obl.get("party", ""),
                "deadline": obl.get("deadline", ""),
                "evidence": obl.get("evidence", ""),
                "cid":      contract_id,
            })

        for i, flag in enumerate(entities.get("risk_flags", [])):
            desc = flag.get("description", "").strip()
            if not desc:
                continue
            self.conn.run("""
                CREATE (r:RiskFlag {
                    id:          $id,
                    type:        $type,
                    severity:    $severity,
                    description: $desc,
                    clause_ref:  $clause_ref,
                    contract_id: $cid
                })
                WITH r
                MATCH (c:Contract {id: $cid})
                MERGE (c)-[:HAS_RISK]->(r)
            """, {
                "id":         f"{contract_id}_risk_{i}",
                "type":       flag.get("type", "other"),
                "severity":   flag.get("severity", "medium"),
                "desc":       desc,
                "clause_ref": flag.get("clause_ref", ""),
                "cid":        contract_id,
            })

        chunk_ids = []
        prev_id   = None
        for i, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{contract_id}_chunk_{i}"
            chunk_ids.append(chunk_id)

            self.conn.run("""
                CREATE (ch:Chunk {
                    id:          $id,
                    text:        $text,
                    index:       $idx,
                    contract_id: $cid,
                    embedding:   $emb
                })
                WITH ch
                MATCH (c:Contract {id: $cid})
                MERGE (c)-[:HAS_CHUNK]->(ch)
            """, {
                "id":   chunk_id,
                "text": chunk_text,
                "idx":  i,
                "cid":  contract_id,
                "emb":  emb,
            })

            if prev_id:
                self.conn.run("""
                    MATCH (a:Chunk {id: $a}),(b:Chunk {id: $b})
                    MERGE (a)-[:NEXT]->(b)
                """, {"a": prev_id, "b": chunk_id})
            prev_id = chunk_id

        return chunk_ids

    def _build_similarity_edges(self, chunk_ids: List[str],
                                 embeddings: List[List[float]]) -> int:
        if len(chunk_ids) < 2:
            return 0

        emb_array = np.array(embeddings)
        norms     = np.linalg.norm(emb_array, axis=1, keepdims=True)
        norms     = np.where(norms == 0, 1, norms)
        normed    = emb_array / norms
        sim_matrix = np.dot(normed, normed.T)

        edge_count = 0
        for i in range(len(chunk_ids)):
            for j in range(i + 1, len(chunk_ids)):
                sim = float(sim_matrix[i, j])
                if sim >= SIM_THRESHOLD and abs(i - j) > 1:
                    self.conn.run("""
                        MATCH (a:Chunk {id: $a}),(b:Chunk {id: $b})
                        MERGE (a)-[r:SIMILAR_TO]-(b)
                        SET r.score = $score
                    """, {
                        "a":     chunk_ids[i],
                        "b":     chunk_ids[j],
                        "score": round(sim, 3),
                    })
                    edge_count += 1
        return edge_count

    def _build_conflict_edges(self, contract_id: str,
                               clauses: List[Dict],
                               relationships: List[Dict]):
        clause_by_name = {}
        for i, c in enumerate(clauses):
            name = c.get("name", c.get("type", "")).strip().lower()
            if name:
                clause_by_name[name] = f"{contract_id}_clause_{i}"

        conflict_rels = [
            r for r in relationships
            if r.get("relation", "").upper() == "CONFLICTS_WITH"
        ]

        for rel in conflict_rels:
            subj = rel.get("subject", "").strip().lower()
            obj  = rel.get("object",  "").strip().lower()
            a_id = clause_by_name.get(subj)
            b_id = clause_by_name.get(obj)

            if a_id and b_id:
                self.conn.run("""
                    MATCH (a:Clause {id:$a}),(b:Clause {id:$b})
                    MERGE (a)-[r:CONFLICTS_WITH]->(b)
                    SET r.reason   = $reason,
                        r.evidence = $evidence
                """, {
                    "a":        a_id,
                    "b":        b_id,
                    "reason":   f"{rel.get('subject','')} conflicts with {rel.get('object','')}",
                    "evidence": rel.get("evidence", ""),
                })

    def _link_related_contracts(self, contract_id: str, parties: List[Dict]):
        for party in parties:
            name = party.get("name", "").strip()
            if not name:
                continue
            related = self.conn.run("""
                MATCH (p:Party {name: $name})-[:PARTY_TO]->(c:Contract)
                WHERE c.id <> $cid
                RETURN c.id AS related_id
            """, {"name": name, "cid": contract_id})

            for r in related:
                self.conn.run("""
                    MATCH (a:Contract {id:$a}),(b:Contract {id:$b})
                    MERGE (a)-[r:RELATED_TO]->(b)
                    SET r.shared_party = $party
                """, {
                    "a":     contract_id,
                    "b":     r["related_id"],
                    "party": name,
                })
