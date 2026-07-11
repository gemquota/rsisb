"""Snapshot System — Identity snapshots, structured diffs, timeline analysis, automated scheduler.

Extends the original RSIS IdentitySnapshot with:
- Structured diffing between snapshots with direction indicators
- Timeline analysis with trend/milestone detection
- Automated snapshot scheduling with configurable policies
- Snapshot tagging, annotation, and search
"""

import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from identity_app.storage import Storage


# ── IdentitySnapshot ────────────────────────────────────────────

@dataclass
class IdentitySnapshot:
    """A point-in-time capture of the system's full identity state."""

    snapshot_id: int
    timestamp: float
    version: str
    layer_scores: dict
    value_axioms: dict
    self_concept: dict
    traits: dict
    beliefs: dict
    narrative: str
    tag: str = ""
    notes: str = ""
    total_attempts: int = 0
    successful_applications: int = 0
    kg_nodes_raw: int = 0
    kg_nodes_consolidated: int = 0
    crisis_active: bool = False
    origin: str = "manual"  # manual, scheduled, auto, pre_crisis, post_crisis

    def to_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "layer_scores": self.layer_scores,
            "value_axioms": self.value_axioms,
            "self_concept": self.self_concept,
            "traits": self.traits,
            "beliefs": self.beliefs,
            "narrative": self.narrative,
            "tag": self.tag,
            "notes": self.notes,
            "total_attempts": self.total_attempts,
            "successful_applications": self.successful_applications,
            "kg_nodes_raw": self.kg_nodes_raw,
            "kg_nodes_consolidated": self.kg_nodes_consolidated,
            "crisis_active": self.crisis_active,
            "origin": self.origin,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IdentitySnapshot":
        return cls(
            snapshot_id=data.get("snapshot_id", 0),
            timestamp=data.get("timestamp", 0.0),
            version=data.get("version", ""),
            layer_scores=data.get("layer_scores", {}),
            value_axioms=data.get("value_axioms", {}),
            self_concept=data.get("self_concept", {}),
            traits=data.get("traits", {}),
            beliefs=data.get("beliefs", {}),
            narrative=data.get("narrative", ""),
            tag=data.get("tag", ""),
            notes=data.get("notes", ""),
            total_attempts=data.get("total_attempts", 0),
            successful_applications=data.get("successful_applications", 0),
            kg_nodes_raw=data.get("kg_nodes_raw", 0),
            kg_nodes_consolidated=data.get("kg_nodes_consolidated", 0),
            crisis_active=data.get("crisis_active", False),
            origin=data.get("origin", "manual"),
        )


# ── SnapshotManager ─────────────────────────────────────────────

class SnapshotManager:
    """Generates, stores, retrieves, and manages identity snapshots."""

    def __init__(self, storage: Optional[Storage] = None):
        self.storage = storage or Storage()

    def take_snapshot(self, self_model, axiom_system=None,
                      tag: str = "", notes: str = "",
                      origin: str = "manual") -> IdentitySnapshot:
        """Create a new identity snapshot from current system state."""
        snapshots = self.storage.list_snapshots()
        next_id = (max(s["snapshot_id"] for s in snapshots) + 1) if snapshots else 1

        # Get traits
        traits = {}
        if hasattr(self_model, 'traits'):
            traits = {n: t.to_dict() for n, t in self_model.traits.items()}

        # Get beliefs
        beliefs = {}
        if hasattr(self_model, 'beliefs'):
            beliefs = {k: b.to_dict() for k, b in self_model.beliefs.items()}

        # Get crisis state
        crisis_data = self.storage.load_crisis_state()

        snapshot = IdentitySnapshot(
            snapshot_id=next_id,
            timestamp=time.time(),
            version=self_model.version,
            layer_scores={
                lid: {"score": ls.get("score", 0), "metrics": ls.get("metrics", {})}
                for lid, ls in self_model.layer_scores.items()
            },
            value_axioms={
                name: state.to_dict()
                for name, state in (axiom_system.axioms.items() if axiom_system else {})
            } if axiom_system else self_model.value_axioms,
            self_concept=dict(self_model.self_concept),
            traits=traits,
            beliefs=beliefs,
            narrative=self_model.get_narrative(),
            tag=tag,
            notes=notes,
            total_attempts=self_model.total_attempts,
            successful_applications=self_model.successful_applications,
            kg_nodes_raw=self_model.kg_nodes_raw,
            kg_nodes_consolidated=self_model.kg_nodes_consolidated,
            crisis_active=crisis_data.get("active", False),
            origin=origin,
        )
        self.storage.save_snapshot(snapshot.to_dict())
        self_model.snapshot_count = max(self_model.snapshot_count, next_id)
        self_model.save()
        return snapshot

    def load_snapshot(self, snapshot_id: int) -> Optional[IdentitySnapshot]:
        """Load a specific snapshot by ID."""
        data = self.storage.load_snapshot(snapshot_id)
        return IdentitySnapshot.from_dict(data) if data else None

    def list_snapshots(self, limit: int = 50) -> list[dict]:
        """List all snapshots with metadata."""
        return self.storage.list_snapshots()[-limit:]

    def delete_snapshot(self, snapshot_id: int) -> bool:
        """Delete a snapshot by ID."""
        return self.storage.delete_snapshot(snapshot_id)

    def prune(self, keep: int = 50) -> int:
        """Delete oldest snapshots beyond the keep limit."""
        return self.storage.prune_snapshots(keep)

    def search_snapshots(self, query: str) -> list[dict]:
        """Search snapshots by tag, notes, or narrative."""
        snapshots = self.storage.list_snapshots()
        results = []
        query = query.lower()
        for s in snapshots:
            data = self.storage.load_snapshot(s["snapshot_id"])
            if not data:
                continue
            if (query in data.get("tag", "").lower()
                or query in data.get("notes", "").lower()
                or query in data.get("narrative", "").lower()):
                results.append(data)
        return results


# ── SnapshotDiff ────────────────────────────────────────────────

class SnapshotDiff:
    """Computes structured diffs between two identity snapshots."""

    @staticmethod
    def compare(snapshot_a: IdentitySnapshot, snapshot_b: IdentitySnapshot) -> dict:
        """Compare two snapshots and produce a structured diff."""
        diff = {
            "snapshot_a": snapshot_a.snapshot_id,
            "snapshot_b": snapshot_b.snapshot_id,
            "time_span": snapshot_b.timestamp - snapshot_a.timestamp,
            "version_change": f"{snapshot_a.version} → {snapshot_b.version}",
            "layer_scores": SnapshotDiff._diff_layer_scores(
                snapshot_a.layer_scores, snapshot_b.layer_scores
            ),
            "value_axioms": SnapshotDiff._diff_value_axioms(
                snapshot_a.value_axioms, snapshot_b.value_axioms
            ),
            "self_concept": SnapshotDiff._diff_self_concept(
                snapshot_a.self_concept, snapshot_b.self_concept
            ),
            "traits": SnapshotDiff._diff_traits(
                snapshot_a.traits, snapshot_b.traits
            ),
            "stats": {
                "total_attempts_change": snapshot_b.total_attempts - snapshot_a.total_attempts,
                "successful_applications_change": snapshot_b.successful_applications - snapshot_a.successful_applications,
                "kg_nodes_raw_change": snapshot_b.kg_nodes_raw - snapshot_a.kg_nodes_raw,
                "crisis_state_change": f"{snapshot_a.crisis_active} → {snapshot_b.crisis_active}",
            },
            "narrative_change": (
                f"'{snapshot_a.narrative[:60]}...' → '{snapshot_b.narrative[:60]}...'"
                if snapshot_a.narrative != snapshot_b.narrative
                else "unchanged"
            ),
            "summary": "",
        }

        # Generate summary
        changed_layers = [lid for lid, d in diff["layer_scores"].items() if d["changed"]]
        if changed_layers:
            diff["summary"] += f"Layers changed: {', '.join(changed_layers)}. "
        improved = [lid for lid, d in diff["layer_scores"].items()
                    if d.get("direction") == "improved"]
        declined = [lid for lid, d in diff["layer_scores"].items()
                    if d.get("direction") == "declined"]
        if improved:
            diff["summary"] += f"Improved: {', '.join(improved)}. "
        if declined:
            diff["summary"] += f"Declined: {', '.join(declined)}. "

        return diff

    @staticmethod
    def _diff_layer_scores(scores_a: dict, scores_b: dict) -> dict:
        """Compare layer scores between two snapshots."""
        all_layers = set(scores_a.keys()) | set(scores_b.keys())
        result = {}
        for lid in sorted(all_layers):
            a_score = scores_a.get(lid, {}).get("score", 0) if isinstance(scores_a.get(lid), dict) else 0
            b_score = scores_b.get(lid, {}).get("score", 0) if isinstance(scores_b.get(lid), dict) else 0
            change = round(b_score - a_score, 1)
            result[lid] = {
                "from": a_score,
                "to": b_score,
                "change": change,
                "changed": abs(change) > 0.01,
                "direction": "improved" if change > 0 else ("declined" if change < 0 else "stable"),
                "pct_change": round((change / a_score * 100) if a_score > 0 else 0, 1),
            }
        return result

    @staticmethod
    def _diff_value_axioms(ax_a: dict, ax_b: dict) -> dict:
        """Compare value axiom states between two snapshots."""
        all_axioms = set(ax_a.keys()) | set(ax_b.keys())
        result = {}
        for axiom in sorted(all_axioms):
            a_count = ax_a.get(axiom, {}).get("reinforced_count", 0) if isinstance(ax_a.get(axiom), dict) else 0
            b_count = ax_b.get(axiom, {}).get("reinforced_count", 0) if isinstance(ax_b.get(axiom), dict) else 0
            result[axiom] = {
                "reinforcements_from": a_count,
                "reinforcements_to": b_count,
                "new_reinforcements": b_count - a_count,
            }
        return result

    @staticmethod
    def _diff_self_concept(sc_a: dict, sc_b: dict) -> dict:
        """Compare self-concept between two snapshots."""
        return {
            "purpose_changed": sc_a.get("purpose") != sc_b.get("purpose"),
            "description_changed": sc_a.get("self_description") != sc_b.get("self_description"),
            "narrative_changed": sc_a.get("current_narrative") != sc_b.get("current_narrative"),
            "aspirations_changed": sc_a.get("aspirations") != sc_b.get("aspirations"),
        }

    @staticmethod
    def _diff_traits(traits_a: dict, traits_b: dict) -> dict:
        """Compare traits between two snapshots."""
        all_traits = set(traits_a.keys()) | set(traits_b.keys())
        result = {}
        for trait in sorted(all_traits):
            a_score = traits_a.get(trait, {}).get("score", 50)
            b_score = traits_b.get(trait, {}).get("score", 50)
            if isinstance(a_score, dict):
                a_score = a_score.get("score", 50)
            if isinstance(b_score, dict):
                b_score = b_score.get("score", 50)
            change = round(b_score - a_score, 1)
            result[trait] = {
                "from": a_score,
                "to": b_score,
                "change": change,
                "direction": "increased" if change > 1 else ("decreased" if change < -1 else "stable"),
            }
        return result


# ── Timeline ────────────────────────────────────────────────────

class Timeline:
    """Analyzes snapshot history for trends, milestones, and patterns."""

    def __init__(self, snapshot_manager: SnapshotManager, storage: Optional[Storage] = None):
        self.snapshot_manager = snapshot_manager
        self.storage = storage or Storage()

    def get_timeline(self, limit: int = 50) -> dict:
        """Build a full timeline analysis from snapshot history."""
        snapshots = self.snapshot_manager.list_snapshots(limit)
        if not snapshots:
            return {"snapshot_count": 0, "snapshots": [], "trends": {}, "milestones": [], "summary": "No snapshots yet", "time_span": "N/A"}

        # Score trends
        all_layer_ids = set()
        for s in snapshots:
            all_layer_ids.update(s.get("layer_scores_summary", {}).keys())

        trends = {}
        for lid in sorted(all_layer_ids):
            scores = [s.get("layer_scores_summary", {}).get(lid, 0) for s in snapshots]
            if len(scores) >= 2:
                trends[lid] = {
                    "first": scores[0],
                    "last": scores[-1],
                    "min": min(scores),
                    "max": max(scores),
                    "avg": round(sum(scores) / len(scores), 1),
                    "trend_direction": "improving" if scores[-1] > scores[0] else ("declining" if scores[-1] < scores[0] else "stable"),
                    "volatility": round(max(scores) - min(scores), 1),
                }

        # Milestone detection
        milestones = []
        for i, s in enumerate(snapshots):
            is_milestone = False
            reasons = []
            scores = s.get("layer_scores_summary", {})

            # First snapshot
            if i == 0:
                is_milestone = True
                reasons.append("first_snapshot")

            # Score milestones
            for lid, score in scores.items():
                if score >= 90:
                    is_milestone = True
                    reasons.append(f"{lid}_reached_90")
                elif score >= 75:
                    is_milestone = True
                    reasons.append(f"{lid}_reached_75")
                elif score >= 50:
                    is_milestone = True
                    reasons.append(f"{lid}_reached_50")

            # Compare with previous
            if i > 0:
                prev = snapshots[i - 1]
                for lid in scores:
                    current = scores[lid]
                    previous = prev.get("layer_scores_summary", {}).get(lid, 0)
                    if current - previous >= 15:
                        is_milestone = True
                        reasons.append(f"{lid}_surge_{current - previous:.0f}pts")
                    elif previous - current >= 15:
                        is_milestone = True
                        reasons.append(f"{lid}_drop_{previous - current:.0f}pts")

            if is_milestone:
                milestones.append({
                    "snapshot_id": s["snapshot_id"],
                    "timestamp": s["timestamp"],
                    "tag": s.get("tag", ""),
                    "reasons": reasons,
                })

        return {
            "snapshot_count": len(snapshots),
            "time_span": self._format_timespan(snapshots),
            "snapshots": [{
                "id": s["snapshot_id"],
                "timestamp": s["timestamp"],
                "tag": s.get("tag", ""),
                "scores": s.get("layer_scores_summary", {}),
            } for s in snapshots],
            "trends": trends,
            "milestones": milestones,
            "summary": self._generate_summary(trends, milestones, snapshots),
        }

    def _format_timespan(self, snapshots: list) -> str:
        """Format the time span of snapshots as a human-readable string."""
        if len(snapshots) < 2:
            return "N/A"
        first = snapshots[0].get("timestamp", 0)
        last = snapshots[-1].get("timestamp", 0)
        span = last - first
        if span < 3600:
            return f"{span / 60:.0f} minutes"
        elif span < 86400:
            return f"{span / 3600:.1f} hours"
        else:
            return f"{span / 86400:.1f} days"

    def _generate_summary(self, trends: dict, milestones: list, snapshots: list) -> str:
        """Generate a natural-language timeline summary."""
        parts = [f"Timeline of {len(snapshots)} snapshots"]

        if trends:
            improving = [lid for lid, t in trends.items() if t["trend_direction"] == "improving"]
            declining = [lid for lid, t in trends.items() if t["trend_direction"] == "declining"]
            if improving:
                parts.append(f"improving: {', '.join(improving)}")
            if declining:
                parts.append(f"declining: {', '.join(declining)}")

        if milestones:
            parts.append(f"{len(milestones)} milestone(s) detected")

        return ". ".join(parts) + "."


# ── SnapshotScheduler ───────────────────────────────────────────

class SnapshotScheduler:
    """Automated snapshot scheduling with configurable policies.

    Supports:
    - Interval-based scheduling (every N seconds/minutes/hours)
    - Conditional triggers (on score change, crisis, etc.)
    - Retention policies (keep last N snapshots)
    """

    def __init__(self, snapshot_manager: SnapshotManager, storage: Optional[Storage] = None):
        self.snapshot_manager = snapshot_manager
        self.storage = storage or Storage()
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load scheduler config from storage."""
        default = {
            "enabled": False,
            "interval_seconds": 3600,  # every hour
            "retention_count": 100,
            "conditional_triggers": {
                "on_score_change": 10.0,  # trigger if any layer changes by 10+
                "on_crisis": True,
                "on_crisis_resolve": True,
            },
            "last_run": 0.0,
        }
        data = self.storage.read_json(self.storage._path("scheduler_config.json"))
        if data:
            default.update(data)
        return default

    def _save_config(self) -> None:
        """Save scheduler config."""
        self.storage.write_json(self.storage._path("scheduler_config.json"), self.config)
        self.storage.prune_snapshots(self.config["retention_count"])

    def configure(self, **kwargs) -> dict:
        """Update scheduler configuration."""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value
        self._save_config()
        return self.config

    def get_status(self) -> dict:
        """Get scheduler status."""
        now = time.time()
        next_run = self.config["last_run"] + self.config["interval_seconds"]
        return {
            "enabled": self.config["enabled"],
            "interval_seconds": self.config["interval_seconds"],
            "retention_count": self.config["retention_count"],
            "last_run": self.config["last_run"],
            "next_run": next_run,
            "due": now >= next_run,
            "conditional_triggers": self.config["conditional_triggers"],
        }

    def check_and_run(self, self_model, axiom_system=None) -> Optional[dict]:
        """Check if a snapshot is due and take one if so."""
        if not self.config["enabled"]:
            return None

        now = time.time()
        results = {"scheduled": False, "conditional": False, "reason": ""}

        # Interval check
        if now >= self.config["last_run"] + self.config["interval_seconds"]:
            results["scheduled"] = True
            results["reason"] = "interval_due"

        # Conditional: score change
        if not results["scheduled"] and self.config["conditional_triggers"].get("on_score_change", 0) > 0:
            snapshots = self.snapshot_manager.list_snapshots(2)
            if len(snapshots) >= 1:
                last = snapshots[-1]
                for lid, ls in self_model.layer_scores.items():
                    last_score = last.get("layer_scores_summary", {}).get(lid, 0)
                    current = ls.get("score", 0)
                    if abs(current - last_score) >= self.config["conditional_triggers"]["on_score_change"]:
                        results["conditional"] = True
                        results["reason"] = f"{lid}_changed_by_{current - last_score:.0f}"
                        break

        if results["scheduled"] or results["conditional"]:
            snapshot = self.snapshot_manager.take_snapshot(
                self_model, axiom_system,
                tag="auto-scheduled" if results["scheduled"] else "auto-conditional",
                origin="scheduled",
            )
            self.config["last_run"] = now
            self._save_config()
            results["snapshot_id"] = snapshot.snapshot_id
            return results

        return None
