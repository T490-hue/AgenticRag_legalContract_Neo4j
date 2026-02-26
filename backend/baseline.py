

import numpy as np
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class BaselineResponse:
    answer:          str
    retrieved_texts: List[str]


class VectorStore:
    def __init__(self):
        self.texts = []
        self.embeddings = []
        self.metadata = []

    def add(self, text: str, embedding: List[float], meta: Dict = None):
        self.texts.append(text)
        self.embeddings.append(embedding)
        self.metadata.append(meta or {})

    def search(self, query_emb: List[float], top_k: int = 5) -> List[Dict]:
        if not self.embeddings:
            return []
        q   = np.array(query_emb)
        mat = np.array(self.embeddings)
        scores = mat @ q / (np.linalg.norm(mat, axis=1) * np.linalg.norm(q) + 1e-8)
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [{"text": self.texts[i], "score": float(scores[i])} for i in top_idx]

    def size(self) -> int:
        return len(self.texts)


class BaselineRAG:
    def __init__(self, embedder, llm):
        self.embedder = embedder
        self.llm      = llm
        self.store    = VectorStore()

    def query(self, question: str, top_k: int = 8) -> BaselineResponse:
        if self.store.size() == 0:
            return BaselineResponse(answer="No contracts loaded yet", retrieved_texts=[])
        emb     = self.embedder.embed(question)
        results = self.store.search(emb, top_k=top_k)
        # Filter low-score results to reduce noise
        texts   = [r["text"] for r in results if r["score"] > 0.2]
        if not texts:
            texts = [r["text"] for r in results[:3]]  # fallback: take top 3 regardless
        answer  = self.llm.generate_answer(question, texts)
        return BaselineResponse(answer=answer, retrieved_texts=texts)
