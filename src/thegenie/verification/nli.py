from __future__ import annotations

import importlib
import math
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from .models import NLIScores


class NLIAdapter(Protocol):
    def score(self, premise: str, hypothesis: str) -> NLIScores: ...


class LazyCrossEncoderNLI:
    """Lazy local NLI adapter; importing this module does not import or load ML code."""

    def __init__(
        self,
        model_name_or_path: str,
        *,
        label_map: Mapping[str, int] | None = None,
        cache_folder: str | Path | None = None,
        device: str | None = None,
        local_files_only: bool = False,
        token: str | None = None,
        model_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.model_name_or_path = model_name_or_path
        self.label_map = {key.lower(): value for key, value in (label_map or {}).items()}
        self.cache_folder = str(cache_folder) if cache_folder else None
        self.device = device
        self.local_files_only = local_files_only
        self.token = token
        self.model_factory = model_factory
        self._model: Any | None = None

    def _load(self) -> Any:
        if self._model is None:
            if self.model_factory is None:
                module = importlib.import_module("sentence_transformers")
                cross_encoder = getattr(module, "CrossEncoder")
                self.model_factory = lambda name: cross_encoder(
                    name,
                    cache_folder=self.cache_folder,
                    device=self.device,
                    local_files_only=self.local_files_only,
                    token=self.token,
                )
            self._model = self.model_factory(self.model_name_or_path)
            if not self.label_map:
                config_map = getattr(getattr(self._model, "model", None), "config", None)
                id2label = getattr(config_map, "id2label", {})
                self.label_map = {
                    str(label).lower(): int(index)
                    for index, label in id2label.items()
                }
            required = {"entailment", "neutral", "contradiction"}
            if not required <= self.label_map.keys():
                raise ValueError("NLI label map must contain entailment, neutral, and contradiction")
        return self._model

    def score(self, premise: str, hypothesis: str) -> NLIScores:
        prediction = self._load().predict([(premise, hypothesis)], apply_softmax=True)
        values = _prediction_values(prediction)
        selected = [
            values[self.label_map[label]]
            for label in ("entailment", "neutral", "contradiction")
        ]
        normalized = _normalize_scores(selected)
        return NLIScores(
            entailment=normalized[0],
            neutral=normalized[1],
            contradiction=normalized[2],
        )


def _prediction_values(prediction: Any) -> list[float]:
    if hasattr(prediction, "tolist"):
        prediction = prediction.tolist()
    if isinstance(prediction, Mapping):
        return [float(prediction[index]) for index in sorted(prediction)]
    if not isinstance(prediction, Sequence) or isinstance(prediction, (str, bytes)):
        raise ValueError("NLI model returned an unsupported prediction")
    values: Any = prediction
    while (
        len(values) == 1
        and isinstance(values[0], Sequence)
        and not isinstance(values[0], (str, bytes))
    ):
        values = values[0]
        if hasattr(values, "tolist"):
            values = values.tolist()
    try:
        return [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise ValueError("NLI model returned non-numeric scores") from exc


def _normalize_scores(values: Sequence[float]) -> tuple[float, float, float]:
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise ValueError("NLI model must return three finite scores")
    total = sum(values)
    if any(value < 0 for value in values) or total <= 0 or abs(total - 1.0) > 1e-4:
        maximum = max(values)
        probabilities = [math.exp(value - maximum) for value in values]
        total = sum(probabilities)
        values = [value / total for value in probabilities]
    else:
        values = [value / total for value in values]
    return float(values[0]), float(values[1]), float(values[2])
