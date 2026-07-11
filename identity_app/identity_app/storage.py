"""Storage — Persistence layer for identity data.

Provides JSON-based file storage with auto-migration, atomic writes,
and a clean abstraction over the data directory.
"""

import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone


DEFAULT_DATA_DIR = "data"


@dataclass
class StorageConfig:
    """Configuration for the storage layer."""
    data_dir: str = DEFAULT_DATA_DIR
    auto_migrate: bool = True
    pretty_print: bool = True
    max_backups: int = 5


class Storage:
    """JSON-based persistence layer with migrations and atomic writes.

    Manages the identity app's data directory and all file I/O.
    Supports atomic writes via temp file + rename, automatic directory
    creation, and schema migration on read.
    """

    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create all required directories."""
        base = Path(self.config.data_dir)
        base.mkdir(parents=True, exist_ok=True)
        (base / "snapshots").mkdir(parents=True, exist_ok=True)
        (base / "backups").mkdir(parents=True, exist_ok=True)

    # ── Path helpers ────────────────────────────────────────────

    def _path(self, *parts: str) -> Path:
        return Path(self.config.data_dir, *parts)

    def snapshot_path(self, snapshot_id: int) -> Path:
        return self._path("snapshots", f"snapshot-{snapshot_id:04d}.json")

    # ── Atomic read/write ───────────────────────────────────────

    def read_json(self, path: Path) -> Optional[dict]:
        """Read and parse a JSON file, with optional auto-migration."""
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        if self.config.auto_migrate:
            data = self._migrate(data, path.name)
        return data

    def write_json(self, path: Path, data: dict, backup: bool = False) -> None:
        """Atomically write JSON to a file using temp + rename."""
        self._ensure_dirs()
        if backup and path.exists():
            self._backup(path)
        fd, tmp = tempfile.mkstemp(dir=self._path("snapshots"), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2 if self.config.pretty_print else None)
            shutil.move(tmp, str(path))
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _backup(self, path: Path) -> None:
        """Create a timestamped backup of a file."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup = self._path("backups", f"{path.stem}_{ts}{path.suffix}")
        shutil.copy2(str(path), str(backup))
        # Prune old backups
        backups = sorted(self._path("backups").glob(f"{path.stem}_*{path.suffix}"))
        for old in backups[:-self.config.max_backups]:
            old.unlink(missing_ok=True)

    # ── Schema migration ────────────────────────────────────────

    def _migrate(self, data: dict, filename: str) -> dict:
        """Apply schema migrations to data loaded from disk."""
        # self_model.json: ensure all expected fields exist
        if filename == "self_model.json":
            data.setdefault("version", "1.0.0")
            data.setdefault("traits", {})
            data.setdefault("beliefs", {})
            data.setdefault("narrative_history", [])
            data.setdefault("temporal_history", [])
            data.setdefault("layer_scores", {})
            data.setdefault("value_axioms", {})
            data.setdefault("self_concept", {})
            data.setdefault("snapshot_count", 0)
            data.setdefault("total_attempts", 0)
            data.setdefault("successful_applications", 0)
            data.setdefault("kg_nodes_raw", 0)
            data.setdefault("kg_nodes_consolidated", 0)
            data.setdefault("crisis_count", 0)
            data.setdefault("last_crisis_at", 0.0)
            data.setdefault("created_at", time.time())
            data.setdefault("updated_at", time.time())
        return data

    # ── High-level operations ───────────────────────────────────

    def load_self_model(self) -> dict:
        """Load the self-model JSON, returning default if absent."""
        path = self._path("self_model.json")
        data = self.read_json(path)
        if data is None:
            return {
                "version": "1.0.0",
                "layer_scores": {},
                "value_axioms": {},
                "self_concept": {},
                "traits": {},
                "beliefs": {},
                "narrative_history": [],
                "temporal_history": [],
                "snapshot_count": 0,
                "total_attempts": 0,
                "successful_applications": 0,
                "kg_nodes_raw": 0,
                "kg_nodes_consolidated": 0,
                "crisis_count": 0,
                "last_crisis_at": 0.0,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
        return data

    def save_self_model(self, data: dict) -> None:
        """Save the self-model JSON atomically."""
        data["updated_at"] = time.time()
        self.write_json(self._path("self_model.json"), data, backup=True)

    def load_crisis_state(self) -> dict:
        """Load the crisis state file."""
        path = self._path("crisis_state.json")
        data = self.read_json(path)
        if data is None:
            return {"active": False, "severity": "none", "triggered_at": 0.0,
                    "triggered_by": "", "resolved_at": 0.0, "history": [],
                    "prediction": {}}
        return data

    def save_crisis_state(self, data: dict) -> None:
        """Save the crisis state atomically."""
        self.write_json(self._path("crisis_state.json"), data)

    def load_timeline_cache(self) -> dict:
        """Load cached timeline analysis data."""
        path = self._path("timeline_cache.json")
        data = self.read_json(path)
        return data if data else {}

    def save_timeline_cache(self, data: dict) -> None:
        """Save timeline cache."""
        self.write_json(self._path("timeline_cache.json"), data)

    def list_snapshots(self) -> list[dict]:
        """Return metadata for all stored snapshots."""
        snapshots = []
        pattern = self._path("snapshots", "snapshot-*.json")
        for path in sorted(Path(self.config.data_dir, "snapshots").glob("snapshot-*.json")):
            data = self.read_json(path)
            if data:
                snapshots.append({
                    "snapshot_id": data.get("snapshot_id"),
                    "timestamp": data.get("timestamp"),
                    "version": data.get("version", ""),
                    "narrative": data.get("narrative", ""),
                    "layer_scores_summary": {
                        lid: ls.get("score", 0)
                        for lid, ls in data.get("layer_scores", {}).items()
                    },
                    "tag": data.get("tag", ""),
                })
        return snapshots

    def save_snapshot(self, snapshot: dict) -> None:
        """Save a snapshot file."""
        sid = snapshot.get("snapshot_id", 0)
        self.write_json(self.snapshot_path(sid), snapshot)

    def load_snapshot(self, snapshot_id: int) -> Optional[dict]:
        """Load a specific snapshot by ID."""
        return self.read_json(self.snapshot_path(snapshot_id))

    def delete_snapshot(self, snapshot_id: int) -> bool:
        """Delete a snapshot file. Returns True if deleted."""
        path = self.snapshot_path(snapshot_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def prune_snapshots(self, keep: int = 50) -> int:
        """Delete oldest snapshots beyond the keep limit. Returns count removed."""
        snapshots = sorted(
            Path(self.config.data_dir, "snapshots").glob("snapshot-*.json")
        )
        removed = 0
        for old in snapshots[:-keep]:
            old.unlink()
            removed += 1
        return removed
