"""Embedding provider for episodic memory. Default: fastembed (ONNX, self-hosted).

Swap the default here (or via MEMORY_EMBED_MODEL) to move to a hosted API later —
callers depend only on the Embedder protocol.
"""

import logging
import os
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.getenv("MEMORY_EMBED_MODEL", "BAAI/bge-small-en-v1.5")


@runtime_checkable
class Embedder(Protocol):
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


class FastEmbedEmbedder:
    """Self-hosted ONNX embeddings via fastembed. bge-small-en-v1.5 → 384 dims."""

    def __init__(self, model_name: str = _DEFAULT_MODEL, dimensions: int = 384):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)
        self.dimensions = dimensions
        logger.info(
            "[MEMORY] FastEmbed model loaded: %s (%d dims)", model_name, dimensions
        )

    def embed(self, text: str) -> list[float]:
        vec = next(iter(self._model.embed([text or ""])))
        return [float(x) for x in vec]


_default: Optional[Embedder] = None


def get_default_embedder() -> Embedder:
    global _default
    if _default is None:
        _default = FastEmbedEmbedder()
    return _default
