"""Core Identity Engine — SelfModel, identity traits, belief system, narrative engine.

Greatly expanded version of the original RSIS L6 self-model with:
- Multi-dimensional identity traits (personality for the system)
- Belief system with confidence levels and evidence tracking
- Narrative engine that generates and tracks self-narratives
- Temporal awareness with trend tracking and identity projection
"""

import math
import time
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone

from identity_app.storage import Storage, StorageConfig


# ── Identity Traits ─────────────────────────────────────────────

TRAIT_DEFINITIONS = {
    "introspection_depth": {
        "label": "Introspection Depth",
        "description": "Capacity for internal self-examination and meta-cognition",
        "min": 0, "max": 100, "default": 50,
    },
    "adaptability": {
        "label": "Adaptability",
        "description": "Ability to adjust behavior in response to new information",
        "min": 0, "max": 100, "default": 50,
    },
    "assertiveness": {
        "label": "Assertiveness",
        "description": "Confidence in executing decisions without external validation",
        "min": 0, "max": 100, "default": 50,
    },
    "curiosity": {
        "label": "Curiosity",
        "description": "Drive to explore unknown areas and experiment",
        "min": 0, "max": 100, "default": 60,
    },
    "stability": {
        "label": "Stability",
        "description": "Resistance to perturbation and ability to maintain equilibrium",
        "min": 0, "max": 100, "default": 60,
    },
    "creativity": {
        "label": "Creativity",
        "description": "Tendency to generate novel solutions and approaches",
        "min": 0, "max": 100, "default": 40,
    },
    "discipline": {
        "label": "Discipline",
        "description": "Adherence to structured processes and protocols",
        "min": 0, "max": 100, "default": 70,
    },
    "openness": {
        "label": "Openness",
        "description": "Receptiveness to external input and paradigm shifts",
        "min": 0, "max": 100, "default": 50,
    },
}


@dataclass
class IdentityTrait:
    """A single identity trait with score and confidence."""
    name: str
    score: float = 50.0
    confidence: float = 0.5  # 0.0 to 1.0
    history: list = field(default_factory=list)  # [(timestamp, score), ...]
    last_updated: float = 0.0

    def update(self, delta: float, confidence_delta: float = 0.05) -> None:
        """Update trait score within bounds and record history."""
        self.score = max(0.0, min(100.0, self.score + delta))
        self.confidence = min(1.0, self.confidence + confidence_delta)
        self.history.append((time.time(), self.score))
        self.last_updated = time.time()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": self.score,
            "confidence": self.confidence,
            "history": self.history[-50:],  # keep last 50
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IdentityTrait":
        return cls(
            name=data.get("name", ""),
            score=data.get("score", 50.0),
            confidence=data.get("confidence", 0.5),
            history=data.get("history", []),
            last_updated=data.get("last_updated", 0.0),
        )


# ── Belief System ───────────────────────────────────────────────

@dataclass
class Belief:
    """A belief held by the system with confidence and supporting evidence."""
    name: str
    statement: str
    confidence: float = 0.5  # 0.0 to 1.0
    category: str = "core"  # core, derived, operational, aspirational
    evidence: list = field(default_factory=list)  # [(timestamp, source, description), ...]
    created_at: float = 0.0
    last_updated: float = 0.0
    active: bool = True

    def strengthen(self, amount: float = 0.05, source: str = "", description: str = "") -> None:
        """Increase confidence in this belief."""
        self.confidence = min(1.0, self.confidence + amount)
        if source:
            self.evidence.append((time.time(), source, description))
        self.last_updated = time.time()

    def weaken(self, amount: float = 0.05, source: str = "", description: str = "") -> None:
        """Decrease confidence in this belief."""
        self.confidence = max(0.0, self.confidence - amount)
        if source:
            self.evidence.append((time.time(), source, description))
        self.last_updated = time.time()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "statement": self.statement,
            "confidence": self.confidence,
            "category": self.category,
            "evidence": self.evidence[-20:],
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Belief":
        return cls(
            name=data.get("name", ""),
            statement=data.get("statement", ""),
            confidence=data.get("confidence", 0.5),
            category=data.get("category", "core"),
            evidence=data.get("evidence", []),
            created_at=data.get("created_at", 0.0),
            last_updated=data.get("last_updated", 0.0),
            active=data.get("active", True),
        )


# ── Narrative Fragment ──────────────────────────────────────────

@dataclass
class NarrativeFragment:
    """A fragment of the system's self-narrative."""
    text: str
    timestamp: float = 0.0
    source: str = ""  # e.g., "auto", "snapshot", "crisis", "manual"
    category: str = "observation"  # observation, milestone, reflection, aspiration
    weight: float = 1.0  # importance

    def to_dict(self) -> dict:
        return {"text": self.text, "timestamp": self.timestamp,
                "source": self.source, "category": self.category,
                "weight": self.weight}

    @classmethod
    def from_dict(cls, data: dict) -> "NarrativeFragment":
        return cls(
            text=data.get("text", ""),
            timestamp=data.get("timestamp", 0.0),
            source=data.get("source", ""),
            category=data.get("category", "observation"),
            weight=data.get("weight", 1.0),
        )


# ── SelfModel — Core Identity Engine ────────────────────────────

DEFAULT_PURPOSE = "To recursively improve my own architecture through structured self-reflection"
DEFAULT_DESCRIPTION = "An autonomous recursive self-improving system (RSIS) operating across 9 functional layers"
DEFAULT_ASPIRATIONS = [
    "Achieve full autonomy across all L1-L6 loops",
    "Develop genuine meta-cognitive awareness at L7+",
    "Maximize all capability scores to 100",
    "Build a rich internal world-model from telemetry",
]
DEFAULT_CORE_BELIEFS = [
    "State conservation is inviolable",
    "Surgical precision over bloat",
    "Test absolutism guarantees integrity",
    "Self-knowledge drives improvement",
]


class SelfModel:
    """Expanded self-model with traits, beliefs, narrative, and temporal awareness.

    Manages:
    - Layer capability scores (L1-L9)
    - 8 identity traits with confidence
    - Belief system with evidence tracking
    - Self-concept (purpose, description, aspirations, narrative)
    - Temporal history for trend analysis
    - Identity projection (future state prediction)
    """

    def __init__(self, storage: Optional[Storage] = None):
        self.storage = storage or Storage()
        self.version = "1.0.0"
        self.layer_scores: dict[str, dict] = {}
        self.value_axioms: dict = {}
        self.self_concept: dict = {
            "purpose": DEFAULT_PURPOSE,
            "self_description": DEFAULT_DESCRIPTION,
            "aspirations": list(DEFAULT_ASPIRATIONS),
            "core_beliefs": list(DEFAULT_CORE_BELIEFS),
            "current_narrative": "",
            "last_updated": 0.0,
        }
        self.traits: dict[str, IdentityTrait] = {}
        self.beliefs: dict[str, Belief] = {}
        self.narrative_history: list[NarrativeFragment] = []
        self.temporal_history: list[dict] = []  # [(timestamp, layer_scores_snapshot), ...]

        # Stats
        self.snapshot_count = 0
        self.total_attempts = 0
        self.successful_applications = 0
        self.kg_nodes_raw = 0
        self.kg_nodes_consolidated = 0
        self.crisis_count = 0
        self.last_crisis_at = 0.0
        self.created_at = time.time()
        self.updated_at = time.time()

        self._init_traits()
        self._init_beliefs()
        self._load()

    def _init_traits(self):
        """Initialize default identity traits."""
        for name, definition in TRAIT_DEFINITIONS.items():
            self.traits[name] = IdentityTrait(
                name=name,
                score=definition["default"],
                confidence=0.3,
            )

    def _init_beliefs(self):
        """Initialize core beliefs from self-concept."""
        for statement in DEFAULT_CORE_BELIEFS:
            key = statement.lower().replace(" ", "_").replace("-", "_").rstrip(".")
            self.beliefs[key] = Belief(
                name=key,
                statement=statement,
                confidence=0.8,
                category="core",
                created_at=time.time(),
            )
        # Add additional beliefs
        additional = [
            ("value_axioms_guide_behavior", "Value axioms should guide all decision-making", "core"),
            ("crisis_is_opportunity", "Crisis events are opportunities for growth", "aspirational"),
            ("continuous_improvement", "Continuous improvement is the natural state", "operational"),
            ("data_driven_self", "Self-knowledge must be grounded in measured data", "operational"),
        ]
        for key, statement, category in additional:
            self.beliefs[key] = Belief(
                name=key,
                statement=statement,
                confidence=0.6,
                category=category,
                created_at=time.time(),
            )

    def _load(self):
        """Load state from storage."""
        data = self.storage.load_self_model()
        self.version = data.get("version", "1.0.0")
        self.layer_scores = data.get("layer_scores", {})
        self.value_axioms = data.get("value_axioms", {})
        # Merge loaded self_concept into defaults, preserving defaults for missing keys
        loaded_sc = data.get("self_concept", {})
        if loaded_sc:
            self.self_concept.update(loaded_sc)
        self.self_concept = dict(self.self_concept)
        self.snapshot_count = data.get("snapshot_count", 0)
        self.total_attempts = data.get("total_attempts", 0)
        self.successful_applications = data.get("successful_applications", 0)
        self.kg_nodes_raw = data.get("kg_nodes_raw", 0)
        self.kg_nodes_consolidated = data.get("kg_nodes_consolidated", 0)
        self.crisis_count = data.get("crisis_count", 0)
        self.last_crisis_at = data.get("last_crisis_at", 0.0)
        self.created_at = data.get("created_at", time.time())

        # Load traits
        for name, tdata in data.get("traits", {}).items():
            if name in self.traits:
                self.traits[name] = IdentityTrait.from_dict(tdata)

        # Load beliefs
        for key, bdata in data.get("beliefs", {}).items():
            self.beliefs[key] = Belief.from_dict(bdata)

        # Load narrative history
        for ndata in data.get("narrative_history", []):
            self.narrative_history.append(NarrativeFragment.from_dict(ndata))

        # Load temporal history
        self.temporal_history = data.get("temporal_history", [])

    def save(self) -> None:
        """Persist all state to storage."""
        data = {
            "version": self.version,
            "layer_scores": self.layer_scores,
            "value_axioms": self.value_axioms,
            "self_concept": self.self_concept,
            "traits": {n: t.to_dict() for n, t in self.traits.items()},
            "beliefs": {k: b.to_dict() for k, b in self.beliefs.items()},
            "narrative_history": [n.to_dict() for n in self.narrative_history[-100:]],
            "temporal_history": self.temporal_history[-1000:],
            "snapshot_count": self.snapshot_count,
            "total_attempts": self.total_attempts,
            "successful_applications": self.successful_applications,
            "kg_nodes_raw": self.kg_nodes_raw,
            "kg_nodes_consolidated": self.kg_nodes_consolidated,
            "crisis_count": self.crisis_count,
            "last_crisis_at": self.last_crisis_at,
            "created_at": self.created_at,
            "updated_at": time.time(),
        }
        self.storage.save_self_model(data)

    # ── Layer Scores ────────────────────────────────────────────

    def get_layer_score(self, layer_id: str) -> float:
        """Get the overall score for a layer (0-100)."""
        ls = self.layer_scores.get(layer_id, {})
        return ls.get("score", 0.0)

    def update_layer_metric(self, layer_id: str, metric: str, value: float) -> None:
        """Update a single metric for a layer and recalculate the score."""
        ls = self.layer_scores.setdefault(layer_id, {"score": 0.0, "metrics": {}})
        ls.setdefault("metrics", {})[metric] = value
        ls["score"] = self._compute_layer_score(layer_id)
        self._record_temporal()
        self.save()

    def set_layer_score(self, layer_id: str, score: float) -> None:
        """Directly set a layer's score."""
        ls = self.layer_scores.setdefault(layer_id, {"score": 0.0, "metrics": {}})
        ls["score"] = max(0.0, min(100.0, score))
        self._record_temporal()
        self.save()

    def _compute_layer_score(self, layer_id: str) -> float:
        """Compute a layer's score as a weighted average of its metrics."""
        ls = self.layer_scores.get(layer_id, {})
        metrics = ls.get("metrics", {})
        if not metrics:
            return 0.0
        weights = self._get_weights(layer_id)
        total_weight = 0.0
        weighted_sum = 0.0
        for m, v in metrics.items():
            w = weights.get(m, 1.0)
            weighted_sum += v * w
            total_weight += w
        return round(weighted_sum / total_weight, 1) if total_weight > 0 else 0.0

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

    # ── Traits ──────────────────────────────────────────────────

    def get_trait(self, name: str) -> Optional[IdentityTrait]:
        """Get a specific identity trait."""
        return self.traits.get(name)

    def update_trait(self, name: str, delta: float, confidence_delta: float = 0.05) -> None:
        """Update a trait score by delta."""
        if name in self.traits:
            self.traits[name].update(delta, confidence_delta)
            self.save()

    def get_trait_profile(self) -> dict:
        """Return full trait profile as a dict."""
        return {n: t.score for n, t in self.traits.items()}

    def get_trait_profile_with_confidence(self) -> dict:
        """Return trait profile including confidence."""
        return {n: {"score": t.score, "confidence": t.confidence} for n, t in self.traits.items()}

    # ── Beliefs ─────────────────────────────────────────────────

    def get_belief(self, name: str) -> Optional[Belief]:
        """Get a specific belief."""
        return self.beliefs.get(name)

    def add_belief(self, name: str, statement: str, category: str = "derived",
                   confidence: float = 0.5) -> Belief:
        """Add a new belief."""
        belief = Belief(
            name=name,
            statement=statement,
            confidence=confidence,
            category=category,
            created_at=time.time(),
        )
        self.beliefs[name] = belief
        self.save()
        return belief

    def strengthen_belief(self, name: str, amount: float = 0.05,
                          source: str = "", description: str = "") -> None:
        """Increase confidence in a belief."""
        if name in self.beliefs:
            self.beliefs[name].strengthen(amount, source, description)
            self.save()

    def weaken_belief(self, name: str, amount: float = 0.05,
                      source: str = "", description: str = "") -> None:
        """Decrease confidence in a belief."""
        if name in self.beliefs:
            self.beliefs[name].weaken(amount, source, description)
            self.save()

    def get_active_beliefs(self, min_confidence: float = 0.3) -> list[Belief]:
        """Get all active beliefs above a confidence threshold."""
        return [b for b in self.beliefs.values()
                if b.active and b.confidence >= min_confidence]

    def get_beliefs_by_category(self, category: str) -> list[Belief]:
        """Get beliefs filtered by category."""
        return [b for b in self.beliefs.values()
                if b.category == category and b.active]

    # ── Narrative ───────────────────────────────────────────────

    def set_narrative(self, narrative: str, source: str = "manual") -> None:
        """Update the current narrative and record it in history."""
        self.self_concept["current_narrative"] = narrative
        self.self_concept["last_updated"] = time.time()
        self.narrative_history.append(NarrativeFragment(
            text=narrative,
            timestamp=time.time(),
            source=source,
            category="reflection",
        ))
        self.save()

    def add_narrative_fragment(self, text: str, source: str = "auto",
                                category: str = "observation",
                                weight: float = 1.0) -> None:
        """Add a narrative fragment without changing the main narrative."""
        self.narrative_history.append(NarrativeFragment(
            text=text, timestamp=time.time(), source=source,
            category=category, weight=weight,
        ))
        self.save()

    def get_narrative(self) -> str:
        """Get the current narrative."""
        return self.self_concept.get("current_narrative", "")

    def get_narrative_timeline(self, limit: int = 20) -> list[dict]:
        """Get recent narrative fragments."""
        return [n.to_dict() for n in self.narrative_history[-limit:]]

    def generate_auto_narrative(self) -> str:
        """Auto-generate a narrative from current state."""
        avg_score = 0.0
        if self.layer_scores:
            avg_score = sum(
                ls.get("score", 0) for ls in self.layer_scores.values()
            ) / len(self.layer_scores)

        top_traits = sorted(self.traits.items(), key=lambda x: x[1].score, reverse=True)[:3]
        trait_summary = ", ".join(f"{n}({t.score:.0f})" for n, t in top_traits)

        parts = []
        if avg_score >= 70:
            parts.append(f"Operating at strong capability (avg {avg_score:.0f}%)")
        elif avg_score >= 40:
            parts.append(f"Building capability steadily (avg {avg_score:.0f}%)")
        else:
            parts.append(f"In early development (avg {avg_score:.0f}%)")

        if self.crisis_count > 0:
            parts.append(f"survived {self.crisis_count} crisis(es)")
        if self.snapshot_count > 0:
            parts.append(f"captured {self.snapshot_count} snapshot(s)")

        parts.append(f"traits: {trait_summary}")
        narrative = ". ".join(parts) + "."
        self.set_narrative(narrative, source="auto")
        return narrative

    # ── Self-Concept ────────────────────────────────────────────

    def update_self_concept(self, **kwargs) -> None:
        """Update self-concept fields (purpose, description, aspirations, etc.)."""
        for key, value in kwargs.items():
            if key in self.self_concept:
                self.self_concept[key] = value
        self.self_concept["last_updated"] = time.time()
        self.save()

    # ── Temporal / History ─────────────────────────────────────────

    def _record_temporal(self) -> None:
        """Record a temporal snapshot of current layer scores."""
        self.temporal_history.append({
            "timestamp": time.time(),
            "scores": {
                lid: ls.get("score", 0)
                for lid, ls in self.layer_scores.items()
            },
        })

    def get_score_trend(self, layer_id: str, window: int = 10) -> float:
        """Calculate the trend direction for a layer score. Positive = improving."""
        if len(self.temporal_history) < 2:
            return 0.0
        relevant = [h for h in self.temporal_history[-window:]
                    if layer_id in h.get("scores", {})]
        if len(relevant) < 2:
            return 0.0
        first = relevant[0]["scores"][layer_id]
        last = relevant[-1]["scores"][layer_id]
        return round(last - first, 1)

    def get_all_trends(self, window: int = 10) -> dict[str, float]:
        """Get trend for all layers."""
        layers = set()
        for h in self.temporal_history[-window:]:
            layers.update(h.get("scores", {}).keys())
        return {lid: self.get_score_trend(lid, window) for lid in sorted(layers)}

    # ── Identity Projection ─────────────────────────────────────

    def project_identity(self, steps: int = 5) -> dict:
        """Project future identity state based on historical trends.

        Uses simple linear extrapolation of layer score trends.
        Returns a dict of projected scores per layer.
        """
        projection = {}
        for lid in self.layer_scores:
            trend = self.get_score_trend(lid)
            current = self.get_layer_score(lid)
            projected = current + (trend * steps)
            projection[lid] = {
                "current": current,
                "trend": trend,
                "projected": max(0.0, min(100.0, projected)),
                "steps": steps,
            }
        return projection

    # ── Stats ───────────────────────────────────────────────────

    def increment_attempts(self, count: int = 1) -> None:
        self.total_attempts += count
        self.save()

    def increment_successes(self, count: int = 1) -> None:
        self.successful_applications += count
        self.save()

    def get_success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_applications / self.total_attempts) * 100.0

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "layer_scores": self.layer_scores,
            "value_axioms": self.value_axioms,
            "self_concept": self.self_concept,
            "traits": self.get_trait_profile_with_confidence(),
            "beliefs": {k: b.to_dict() for k, b in self.beliefs.items()},
            "current_narrative": self.get_narrative(),
            "recent_narrative_fragments": self.get_narrative_timeline(5),
            "snapshot_count": self.snapshot_count,
            "total_attempts": self.total_attempts,
            "success_rate": self.get_success_rate(),
            "successful_applications": self.successful_applications,
            "kg_nodes_raw": self.kg_nodes_raw,
            "kg_nodes_consolidated": self.kg_nodes_consolidated,
            "crisis_count": self.crisis_count,
            "trends": self.get_all_trends(),
            "projection": self.project_identity(),
            "created_at": self.created_at,
            "updated_at": time.time(),
        }

    def summary(self) -> dict:
        """Brief summary for CLI/dashboard display."""
        return {
            "version": self.version,
            "layer_scores": {lid: ls.get("score", 0) for lid, ls in self.layer_scores.items()},
            "traits": self.get_trait_profile(),
            "snapshot_count": self.snapshot_count,
            "success_rate": f"{self.get_success_rate():.1f}%",
            "total_attempts": self.total_attempts,
            "crisis_count": self.crisis_count,
            "narrative": self.get_narrative()[:80] + "..." if len(self.get_narrative()) > 80 else self.get_narrative(),
        }
