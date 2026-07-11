"""IdentitySnapshot — Captures system state at points in time.

Snapshots preserve all 9 layer capability scores, value axiom reinforcement
counts, and KG node metadata. They are stored in rack/L6/ and indexed
by timestamp.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


SNAPSHOT_DIR = "rack/L6"


@dataclass
class IdentitySnapshot:
    """A point-in-time capture of the system's self-model state."""

    snapshot_id: int
    timestamp: float
    version: str
    layer_scores: dict  # {layer_id: {score: float, metrics: dict}}
    value_axioms: dict  # {axiom_name: {reinforced_count: int, ...}}
    self_concept: dict  # Current self-concept fields
    total_attempts: int
    successful_applications: int
    kg_nodes_raw: int
    kg_nodes_consolidated: int
    narrative: str = ""

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "layer_scores": self.layer_scores,
            "value_axioms": self.value_axioms,
            "self_concept": self.self_concept,
            "total_attempts": self.total_attempts,
            "successful_applications": self.successful_applications,
            "kg_nodes_raw": self.kg_nodes_raw,
            "kg_nodes_consolidated": self.kg_nodes_consolidated,
            "narrative": self.narrative,
        }


class SnapshotManager:
    """Generates, stores, and retrieves identity snapshots."""

    def __init__(self, snapshot_dir: str = SNAPSHOT_DIR):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def take_snapshot(self, self_model, value_tracker) -> IdentitySnapshot:
        """Create a new identity snapshot from current system state."""
        snapshots = self.list_snapshots()
        next_id = (max(s["snapshot_id"] for s in snapshots) + 1) if snapshots else 1

        snapshot = IdentitySnapshot(
            snapshot_id=next_id,
            timestamp=time.time(),
            version=self_model.version,
            layer_scores={
                lid: {"score": ls.score, "metrics": ls.metrics}
                for lid, ls in self_model.layer_scores.items()
            },
            value_axioms={
                name: asdict(state)
                for name, state in value_tracker.axioms.items()
            },
            self_concept=asdict(self_model.self_concept),
            total_attempts=self_model.total_attempts,
            successful_applications=self_model.successful_applications,
            kg_nodes_raw=self_model.kg_nodes_raw,
            kg_nodes_consolidated=self_model.kg_nodes_consolidated,
            narrative=self_model.self_concept.current_narrative,
        )
        self._save(snapshot)
        return snapshot

    def _save(self, snapshot: IdentitySnapshot):
        """Persist a snapshot to disk."""
        path = self.snapshot_dir / f"snapshot-{snapshot.snapshot_id:04d}.json"
        with open(path, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

    def load_snapshot(self, snapshot_id: int) -> Optional[IdentitySnapshot]:
        """Load a specific snapshot by ID."""
        path = self.snapshot_dir / f"snapshot-{snapshot_id:04d}.json"
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)
        return IdentitySnapshot(**data)

    def list_snapshots(self) -> list[dict]:
        """Return metadata for all saved snapshots."""
        snapshots = []
        for path in sorted(self.snapshot_dir.glob("snapshot-*.json")):
            with open(path) as f:
                data = json.load(f)
            snapshots.append({
                "snapshot_id": data["snapshot_id"],
                "timestamp": data["timestamp"],
                "version": data["version"],
                "narrative": data.get("narrative", ""),
                "layer_scores": data.get("layer_scores", {}),
            })
        return snapshots
