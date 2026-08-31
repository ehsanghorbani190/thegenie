from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_prefix="RAG_",
        extra="ignore",
    )

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "academic_chunks"

    documents_path: Path = Path("documents")
    data_path: Path = Path("data")
    cache_path: Path = Path("data/cache")
    metadata_path: Path = Path("data/metadata")
    verification_path: Path = Path("data/verification")

    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    nli_model: str = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
    device: str = "cpu"
    offline: bool = False
    hf_token: str | None = None

    chunk_size: int = Field(default=512, gt=0)
    chunk_overlap: int = Field(default=64, ge=0)
    embedding_batch_size: int = Field(default=16, gt=0)
    vector_candidates: int = Field(default=20, gt=0)
    result_count: int = Field(default=5, gt=0)
    deduplication_threshold: float = Field(default=0.9, ge=0, le=1)
    source_diversity: bool = True
    entailment_threshold: float = Field(default=0.7, ge=0, le=1)
    contradiction_threshold: float = Field(default=0.7, ge=0, le=1)
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"

    @model_validator(mode="after")
    def validate_limits(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        if self.result_count > self.vector_candidates:
            raise ValueError("result_count cannot exceed vector_candidates")
        return self
