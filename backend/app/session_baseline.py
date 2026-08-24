from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
import json
import os
from tempfile import NamedTemporaryFile


@dataclass(frozen=True)
class SessionBaseline:
    session_date: str
    starting_equity: float


class SessionBaselineStore:
    """Durable session-start equity baseline; never resets an existing session."""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> SessionBaseline | None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            baseline = SessionBaseline(str(data["session_date"]), float(data["starting_equity"]))
            if baseline.starting_equity <= 0:
                raise ValueError("starting_equity must be positive")
            return baseline
        except FileNotFoundError:
            return None

    def get_or_initialize(self, session_date: date, current_equity: float) -> SessionBaseline:
        if current_equity <= 0:
            raise ValueError("current_equity must be positive")
        existing = self.load()
        requested = session_date.isoformat()
        if existing is not None and existing.session_date == requested:
            return existing
        baseline = SessionBaseline(requested, float(current_equity))
        self._write(baseline)
        return baseline

    def _write(self, baseline: SessionBaseline) -> None:
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        fd, temp_path = None, None
        try:
            fd, temp_path = NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False)
            with fd:
                json.dump(asdict(baseline), fd, separators=(",", ":"), sort_keys=True)
                fd.flush()
                os.fsync(fd.fileno())
            os.replace(temp_path, self.path)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
