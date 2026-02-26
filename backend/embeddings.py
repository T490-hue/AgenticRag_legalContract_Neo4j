

import numpy as np
from typing import List
from sentence_transformers import SentenceTransformer
from rich.console import Console

console   = Console()
MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
EMBED_DIM  = 768


class EmbeddingModel:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            console.print(f"[cyan]Loading embeddings: {MODEL_NAME}...[/cyan]")
            cls._instance.model = SentenceTransformer(MODEL_NAME)
            console.print(f"[green]✓ Embeddings ready | dim={EMBED_DIM}[/green]")
        return cls._instance

    def embed(self, text: str) -> List[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        return self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 10,
        ).tolist()
