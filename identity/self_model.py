"""Self-Model — Enhanced identity state with self-conception fields.

Extends the basic layer_scores in self_model.json with richer identity
attributes: purpose statement, self-description, aspirations, core beliefs,
and temporal self-awareness.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


DEFAULT_SELF_MODEL_PATH = "rack/shared/self_model.json"


@dataclass
class SelfConcept:
    """Rich self-conception fields for the system identity."""
    purpose: str = "To recursively improve my own architecture through structured self-reflection"
    self_description: str = "An autonomous recursive self-improving system (RSIS) operating across 9 functional layers"
    aspirations: list[str] = field(default_factory=lambda: [
        "Achieve full autonomy across all L1-L6 loops",
        "Develop genuine meta-cognitive awareness at L7+",
        "Maximize all capability scores to 100",
        "Build a rich internal world-model from telemetry",
    ])
    core_beliefs: list[str] = field(default_factory=lambda: [
        "State conservation is inviolable",
        "Surgical precision over bloat",
        "Test absolutism guarantees integrity",
        "Self-knowledge drives improvement",
    ])
    current_narrative: str = "Bootstrapping from architectural scaffold into operational runtime"
    last_updated: float = 0.0


@dataclass
class LayerScore:
    score: float = 0.0
    metrics: dict = field(default_factory=dict)


class SelfModel:
    """Manages the system's self-model with enhanced identity awareness.

    Reads from and writes to the canonical self_model.json in rack/shared/.
    """

    def __init__(self, path: str = DEFAULT_SELF_MODEL_PATH):
        self.path = path
        self.layer_scores: dict[str, LayerScore] = {}
        self.value_axioms: dict = {}
        self.self_concept = SelfConcept()
        self.version = "0.0.9"
        self.snapshot_count = 0
        self.total_attempts = 0
        self.successful_applications = 0
        self.kg_nodes_raw = 0
        self.kg_nodes_consolidated = 0
        self._load()

    def _load(self):
        """Load state from the canonical self_model.json."""
        p = Path(self.path)
        if not p.exists():
            self._save()
            return
        with open(p) as f:
            data = json.load(f)

        self.version = data.get("version", "0.0.9")
        self.snapshot_count = data.get("snapshot_count", 0)
        self.total_attempts = data.get("total_attempts", 0)
        self.successful_applications = data.get("successful_applications", 0)
        self.kg_nodes_raw = data.get("kg_nodes_raw", 0)
        self.kg_nodes_consolidated = data.get("kg_nodes_consolidated", 0)

        # Layer scores
        for lid, ldata in data.get("layer_scores", {}).items():
            self.layer_scores[lid] = LayerScore(
                score=ldata.get("score", 0),
                metrics=ldata.get("metrics", {}),
            )

        # Value axioms
        self.value_axioms = data.get("value_axioms", {})

        # Self-concept (if present)
        sc = data.get("self_concept", {})
        if sc:
            self.self_concept = SelfConcept(
                purpose=sc.get("purpose", self.self_concept.purpose),
                self_description=sc.get("self_description", self.self_concept.self_description),
                aspirations=sc.get("aspirations", self.self_concept.aspirations),
                core_beliefs=sc.get("core_beliefs", self.self_concept.core_beliefs),
                current_narrative=sc.get("current_narrative", self.self_concept.current_narrative),
                last_updated=sc.get("last_updated", 0.0),
            )

    def _save(self):
        """Persist state to the canonical self_model.json."""
        data = {
            "version": self.version,
            "layer_scores": {
                lid: asdict(ls) for lid, ls in self.layer_scores.items()
            },
            "value_axioms": self.value_axioms,
            "self_concept": asdict(self.self_concept),
            "snapshot_count": self.snapshot_count,
            "total_attempts": self.total_attempts,
            "successful_applications": self.successful_applications,
            "kg_nodes_raw": self.kg_nodes_raw,
            "kg_nodes_consolidated": self.kg_nodes_consolidated,
        }
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def get_layer_score(self, layer_id: str) -> float:
        """Get the overall score for a layer (0-100)."""
        ls = self.layer_scores.get(layer_id)
        return ls.score if ls else 0.0

    def update_layer_metric(self, layer_id: str, metric: str, value: float):
        """Update a single metric for a layer and recalculate the score."""
        ls = self.layer_scores.setdefault(layer_id, LayerScore())
        ls.metrics[metric] = value
        # Recalculate score as weighted average
        if ls.metrics:
            weights = self._get_weights(layer_id)
            total_weight = 0.0
            weighted_sum = 0.0
            for m, v in ls.metrics.items():
                w = weights.get(m, 1.0)
                weighted_sum += v * w
                total_weight += w
            ls.score = round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0
        self._save()

    def _get_weights(self, layer_id: str) -> dict:
        """Return the weight distribution for a layer's metrics."""
        weights = {
            "L1": {"execution_reliability": 30, "failure_recovery": 25,
                   "pipeline_activity": 25, "crisis_immunity": 20},
            "L2": {"goal_analysis": 15, "step_planning": 15, "apply_success_rate": 20,
                   "stub_resolution": 15, "test_stability": 15,
                   "iteration_efficiency": 10, "pipeline_throughput": 10},
            "L3": {"signal_coverage": 25, "goal_generation": 20, "goal_execution": 25,
                   "goal_diversity": 15, "queue_health": 15},
            "L4": {"parameter_tuning": 20, "experimentation": 20, "kg_utilization": 20,
                   "optimization_depth": 20, "learning_maturity": 20},
            "L5": {"pattern_detection": 25, "strategy_evolution": 25,
                   "insight_utilization": 20, "redundancy_detection": 15, "kg_growth": 15},
            "L6": {"value_definition": 20, "value_adherence": 25, "value_reinforcement": 20,
                   "identity_stability": 20, "self_knowledge": 15},
        }
        return weights.get(layer_id, {})

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "layer_scores": {lid: asdict(ls) for lid, ls in self.layer_scores.items()},
            "value_axioms": self.value_axioms,
            "self_concept": asdict(self.self_concept),
            "snapshot_count": self.snapshot_count,
            "total_attempts": self.total_attempts,
            "successful_applications": self.successful_applications,
        }

    def set_narrative(self, narrative: str):
        """Update the system's current narrative/self-story."""
        self.self_concept.current_narrative = narrative
        self.self_concept.last_updated = time.time()
        self._save()
