from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import Any, Sequence


class LocalSentenceTransformerEmbedder:
    """Lazy, reusable local SentenceTransformer embedding adapter."""

    def __init__(
        self,
        model_name: str,
        *,
        cache_dir: str | Path | None = None,
        device: str | None = None,
        batch_size: int = 16,
        offline: bool = False,
        token: str | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.model_name = model_name
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.device = device
        self.batch_size = batch_size
        self.offline = offline
        self.token = token
        self._model: Any | None = None
        self._lock = Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def model(self) -> Any:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(
                        self.model_name,
                        cache_folder=str(self.cache_dir) if self.cache_dir else None,
                        device=_resolve_device(self.device),
                        local_files_only=self.offline,
                        token=self.token,
                    )
        return self._model

    @property
    def dimension(self) -> int:
        dimension = self.model.get_embedding_dimension()
        if dimension is None:
            raise RuntimeError("embedding model did not report a vector dimension")
        return int(dimension)

    @property
    def tokenizer(self) -> Any:
        return self.model.tokenizer

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        if not query.strip():
            raise ValueError("query must not be empty")
        return self.embed_documents([query])[0]

    def is_available_locally(self) -> bool:
        if self.loaded:
            return True
        return _model_is_cached(self.model_name, self.cache_dir)


class LocalCrossEncoder:
    """Lazy generic CrossEncoder adapter suitable for reranking or NLI."""

    def __init__(
        self,
        model_name: str,
        *,
        cache_dir: str | Path | None = None,
        device: str | None = None,
        batch_size: int = 16,
        offline: bool = False,
        token: str | None = None,
        activation_fn: Any | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.model_name = model_name
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.device = device
        self.batch_size = batch_size
        self.offline = offline
        self.token = token
        self.activation_fn = activation_fn
        self._model: Any | None = None
        self._lock = Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def model(self) -> Any:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import CrossEncoder

                    kwargs: dict[str, Any] = {}
                    if self.activation_fn is not None:
                        kwargs["activation_fn"] = self.activation_fn
                    self._model = CrossEncoder(
                        self.model_name,
                        cache_folder=str(self.cache_dir) if self.cache_dir else None,
                        device=_resolve_device(self.device),
                        local_files_only=self.offline,
                        token=self.token,
                        **kwargs,
                    )
        return self._model

    def predict(self, pairs: Sequence[tuple[str, str]]) -> Any:
        if not pairs:
            return []
        return self.model.predict(
            list(pairs),
            batch_size=self.batch_size,
            show_progress_bar=False,
        )

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        if not query.strip():
            raise ValueError("query must not be empty")
        predictions = self.predict([(query, passage) for passage in passages])
        if hasattr(predictions, "tolist"):
            predictions = predictions.tolist()
        return [float(value) for value in predictions]

    def is_available_locally(self) -> bool:
        if self.loaded:
            return True
        return _model_is_cached(self.model_name, self.cache_dir)


def _resolve_device(device: str | None) -> str:
    if device and device.lower() != "auto":
        return device
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def _model_is_cached(model_name: str, cache_dir: Path | None) -> bool:
    """Check Hugging Face's cache without network access or model loading."""
    try:
        from huggingface_hub import try_to_load_from_cache
        from huggingface_hub.constants import HF_HUB_CACHE

        cache = str(cache_dir) if cache_dir else os.getenv("HF_HUB_CACHE", HF_HUB_CACHE)
        for filename in ("config.json", "modules.json"):
            cached = try_to_load_from_cache(
                model_name,
                filename,
                cache_dir=cache,
                revision="main",
            )
            if isinstance(cached, str):
                return True
        return False
    except (ImportError, OSError, ValueError):
        return False
