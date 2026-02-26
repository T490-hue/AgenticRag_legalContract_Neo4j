

import os
from typing import List, Dict, Tuple, Any
from dataclasses import dataclass
from rich.console import Console

console = Console()
TOP_K   = int(os.getenv("TOP_K_RETRIEVAL", 5))

CLAUSE_SYNONYMS = {
    "limitation_of_liability": [
        "liability cap", "liability limit", "cap on liability",
        "maximum liability", "total liability", "liability ceiling",
        "limit liability", "limited liability", "liable", "capped at",
        "shall not exceed", "not exceed", "limitation of liability",
    ],
    "indemnification": [
        "indemnif", "indemnity", "hold harmless", "defend and hold",
        "indemnification", "losses damages liabilities",
    ],
    "termination": [
        "terminat", "terminate", "termination", "end the agreement",
        "cancel", "cancellation", "expir", "expiration",
    ],
    "confidentiality": [
        "confidential", "nda", "non-disclosure", "proprietary",
        "trade secret", "disclose", "disclosure",
    ],
    "ip_ownership_assignment": [
        "intellectual property", "ip ownership", "ip assignment",
        "patent", "copyright", "trademark", "invention", "assign",
        "ownership of", "owns the",
    ],
    "non_compete": [
        "non-compete", "non compete", "noncompete", "compete",
        "competitive", "competition", "solicitation",
    ],
    "governing_law": [
        "governing law", "jurisdiction", "governed by", "laws of",
        "applicable law", "choice of law",
    ],
    "price_or_payment_terms": [
        "payment", "pay", "fee", "fees", "price", "cost", "invoice",
        "royalt", "royalty", "royalties", "compensation", "financial",
        "money", "dollar", "amount", "remuneration",
    ],
    "dispute_resolution": [
        "dispute", "arbitration", "arbitrat", "mediation", "litigation",
        "court", "legal proceedings", "resolve",
    ],
    "warranty": [
        "warrant", "warranty", "warrants", "guarantee", "representation",
    ],
    "renewal_term": [
        "renew", "renewal", "auto-renew", "automatically renew",
        "extension", "extend",
    ],
    "audit_rights": [
        "audit", "inspect", "examination", "review records",
    ],
    "change_of_control": [
        "change of control", "acquisition", "merger", "acquired",
        "takeover", "assignment",
    ],
    "force_majeure": [
        "force majeure", "act of god", "natural disaster",
        "unforeseeable", "beyond control",
    ],
}


def detect_clause_types(query: str) -> List[str]:
    query_lower = query.lower()
    matched = []
    for clause_type, synonyms in CLAUSE_SYNONYMS.items():
        if any(syn in query_lower for syn in synonyms):
            matched.append(clause_type)
    return matched


@dataclass
class RetrievedChunk:
    chunk_id:         str
    text:             str
    score:            float
    retrieval_method: str
    contract_id:      str
    contract_title:   str = ""
    clause_context:   str = ""


class LegalRetriever:
    def __init__(self, conn, embedder):
        self.conn     = conn
        self.embedder = embedder

    def keyword_rerank(self, chunks: List[RetrievedChunk],
                       query: str) -> List[RetrievedChunk]:
        stopwords = {
            "the","a","an","is","are","was","were","how","what","who",
            "where","when","why","did","do","does","in","of","to","and",
            "for","with","that","this","from","by","on","at","as","be",
            "have","has","had","which","their","they","can","between",
            "contract","agreement","party","parties","clause","section"
        }
        keywords = [
            w.lower().strip("?.,") for w in query.split()
            if len(w) > 3 and w.lower() not in stopwords
        ]
        for chunk in chunks:
            text_lower = chunk.text.lower()
            hits = sum(1 for kw in keywords if kw in text_lower)
            chunk.score = chunk.score + (hits * 0.15)
        return sorted(chunks, key=lambda x: x.score, reverse=True)

    def vector_search(self, query: str, top_k: int = TOP_K) -> List[RetrievedChunk]:
        emb     = self.embedder.embed(query)
        results = self.conn.run("""
            CALL db.index.vector.queryNodes('chunk_vector', $k, $emb)
            YIELD node AS chunk, score
            MATCH (c:Contract)-[:HAS_CHUNK]->(chunk)
            RETURN chunk.id AS id, chunk.text AS text,
                   chunk.contract_id AS contract_id,
                   c.title AS title, score
            ORDER BY score DESC
        """, {"emb": emb, "k": top_k * 2})

        return [
            RetrievedChunk(
                chunk_id=r["id"], text=r["text"], score=r["score"],
                retrieval_method="vector",
                contract_id=r["contract_id"] or "",
                contract_title=r["title"] or "",
            )
            for r in results[:top_k]
        ]

    def clause_search(self, clause_types: List[str]) -> List[RetrievedChunk]:
      
        if not clause_types:
            return []

        results = self.conn.run("""
            MATCH (cl:Clause)
            WHERE cl.type IN $types
            MATCH (c:Contract)-[:DERIVED_FROM]->(cl)
            MATCH (c)-[:HAS_CHUNK]->(chunk:Chunk)
            RETURN chunk.id AS id, chunk.text AS text,
                   chunk.contract_id AS contract_id,
                   c.title AS title,
                   cl.type AS clause_type,
                   cl.risk_level AS risk_level,
                   0.92 AS score
            LIMIT $limit
        """, {"types": clause_types, "limit": TOP_K * 3})

        return [
            RetrievedChunk(
                chunk_id=r["id"], text=r["text"], score=r["score"],
                retrieval_method="clause",
                contract_id=r["contract_id"] or "",
                contract_title=r["title"] or "",
                clause_context=f"clause:{r['clause_type']} risk:{r['risk_level']}",
            )
            for r in results
        ]

    def comparative_search(self, clause_types: List[str]) -> List[RetrievedChunk]:
       
        if len(clause_types) < 2:
            return []

        results = []
        for ct in clause_types:
            rows = self.conn.run("""
		MATCH (cl:Clause {type: $type})
		MATCH (cl)-[:DERIVED_FROM]->(chunk:Chunk)
		MATCH (c:Contract)-[:HAS_CHUNK]->(chunk)
                RETURN chunk.id AS id, chunk.text AS text,
                       chunk.contract_id AS contract_id,
                       c.title AS title,
                       $type AS clause_type,
                       0.95 AS score
                LIMIT $limit
            """, {"type": ct, "limit": TOP_K})
            results.extend(rows)

        return [
            RetrievedChunk(
                chunk_id=r["id"], text=r["text"], score=r["score"],
                retrieval_method="comparative",
                contract_id=r["contract_id"] or "",
                contract_title=r["title"] or "",
                clause_context=f"comparative:{r['clause_type']}",
            )
            for r in results
        ]

    def graph_expand(self, seed_ids: List[str]) -> List[RetrievedChunk]:
        if not seed_ids:
            return []

        results = self.conn.run("""
            MATCH (seed:Chunk) WHERE seed.id IN $seed_ids
            MATCH (seed)-[r:SIMILAR_TO]-(neighbor:Chunk)
            WHERE NOT neighbor.id IN $seed_ids
            MATCH (c:Contract)-[:HAS_CHUNK]->(neighbor)
            RETURN neighbor.id AS id, neighbor.text AS text,
                   neighbor.contract_id AS contract_id,
                   c.title AS title, r.score AS score
            ORDER BY score DESC LIMIT $limit
        """, {"seed_ids": seed_ids, "limit": TOP_K})

        return [
            RetrievedChunk(
                chunk_id=r["id"], text=r["text"],
                score=float(r["score"] or 0.5),
                retrieval_method="graph_expand",
                contract_id=r["contract_id"] or "",
                contract_title=r["title"] or "",
            )
            for r in results
        ]

    def structured_search(self, query: str,
                          query_type: str = "clause") -> List[RetrievedChunk]:
        query_lower = query.lower()

        if any(w in query_lower for w in ["risk","risky","dangerous","missing","flag"]):
            results = self.conn.run("""
                MATCH (r:RiskFlag)-[:FLAGS|HAS_RISK]-(c:Contract)
                WHERE r.severity IN ['high', 'medium']
                MATCH (c)-[:HAS_CHUNK]->(chunk:Chunk)
                RETURN chunk.id AS id, chunk.text AS text,
                       chunk.contract_id AS contract_id,
                       c.title AS title,
                       r.type + ': ' + r.description AS context,
                       CASE r.severity WHEN 'high' THEN 0.95 ELSE 0.8 END AS score
                LIMIT $limit
            """, {"limit": TOP_K})

        elif any(w in query_lower for w in ["conflict","contradict","inconsistent","clash"]):
            results = self.conn.run("""
                MATCH (a:Clause)-[r:CONFLICTS_WITH]->(b:Clause)
                MATCH (c:Contract)-[:CONTAINS]->(a)
                MATCH (c)-[:HAS_CHUNK]->(chunk:Chunk)
                RETURN chunk.id AS id, chunk.text AS text,
                       chunk.contract_id AS contract_id,
                       c.title AS title,
                       a.type + ' CONFLICTS_WITH ' + b.type AS context,
                       0.95 AS score
                LIMIT $limit
            """, {"limit": TOP_K})

        elif any(w in query_lower for w in ["party","parties","company","who","signed"]):
            results = self.conn.run("""
                MATCH (p:Party)-[:PARTY_TO]->(c:Contract)
                MATCH (c)-[:HAS_CHUNK]->(chunk:Chunk)
                RETURN chunk.id AS id, chunk.text AS text,
                       chunk.contract_id AS contract_id,
                       c.title AS title,
                       'Party: ' + p.name AS context,
                       0.85 AS score
                LIMIT $limit
            """, {"limit": TOP_K})

        elif any(w in query_lower for w in ["obligation","must","required","shall","duty","remain"]):
            results = self.conn.run("""
                MATCH (c:Contract)-[:IMPOSES]->(o:Obligation)
                MATCH (c)-[:HAS_CHUNK]->(chunk:Chunk)
                RETURN chunk.id AS id, chunk.text AS text,
                       chunk.contract_id AS contract_id,
                       c.title AS title,
                       o.party + ': ' + o.description AS context,
                       0.85 AS score
                LIMIT $limit
            """, {"limit": TOP_K})

        elif any(w in query_lower for w in ["terminat","after termination","post-termination","survive"]):
            # Special: post-termination obligations
            results = self.conn.run("""
                MATCH (cl:Clause)
                WHERE cl.type IN ['termination','price_or_payment_terms','royalty']
                MATCH (c:Contract)-[:CONTAINS]->(cl)
                MATCH (c)-[:HAS_CHUNK]->(chunk:Chunk)
                RETURN chunk.id AS id, chunk.text AS text,
                       chunk.contract_id AS contract_id,
                       c.title AS title,
                       'post-termination: ' + cl.type AS context,
                       0.9 AS score
                LIMIT $limit
            """, {"limit": TOP_K})

        else:
            return []

        return [
            RetrievedChunk(
                chunk_id=r["id"], text=r["text"],
                score=float(r.get("score", 0.8)),
                retrieval_method="structured",
                contract_id=r["contract_id"] or "",
                contract_title=r["title"] or "",
                clause_context=r.get("context", ""),
            )
            for r in results
        ]

    def sequential_expand(self, seed_ids: List[str]) -> List[RetrievedChunk]:
        if not seed_ids:
            return []
        results = self.conn.run("""
            MATCH (seed:Chunk) WHERE seed.id IN $seed_ids
            MATCH (neighbor:Chunk)
            WHERE (seed)-[:NEXT]->(neighbor) OR (neighbor)-[:NEXT]->(seed)
            AND NOT neighbor.id IN $seed_ids
            MATCH (c:Contract)-[:HAS_CHUNK]->(neighbor)
            RETURN DISTINCT neighbor.id AS id, neighbor.text AS text,
                   neighbor.contract_id AS contract_id,
                   c.title AS title, 0.6 AS score
        """, {"seed_ids": seed_ids[:3]})

        return [
            RetrievedChunk(
                chunk_id=r["id"], text=r["text"], score=r["score"],
                retrieval_method="sequential",
                contract_id=r["contract_id"] or "",
                contract_title=r["title"] or "",
            )
            for r in results
        ]

    def retrieve(
        self,
        query:      str,
        query_type: str       = "clause",
        entities:   List[str] = None,
    ) -> Tuple[List[RetrievedChunk], Dict[str, Any]]:
        debug = {"query_type": query_type, "strategies": []}
        seen: Dict[str, RetrievedChunk] = {}

        # Detect clause types from query BEFORE anything else
        detected_types = detect_clause_types(query)
        debug["detected_clause_types"] = detected_types

        for c in self.vector_search(query):
            seen[c.chunk_id] = c
        debug["strategies"].append("vector")

        seed_ids = list(seen.keys())

        if detected_types:
            for c in self.clause_search(detected_types):
                if c.chunk_id not in seen:
                    seen[c.chunk_id] = c
            debug["strategies"].append("clause")

        if len(detected_types) >= 2 or query_type == "comparative":
            types_for_compare = detected_types or []
            for c in self.comparative_search(types_for_compare):
                if c.chunk_id not in seen:
                    seen[c.chunk_id] = c
            debug["strategies"].append("comparative")

        for c in self.graph_expand(seed_ids):
            if c.chunk_id not in seen:
                seen[c.chunk_id] = c
        debug["strategies"].append("graph_expand")

        if query_type in ("relational", "risk", "comparative", "multi-hop", "clause"):
            for c in self.structured_search(query, query_type):
                if c.chunk_id not in seen:
                    seen[c.chunk_id] = c
            debug["strategies"].append("structured")

        for c in self.sequential_expand(seed_ids[:3]):
            if c.chunk_id not in seen:
                seen[c.chunk_id] = c
        debug["strategies"].append("sequential")

        all_chunks = self.keyword_rerank(list(seen.values()), query)
        debug["total"] = len(all_chunks)

        console.print(
            f"[cyan]Retrieval: {len(all_chunks)} chunks | "
            f"types={detected_types} | strategies={debug['strategies']}[/cyan]"
        )

        return all_chunks[:TOP_K * 2], debug
