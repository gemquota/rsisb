"""Signal Watcher — Polls the filesystem for changes and generates signals.

Uses os.stat()-based mtime polling at configurable intervals to detect
file creations, modifications, and deletions. Each detected change
generates a Signal that the Goal Generator can consume.
"""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Signal:
    """A detected signal from the environment."""
    signal_type: str  # file_created | file_modified | file_deleted | metric_change | stub_detected
    source: str       # Path or metric name
    timestamp: float
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.signal_type,
            "source": self.source,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class SignalWatcher:
    """Watches configured paths for filesystem changes.

    Polls mtime at a configurable interval. Maintains a snapshot of
    previous mtime data to detect changes between polls.
    """

    def __init__(self, watch_paths: Optional[list[str]] = None, poll_interval: float = 30.0):
        self.watch_paths = watch_paths or ["."]
        self.poll_interval = poll_interval
        self._previous_state: dict[str, float] = {}  # path -> mtime
        self._signals: list[Signal] = []
        self._last_poll: float = 0.0

    def poll(self) -> list[Signal]:
        """Poll watched paths for changes. Returns new signals since last poll."""
        now = time.time()
        if now - self._last_poll < self.poll_interval:
            return []

        self._last_poll = now
        new_signals = []

        for watch_path in self.watch_paths:
            p = Path(watch_path)
            if not p.exists():
                continue

            current_state: dict[str, float] = {}

            # Recursively walk, respecting .gitignore patterns
            for fpath in p.rglob("*"):
                if not fpath.is_file():
                    continue
                # Skip .git and __pycache__
                rel = str(fpath.relative_to(p))
                if rel.startswith(".git/") or rel.startswith("__pycache__/") or "/__pycache__/" in rel:
                    continue
                if any(part.startswith(".") and part != "." for part in fpath.parts):
                    if ".git" in fpath.parts:
                        continue

                stat = fpath.stat()
                current_state[str(fpath)] = stat.st_mtime

                # Check if this is new or modified
                prev_mtime = self._previous_state.get(str(fpath))
                if prev_mtime is None:
                    signal = Signal(
                        signal_type="file_created",
                        source=str(fpath),
                        timestamp=now,
                        metadata={"size": stat.st_size},
                    )
                    new_signals.append(signal)
                elif stat.st_mtime > prev_mtime:
                    signal = Signal(
                        signal_type="file_modified",
                        source=str(fpath),
                        timestamp=now,
                        metadata={"size": stat.st_size},
                    )
                    new_signals.append(signal)

            # Check for deleted files
            for prev_path in self._previous_state:
                if prev_path not in current_state:
                    signal = Signal(
                        signal_type="file_deleted",
                        source=prev_path,
                        timestamp=now,
                    )
                    new_signals.append(signal)

            self._previous_state = current_state

        self._signals.extend(new_signals)
        return new_signals

    def get_recent_signals(self, limit: int = 20) -> list[dict]:
        """Return recent signals as dicts."""
        return [s.to_dict() for s in self._signals[-limit:]]

    def get_signal_count(self) -> int:
        return len(self._signals)

    def clear_signals(self):
        self._signals.clear()
