from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class ModelVersion:
    name: str
    version: str
    metrics: dict
    status: str = "CANDIDATE"
    created_at: str = ""


class ModelRegistry:
    def __init__(self):
        self.models: list[ModelVersion] = []

    def register(self, name: str, version: str, metrics: dict) -> ModelVersion:
        model = ModelVersion(name, version, metrics, "CANDIDATE", datetime.now(timezone.utc).isoformat())
        self.models.append(model)
        return model

    def promote(self, name: str, version: str) -> ModelVersion:
        target = None
        for model in self.models:
            if model.name == name:
                model.status = "PRODUCTION" if model.version == version else "ARCHIVED"
                if model.version == version:
                    target = model
        if target is None:
            raise ValueError("model version not found")
        return target

    def list(self):
        return [asdict(m) for m in self.models]


registry = ModelRegistry()
