"""
graph_db.py - Neo4j connection and legal knowledge graph schema

Legal Graph Schema:
  Nodes:
    Contract     - the agreement document
    Party        - companies/individuals in contracts
    Clause       - individual contract clauses
    Obligation   - duties imposed by clauses
    Jurisdiction - governing law location
    RiskFlag     - auto-detected risky clauses
    Chunk        - text chunks for vector search

  Relationships:
    (Contract)-[:HAS_PARTY {role}]->(Party)
    (Contract)-[:CONTAINS]->(Clause)
    (Contract)-[:GOVERNED_BY]->(Jurisdiction)
    (Contract)-[:RELATED_TO]->(Contract)      -- same parties
    (Clause)-[:IMPOSES]->(Obligation)
    (Clause)-[:CONFLICTS_WITH]->(Clause)      -- novel: contradicting clauses
    (Clause)-[:SIMILAR_TO {score}]->(Clause)  -- semantic similarity
    (Party)-[:PARTY_TO]->(Contract)
    (RiskFlag)-[:FLAGS]->(Clause)             -- novel: risk annotation
    (Chunk)-[:BELONGS_TO]->(Contract)
    (Chunk)-[:NEXT]->(Chunk)
    (Chunk)-[:SIMILAR_TO {score}]->(Chunk)
"""

import os
from typing import List, Dict
from neo4j import GraphDatabase
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "legalrag")


class Neo4jConnection:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            max_connection_lifetime=3600,
        )
        try:
            self.driver.verify_connectivity()
            console.print(f"[green]✓ Connected to Neo4j at {NEO4J_URI}[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠ Neo4j: {e}[/yellow]")

    def run(self, query: str, parameters: Dict = None) -> List[Dict]:
        with self.driver.session() as session:
            return session.run(query, parameters or {}).data()

    def close(self):
        self.driver.close()


def setup_schema(conn: Neo4jConnection):
    console.print("[cyan]Setting up legal graph schema...[/cyan]")

    constraints = [
        "CREATE CONSTRAINT contract_id   IF NOT EXISTS FOR (c:Contract)     REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT party_name    IF NOT EXISTS FOR (p:Party)        REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT clause_id     IF NOT EXISTS FOR (c:Clause)       REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id      IF NOT EXISTS FOR (c:Chunk)        REQUIRE c.id IS UNIQUE",
        "CREATE CONSTRAINT jurisdiction_name IF NOT EXISTS FOR (j:Jurisdiction) REQUIRE j.name IS UNIQUE",
    ]
    for c in constraints:
        try:
            conn.run(c)
        except Exception:
            pass

    # Vector indexes
    for name, label, prop in [
        ("chunk_vector",  "Chunk",    "embedding"),
        ("clause_vector", "Clause",   "embedding"),
    ]:
        try:
            conn.run(f"""
                CALL db.index.vector.createNodeIndex(
                    '{name}', '{label}', '{prop}', 768, 'cosine'
                )
            """)
            console.print(f"[green]✓ Vector index: {name}[/green]")
        except Exception:
            pass

    console.print("[green]✓ Legal graph schema ready[/green]")


def get_stats(conn: Neo4jConnection) -> Dict:
    nodes = conn.run("""
        MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count
        ORDER BY count DESC
    """)
    rels = conn.run("""
        MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count
        ORDER BY count DESC
    """)
    return {
        "nodes":         {r["label"]: r["count"] for r in nodes if r["label"]},
        "relationships": {r["type"]:  r["count"] for r in rels  if r["type"]},
    }
