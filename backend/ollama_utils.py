
import os
import json
import time
from typing import List, Dict
import ollama
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL",    "gemma3:27b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


ENTITY_TYPES = [
    # Actors
    "PARTY",           # company or individual signing the contract
    "JURISDICTION",    # governing law location

    # CUAD clause types (Hendrycks et al. 2021)
    "INDEMNIFICATION",
    "LIMITATION_OF_LIABILITY",
    "IP_OWNERSHIP_ASSIGNMENT",
    "NON_COMPETE",
    "EXCLUSIVITY",
    "CONFIDENTIALITY",
    "TERMINATION",
    "GOVERNING_LAW",
    "DISPUTE_RESOLUTION",
    "RENEWAL_TERM",
    "NOTICE_PERIOD_TO_TERMINATE_RENEWAL",
    "AUDIT_RIGHTS",
    "CHANGE_OF_CONTROL",
    "ANTI_ASSIGNMENT",
    "LICENSE_GRANT",
    "PRICE_OR_PAYMENT_TERMS",
    "MINIMUM_COMMITMENT",
    "UNCAPPED_LIABILITY",
    "CAP_ON_LIABILITY",
    "WARRANTY",
    "FORCE_MAJEURE",
    "NO_SOLICIT_OF_EMPLOYEES",
    "REVENUE_PROFIT_SHARING",

    # Derived nodes (novel — not in original CUAD)
    "OBLIGATION",      # specific duty imposed on a party
    "RISK_FLAG",       # identified legal risk
    "DATE",            # key contractual date
    "AMOUNT",          # monetary value or threshold
]

RELATION_TYPES = [
    "PARTY_TO",              # Party → Contract
    "GOVERNED_BY",           # Contract → Jurisdiction
    "CONTAINS",              # Contract → Clause
    "OBLIGATES",             # Clause/Contract → Obligation
    "GRANTS_RIGHT_TO",       # Clause → Party (license, permission)
    "ASSIGNS_IP_TO",         # Clause → Party (IP assignment)
    "INDEMNIFIES",           # Party → Party (indemnification direction)
    "CAPS_LIABILITY_AT",     # Clause → Amount
    "RESTRICTS",             # Clause → Party/Activity
    "TERMINATES_ON",         # Contract → Date
    "RENEWED_BY",            # Contract → Clause (renewal terms)
    "DISPUTES_RESOLVED_BY",  # Contract → Jurisdiction/Method
    "CONFLICTS_WITH",        # Clause → Clause (contradiction — novel)
    "HAS_RISK",              # Contract/Clause → Risk_Flag (novel)
    "RELATED_TO",            # Contract → Contract (shared party — novel)
]

# Few-shot example — anchors the output format for the LLM
# Based on Microsoft GraphRAG's use of in-context examples
FEW_SHOT_EXAMPLE = """
Example input:
  "Acme Corp agrees to indemnify Zenith Ltd for all third-party claims.
   However, Acme's total liability under this agreement shall not exceed $500,000.
   This agreement is governed by the laws of Delaware."

Example output:
{
  "contract_metadata": {
    "title": "Service Agreement",
    "contract_type": "Service Agreement",
    "effective_date": "",
    "jurisdiction": "Delaware"
  },
  "entities": [
    {"name": "Acme Corp",           "type": "PARTY",                    "description": "Indemnifying party and service provider"},
    {"name": "Zenith Ltd",          "type": "PARTY",                    "description": "Indemnified party and client"},
    {"name": "Indemnification",     "type": "INDEMNIFICATION",          "description": "Acme indemnifies Zenith for all third-party claims — broad, no carve-outs"},
    {"name": "Liability Cap",       "type": "CAP_ON_LIABILITY",         "description": "Acme's total liability capped at $500,000"},
    {"name": "$500,000",            "type": "AMOUNT",                   "description": "Maximum liability threshold"},
    {"name": "Delaware",            "type": "JURISDICTION",             "description": "Governing law state"}
  ],
  "relationships": [
    {"subject": "Acme Corp",        "predicate": "PARTY_TO",            "object": "Service Agreement",    "evidence": "Acme Corp agrees to indemnify",          "confidence": "high"},
    {"subject": "Zenith Ltd",       "predicate": "PARTY_TO",            "object": "Service Agreement",    "evidence": "indemnify Zenith Ltd",                   "confidence": "high"},
    {"subject": "Service Agreement","predicate": "CONTAINS",            "object": "Indemnification",      "evidence": "agrees to indemnify Zenith Ltd for all", "confidence": "high"},
    {"subject": "Service Agreement","predicate": "CONTAINS",            "object": "Liability Cap",        "evidence": "total liability shall not exceed",        "confidence": "high"},
    {"subject": "Acme Corp",        "predicate": "INDEMNIFIES",         "object": "Zenith Ltd",           "evidence": "Acme Corp agrees to indemnify Zenith Ltd","confidence": "high"},
    {"subject": "Liability Cap",    "predicate": "CAPS_LIABILITY_AT",   "object": "$500,000",             "evidence": "shall not exceed $500,000",               "confidence": "high"},
    {"subject": "Indemnification",  "predicate": "CONFLICTS_WITH",      "object": "Liability Cap",        "evidence": "broad indemnification contradicts $500k cap", "confidence": "high"},
    {"subject": "Service Agreement","predicate": "GOVERNED_BY",         "object": "Delaware",             "evidence": "governed by the laws of Delaware",        "confidence": "high"}
  ],
  "risk_flags": [
    {"type": "CONFLICTING_CLAUSES", "severity": "high",
     "description": "Indemnification clause is broad with no carve-outs, but liability is capped at $500k — creates legal ambiguity about enforceability of unlimited indemnity",
     "clause_ref": "Indemnification vs Liability Cap"}
  ]
}
"""


class OllamaLLM:
    def __init__(self):
        self.client = ollama.Client(host=OLLAMA_BASE_URL)
        self.model  = OLLAMA_MODEL
        try:
            self.client.list()
            console.print(f"[green]✓ Ollama connected | model: {self.model}[/green]")
        except Exception as e:
            console.print(f"[red]✗ Ollama failed: {e}[/red]")
            console.print("[yellow]Run: ollama serve[/yellow]")

    def generate(self, prompt: str, retries: int = 3) -> str:
        for attempt in range(retries):
            try:
                response = self.client.generate(
                    model=self.model,
                    prompt=prompt,
                    options={"temperature": 0.0, "num_predict": 4096},
                )
                return response["response"].strip()
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return f"Error: {e}"
        return "Error: max retries exceeded"

    def _parse_json(self, text: str, fallback: dict) -> dict:
        """Strip markdown fences, find outermost JSON object, parse safely."""
        try:
            clean = text.strip()
            # Strip ```json ... ``` fences
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0].strip()
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0].strip()
            # Find outermost { }
            start = clean.find("{")
            end   = clean.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(clean[start:end])
        except Exception:
            pass
        return fallback

    def extract_legal_entities(self, text: str) -> Dict:
        """
        Single-pass extraction: entities + relationships + risk flags.

        One LLM call produces the complete knowledge graph structure.
        Follows REBEL's end-to-end generation approach with Microsoft
        GraphRAG's prompt architecture and CUAD's legal taxonomy.
        """
        entity_types_str   = "\n".join([f"    - {t}" for t in ENTITY_TYPES])
        relation_types_str = "\n".join([f"    - {t}" for t in RELATION_TYPES])

        prompt = f"""You are an expert legal knowledge graph builder specializing in
commercial contract analysis. You are skilled at identifying parties, obligations,
rights, restrictions, and clause-level conflicts within legal agreements.

-Goal-
Given a legal contract, perform a single-pass extraction to build a complete
knowledge graph. Extract all entities, all relationships between them as
(subject, predicate, object) triples, and identify legal risk flags.
Every claim must be grounded in the actual contract text.

-Steps-

Step 1 — Extract entities.
  For each entity identify:
  - name:        exact name as it appears in the contract
  - type:        one value from the allowed entity types below
  - description: one sentence grounded in the contract text only

Step 2 — Extract relationships.
  For each pair of related entities create a triple:
  - subject:    entity name (from Step 1)
  - predicate:  one value from the allowed relationship types below
  - object:     entity name (from Step 1)
  - evidence:   SHORT exact quote from the contract (under 20 words)
  - confidence: high / medium / low

  CRITICAL RULE: If you find two clauses that contradict each other
  (e.g. a broad indemnification obligation alongside a liability cap,
  or an IP assignment that conflicts with a license-back provision),
  you MUST create a CONFLICTS_WITH relationship between them.
  This is the most important relationship type — do not miss it.

Step 3 — Identify risk flags.
  For each significant legal risk:
  - type:        CONFLICTING_CLAUSES / UNCAPPED_INDEMNITY / BROAD_IP_ASSIGNMENT /
                 AUTO_RENEWAL / MISSING_LIABILITY_CAP / RESTRICTIVE_NON_COMPETE /
                 ONE_SIDED_TERMINATION / MISSING_STANDARD_CLAUSE / OTHER
  - severity:    high / medium / low
  - description: one sentence explaining why this is a risk
  - clause_ref:  which clause(s) are involved

-Allowed entity types (CUAD taxonomy + extensions)-
{entity_types_str}

-Allowed relationship predicates-
{relation_types_str}

-Output format rules-
  - Return ONLY valid JSON. No prose before or after.
  - Do NOT invent information not found in the contract text.
  - Entity names must match exactly between entities and relationships lists.
  - Evidence quotes must be verbatim from the contract (under 20 words).

-Few-shot example-
{FEW_SHOT_EXAMPLE}

-Real task-
Now extract from this contract:

{text[:5000]}

Return ONLY the JSON:"""

        console.print("[bold cyan]Extracting legal knowledge graph (single pass)...[/bold cyan]")
        raw    = self.generate(prompt)
        parsed = self._parse_json(raw, {
            "contract_metadata": {}, "entities": [],
            "relationships": [], "risk_flags": []
        })

        # ── Build unified output compatible with ingestion.py ─
        meta      = parsed.get("contract_metadata", {})
        entities  = parsed.get("entities",          [])
        relations = parsed.get("relationships",     [])
        risks     = parsed.get("risk_flags",        [])

        parties = [
            {"name": e["name"], "type": "company", "role": e.get("description", "")}
            for e in entities if e.get("type") == "PARTY"
        ]

        clauses = [
            {
                "type":       e.get("type", "other").lower(),
                "summary":    e.get("description", ""),
                "risk_level": self._clause_risk(e["name"], risks),
                "name":       e.get("name", ""),
            }
            for e in entities
            if e.get("type") not in ("PARTY", "JURISDICTION", "DATE",
                                      "AMOUNT", "OBLIGATION", "RISK_FLAG")
        ]

        obligations = [
            {
                "party":       r["subject"],
                "description": f"{r['predicate']} → {r['object']}",
                "deadline":    "",
                "evidence":    r.get("evidence", ""),
            }
            for r in relations
            if r.get("predicate") in ("OBLIGATES", "INDEMNIFIES",
                                       "ASSIGNS_IP_TO", "RESTRICTS")
        ]

        risk_flags = [
            {
                "type":        f.get("type",        "other"),
                "severity":    f.get("severity",    "medium"),
                "description": f.get("description", ""),
                "clause_ref":  f.get("clause_ref",  ""),
            }
            for f in risks
        ]

        for r in relations:
            if r.get("predicate") == "CONFLICTS_WITH":
                already = any(
                    f.get("clause_ref","") == f"{r['subject']} vs {r['object']}"
                    for f in risk_flags
                )
                if not already:
                    risk_flags.append({
                        "type":        "CONFLICTING_CLAUSES",
                        "severity":    "high",
                        "description": (
                            f"{r['subject']} conflicts with {r['object']}. "
                            f"Evidence: {r.get('evidence','')}"
                        ),
                        "clause_ref":  f"{r['subject']} vs {r['object']}",
                    })

        result = {
            "title":          meta.get("title",          ""),
            "contract_type":  meta.get("contract_type",  "Commercial Agreement"),
            "effective_date": meta.get("effective_date", ""),
            "expiry_date":    "",
            "jurisdiction":   meta.get("jurisdiction",   ""),
            "parties":        parties,
            "clauses":        clauses,
            "obligations":    obligations,
            "risk_flags":     risk_flags,
            "relationships":  [
                {
                    "subject":    r["subject"],
                    "relation":   r["predicate"],
                    "object":     r["object"],
                    "evidence":   r.get("evidence",   ""),
                    "confidence": r.get("confidence", "medium"),
                }
                for r in relations
            ],
            # Raw outputs for debugging
            "_raw_entities":      entities,
            "_raw_relationships": relations,
        }

        console.print(
            f"[green]✓ Extraction complete: "
            f"{len(parties)} parties, "
            f"{len(clauses)} clauses, "
            f"{len(risk_flags)} risk flags, "
            f"{len(relations)} relationships[/green]"
        )
        return result

    def _clause_risk(self, clause_name: str, risk_flags: list) -> str:
        """Derive risk level for a clause from the risk_flags list."""
        name_lower = clause_name.lower()
        for flag in risk_flags:
            ref = flag.get("clause_ref", "").lower()
            if name_lower in ref or ref in name_lower:
                return flag.get("severity", "medium")
        return "low"


    def generate_answer(self, query: str, chunks: List[str]) -> str:
        """
        Generate a faithful, grounded answer from retrieved contract chunks.

        Hallucination is prevented at the prompt level (techniques 1-4 above),
        at the generation level (temperature=0, technique 5), and upstream
        via confidence gating in main.py (technique 6).
        """
        passages = "\n\n".join([
            f"[P{i+1}] {c[:600]}"
            for i, c in enumerate(chunks[:5])
        ])

        prompt = f"""You are a legal contract analysis assistant.

-Context passages (retrieved from contracts)-
{passages}

-Question-
{query}

-Instructions-
Answer the question using ONLY the context passages above.
Do NOT use any knowledge from your training data.
Do NOT add legal advice or interpretation beyond what the passages state.
When you state a fact, reference which passage it comes from using [P1], [P2] etc.
If the passages do not contain enough information to answer, respond with exactly:
"The provided contracts do not contain sufficient information to answer this question."

-Answer-"""

        return self.generate(prompt)

    def classify_query(self, query: str) -> str:
        prompt = f"""Classify this legal contract question into exactly one category:

- factual     : asks for a specific fact (date, party name, payment amount)
- clause      : asks about a specific clause type or its contents
- relational  : asks about relationships between parties or contracts
- comparative : compares terms across multiple contracts
- risk        : asks about legal risks, conflicts, or missing protections
- multi-hop   : requires connecting information across multiple contracts or clauses

Question: {query}

Reply with one word only (the category name):"""

        result = self.generate(prompt).lower().strip()
        for cat in ["factual", "clause", "relational",
                    "comparative", "risk", "multi-hop"]:
            if cat in result:
                return cat
        return "clause"
