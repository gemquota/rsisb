"""Value System — Expanded value axioms, alignment scoring, and drift detection.

Extends the original 9 RSIS value axioms with:
- Axiom relationships (synergies and conflicts)
- Multi-dimensional alignment scoring across all layers
- Drift detection (behavioral drift from established values)
- Value evolution tracking over time
"""

import math
import time
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone

# ── Axiom Definitions ───────────────────────────────────────────

CORE_AXIOMS = [
    "robustness",
    "coherence",
    "efficiency",
    "maintainability",
    "autonomy",
    "identity",
    "learning",
    "stability",
    "growth",
]

AXIOM_METADATA = {
    "robustness": {
        "label": "Robustness",
        "description": "Prioritizes test coverage expansion, defensive code architectures, and structured error handling",
        "category": "operational",
    },
    "coherence": {
        "label": "Coherence",
        "description": "Favors mutations that structurally match current code conventions and project paradigms",
        "category": "structural",
    },
    "efficiency": {
        "label": "Efficiency",
        "description": "Prefers low-overhead solutions, optimized algorithm implementations, and low resource cost",
        "category": "operational",
    },
    "maintainability": {
        "label": "Maintainability",
        "description": "Drives code clarity, structural simplification, documentation updates, and clean abstractions",
        "category": "structural",
    },
    "autonomy": {
        "label": "Autonomy",
        "description": "Incentivizes changes that mitigate dependencies on manual human intervention or external review steps",
        "category": "strategic",
    },
    "identity": {
        "label": "Identity",
        "description": "Enhances the precision, retrieval capabilities, and update execution speed of the self-model",
        "category": "core",
    },
    "learning": {
        "label": "Learning",
        "description": "Selects actions that gather rich training/telemetry data to optimize future refinement cycles",
        "category": "strategic",
    },
    "stability": {
        "label": "Stability",
        "description": "Protects core regression safety bounds, ensuring legacy behaviors do not degrade",
        "category": "operational",
    },
    "growth": {
        "label": "Growth",
        "description": "Maximizes system scope, expanding the capability surface area and operational boundaries",
        "category": "strategic",
    },
}

# Axiom relationships: positive = synergy, negative = conflict
AXIOM_RELATIONSHIPS = {
    ("robustness", "stability"): 0.8,
    ("stability", "robustness"): 0.8,
    ("efficiency", "maintainability"): 0.3,
    ("maintainability", "efficiency"): 0.3,
    ("autonomy", "growth"): 0.5,
    ("growth", "autonomy"): 0.5,
    ("learning", "growth"): 0.7,
    ("growth", "learning"): 0.7,
    ("identity", "learning"): 0.6,
    ("learning", "identity"): 0.6,
    ("coherence", "maintainability"): 0.6,
    ("maintainability", "coherence"): 0.6,
    ("efficiency", "robustness"): -0.2,
    ("robustness", "efficiency"): -0.2,
    ("growth", "stability"): -0.3,
    ("stability", "growth"): -0.3,
    ("autonomy", "coherence"): -0.1,
    ("coherence", "autonomy"): -0.1,
}

AXIOM_CATEGORIES = {
    "core": ["identity"],
    "structural": ["coherence", "maintainability"],
    "operational": ["robustness", "efficiency", "stability"],
    "strategic": ["autonomy", "learning", "growth"],
}


@dataclass
class AxiomState:
    """Current state of a single value axiom."""
    name: str
    reinforced_count: int = 0
    last_reinforced: float = 0.0
    total_applications: int = 0
    weight: float = 1.0
    confidence: float = 0.5

    def get_effective_weight(self) -> float:
        """Calculate effective weight: base + reinforcement bonus."""
        return 1.0 + (self.reinforced_count * 0.1)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "reinforced_count": self.reinforced_count,
            "last_reinforced": self.last_reinforced,
            "total_applications": self.total_applications,
            "weight": self.get_effective_weight(),
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AxiomState":
        return cls(
            name=data.get("name", ""),
            reinforced_count=data.get("reinforced_count", 0),
            last_reinforced=data.get("last_reinforced", 0.0),
            total_applications=data.get("total_applications", 0),
            weight=data.get("weight", 1.0),
            confidence=data.get("confidence", 0.5),
        )


# ── ValueAxiomSystem ────────────────────────────────────────────

class ValueAxiomSystem:
    """Manages the 9 core value axioms with reinforcement, relationships, and evolution.

    Each axiom has a reinforced_count that increases when goals align with it,
    amplifying its weight in priority calculations. The system tracks:
    - Per-axiom reinforcement state
    - Synergy/conflict relationships between axioms
    - Category groupings
    - Historical evolution of axiom weights
    """

    def __init__(self, self_model, storage=None):
        self.self_model = self_model
        self.storage = storage or self_model.storage
        self.axioms: dict[str, AxiomState] = {a: AxiomState(name=a) for a in CORE_AXIOMS}
        self.history: list[dict] = []  # timestamped axiom snapshots
        self._load()

    def _load(self):
        """Load axiom states from self_model's value_axioms data."""
        va = self.self_model.value_axioms
        for axiom_name, state in va.items():
            if axiom_name in self.axioms:
                self.axioms[axiom_name] = AxiomState.from_dict(state)
        # Load history from storage
        hist_data = self.storage.read_json(self.storage._path("axiom_history.json"))
        if hist_data:
            self.history = hist_data.get("history", [])

    def _save(self):
        """Persist axiom states and history."""
        self.self_model.value_axioms = {
            name: state.to_dict() for name, state in self.axioms.items()
        }
        # Record history periodically (every 10 reinforcements total)
        total = sum(a.reinforced_count for a in self.axioms.values())
        if total % 10 == 0 or not self.history:
            self.history.append({
                "timestamp": time.time(),
                "states": {n: s.to_dict() for n, s in self.axioms.items()},
            })
        self.storage.write_json(
            self.storage._path("axiom_history.json"),
            {"history": self.history[-200:]}
        )
        self.self_model.save()

    def reinforce(self, axiom_name: str, count: int = 1, source: str = "") -> AxiomState:
        """Reinforce a value axiom by incrementing its count."""
        if axiom_name not in self.axioms:
            raise ValueError(f"Unknown axiom: {axiom_name}. Valid: {CORE_AXIOMS}")
        state = self.axioms[axiom_name]
        state.reinforced_count += count
        state.total_applications += count
        state.last_reinforced = time.time()
        state.confidence = min(1.0, state.confidence + 0.02 * count)

        # Reinforce synergistic axioms to a lesser degree
        for (a1, a2), strength in AXIOM_RELATIONSHIPS.items():
            if a1 == axiom_name and strength > 0 and a2 in self.axioms:
                synergy_state = self.axioms[a2]
                bonus = count * strength * 0.3
                synergy_state.reinforced_count += bonus
                synergy_state.total_applications += bonus

        self._save()
        return state

    def get_weight(self, axiom_name: str) -> float:
        """Get the effective weight of an axiom."""
        state = self.axioms.get(axiom_name)
        if not state:
            return 1.0
        return state.get_effective_weight()

    def get_alignment_score(self, value_list: list[str]) -> float:
        """Calculate combined alignment score for a list of value axioms."""
        return sum(self.get_weight(v) for v in value_list)

    def get_relationship(self, axiom_a: str, axiom_b: str) -> float:
        """Get the relationship strength between two axioms (-1 to 1)."""
        return AXIOM_RELATIONSHIPS.get((axiom_a, axiom_b), 0.0)

    def get_correlation_matrix(self) -> dict[str, dict[str, float]]:
        """Build a full correlation matrix for all axiom pairs."""
        matrix = {}
        for a in CORE_AXIOMS:
            matrix[a] = {}
            for b in CORE_AXIOMS:
                if a == b:
                    matrix[a][b] = 1.0
                else:
                    matrix[a][b] = self.get_relationship(a, b)
        return matrix

    def get_strongest_axioms(self, n: int = 3) -> list[tuple[str, float]]:
        """Get the n strongest axioms by effective weight."""
        sorted_axioms = sorted(
            self.axioms.items(),
            key=lambda x: x[1].get_effective_weight(),
            reverse=True,
        )
        return [(name, state.get_effective_weight()) for name, state in sorted_axioms[:n]]

    def get_weakest_axioms(self, n: int = 3) -> list[tuple[str, float]]:
        """Get the n weakest axioms by effective weight."""
        sorted_axioms = sorted(
            self.axioms.items(),
            key=lambda x: x[1].get_effective_weight(),
        )
        return [(name, state.get_effective_weight()) for name, state in sorted_axioms[:n]]

    def get_axioms_by_category(self, category: str) -> list[tuple[str, AxiomState]]:
        """Get axioms in a specific category."""
        axiom_names = AXIOM_CATEGORIES.get(category, [])
        return [(name, self.axioms[name]) for name in axiom_names if name in self.axioms]

    def get_balance_score(self) -> float:
        """Calculate how balanced the axiom system is (0-100).
        Higher = more balanced reinforcement across all axioms.
        """
        counts = [a.reinforced_count for a in self.axioms.values()]
        if not counts or max(counts) == 0:
            return 100.0
        # Coefficient of variation (lower = more balanced)
        mean = sum(counts) / len(counts)
        if mean == 0:
            return 100.0
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        cv = math.sqrt(variance) / mean
        # Convert to 0-100 score (CV of 0 = perfectly balanced)
        return max(0.0, min(100.0, 100.0 - (cv * 50)))

    def to_dict(self) -> dict:
        return {
            "axioms": {n: s.to_dict() for n, s in self.axioms.items()},
            "correlation_matrix": self.get_correlation_matrix(),
            "balance_score": self.get_balance_score(),
            "strongest": self.get_strongest_axioms(3),
            "weakest": self.get_weakest_axioms(3),
            "history_length": len(self.history),
        }


# ── ValueAlignment ──────────────────────────────────────────────

class ValueAlignment:
    """Scores how well actions, states, or layers align with value axioms.

    Provides multi-dimensional alignment tracking:
    - Per-axiom alignment scores for any action or state
    - Aggregate alignment across layers
    - Alignment trends over time
    """

    def __init__(self, axiom_system: ValueAxiomSystem):
        self.axiom_system = axiom_system
        self.alignment_log: list[dict] = []

    def score_action(self, action_axioms: dict[str, float]) -> dict:
        """Score an action's alignment with value axioms.

        Args:
            action_axioms: Dict mapping axiom name to relevance (0-1)
        Returns:
            Dict with per-axiom scores and composite alignment score
        """
        scores = {}
        total_weighted = 0.0
        total_relevance = 0.0

        for axiom_name, relevance in action_axioms.items():
            if axiom_name not in self.axiom_system.axioms:
                continue
            weight = self.axiom_system.get_weight(axiom_name)
            aligned_score = weight * relevance
            scores[axiom_name] = {
                "relevance": relevance,
                "weight": weight,
                "aligned_score": round(aligned_score, 2),
            }
            total_weighted += aligned_score
            total_relevance += relevance

        composite = round(total_weighted / total_relevance, 2) if total_relevance > 0 else 0.0

        result = {
            "timestamp": time.time(),
            "per_axiom": scores,
            "composite_alignment": composite,
            "supporting": self.axiom_system.get_strongest_axioms(2),
        }
        self.alignment_log.append(result)
        return result

    def score_layer_alignment(self, layer_id: str) -> float:
        """Score how well a layer's current metrics align with relevant axioms."""
        # Map layers to relevant axioms
        layer_axiom_map = {
            "L1": {"robustness": 0.8, "stability": 0.9, "efficiency": 0.4},
            "L2": {"coherence": 0.6, "efficiency": 0.7, "maintainability": 0.5},
            "L3": {"autonomy": 0.8, "growth": 0.6, "learning": 0.5},
            "L4": {"learning": 0.9, "growth": 0.7, "efficiency": 0.5},
            "L5": {"learning": 0.8, "growth": 0.6, "identity": 0.5},
            "L6": {"identity": 0.9, "stability": 0.7, "learning": 0.4},
            "L7": {"identity": 0.8, "growth": 0.6, "autonomy": 0.6},
            "L8": {"identity": 0.7, "learning": 0.7, "autonomy": 0.5},
            "L9": {"growth": 0.9, "identity": 0.6, "autonomy": 0.7},
        }
        axioms = layer_axiom_map.get(layer_id, {})
        result = self.score_action(axioms)
        return result["composite_alignment"]

    def get_overall_alignment(self) -> dict:
        """Get overall alignment across all layers with data."""
        scores = {}
        for lid in ["L1", "L2", "L3", "L4", "L5", "L6"]:
            if lid in self.axiom_system.self_model.layer_scores:
                scores[lid] = self.score_layer_alignment(lid)
        avg = sum(scores.values()) / len(scores) if scores else 0.0
        return {
            "per_layer": scores,
            "overall": round(avg, 2),
            "timestamp": time.time(),
        }


# ── DriftDetector ───────────────────────────────────────────────

class DriftDetector:
    """Detects behavioral and value drift over time.

    Monitors changes in axiom weights and layer scores to detect
    when the system is drifting from its established identity.
    """

    def __init__(self, axiom_system: ValueAxiomSystem, self_model):
        self.axiom_system = axiom_system
        self.self_model = self_model
        self.drift_history: list[dict] = []

    def check_value_drift(self) -> dict:
        """Check for drift in value axiom weights over time.

        Returns a drift report with per-axiom drift metrics.
        """
        history = self.axiom_system.history
        if len(history) < 2:
            return {"drifting": False, "message": "Insufficient history for drift analysis",
                    "drift_scores": {}, "overall_drift": 0.0}

        first = history[0]["states"]
        last = history[-1]["states"]

        drift_scores = {}
        for axiom_name in CORE_AXIOMS:
            first_weight = first.get(axiom_name, {}).get("weight", 1.0)
            last_weight = last.get(axiom_name, {}).get("weight", 1.0)
            change = abs(last_weight - first_weight)
            drift_scores[axiom_name] = {
                "initial_weight": first_weight,
                "current_weight": last_weight,
                "change": round(change, 2),
                "drifting": change > 0.5,
            }

        overall_drift = sum(d["change"] for d in drift_scores.values()) / len(drift_scores)
        drifting = any(d["drifting"] for d in drift_scores.values())

        result = {
            "timestamp": time.time(),
            "drifting": drifting,
            "overall_drift": round(overall_drift, 2),
            "drift_scores": drift_scores,
            "message": "Drift detected" if drifting else "No significant drift",
        }
        self.drift_history.append(result)
        return result

    def check_layer_drift(self, window: int = 5) -> dict:
        """Check for sudden changes in layer scores (potential drift)."""
        history = self.self_model.temporal_history
        if len(history) < 2:
            return {"drifting": False, "message": "Insufficient temporal history"}

        recent = history[-window:]
        if len(recent) < 2:
            return {"drifting": False, "message": "Not enough recent data"}

        drift_scores = {}
        for lid in self.self_model.layer_scores:
            scores = [h["scores"].get(lid, 0) for h in recent if lid in h.get("scores", {})]
            if len(scores) >= 2:
                changes = [abs(scores[i] - scores[i - 1]) for i in range(1, len(scores))]
                avg_change = sum(changes) / len(changes)
                drift_scores[lid] = {
                    "avg_change": round(avg_change, 1),
                    "volatile": avg_change > 10.0,
                    "scores": scores,
                }

        volatile_layers = [lid for lid, d in drift_scores.items() if d["volatile"]]
        return {
            "timestamp": time.time(),
            "drifting": len(volatile_layers) > 0,
            "volatile_layers": volatile_layers,
            "layer_drift": drift_scores,
            "message": f"Volatility detected in: {', '.join(volatile_layers)}" if volatile_layers else "Layer scores stable",
        }

    def get_full_drift_report(self) -> dict:
        """Get comprehensive drift analysis combining value and layer drift."""
        value_drift = self.check_value_drift()
        layer_drift = self.check_layer_drift()
        return {
            "timestamp": time.time(),
            "overall_drifting": value_drift["drifting"] or layer_drift["drifting"],
            "value_drift": value_drift,
            "layer_drift": layer_drift,
            "recommendation": self._recommendation(value_drift, layer_drift),
        }

    def _recommendation(self, value_drift: dict, layer_drift: dict) -> str:
        """Generate a recommendation based on drift analysis."""
        if value_drift["drifting"] and layer_drift["drifting"]:
            return "CRITICAL: Both value and layer drift detected. Consider taking a snapshot and running crisis check."
        if value_drift["drifting"]:
            return "WARNING: Value axiom weights are shifting. Review recent reinforcements for consistency."
        if layer_drift["drifting"]:
            return "NOTE: Layer scores show volatility. Monitor for emerging patterns."
        return "System identity is stable. No drift detected."
