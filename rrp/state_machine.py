"""RRP State Machine — Pure deterministic state core.

No IO, no LLM calls, no side effects. The RRPState dataclass tracks
everything: ambiguity vectors, decisions, constraints, telemetry v2.0,
agent switching, and session lifecycle.
"""

import time
import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# === Enums ===

class UseCase(Enum):
    ALIGNMENT = 1
    IDEATION = 2
    CONVERGENCE = 3
    STRESS_TESTING = 4
    DATA_MAPPING = 5
    DETERMINISM = 6


class ExecutionMode(Enum):
    HYBRID = 1
    BATCH = 2
    PULSE = 3


class DecisionType(Enum):
    COMMITMENT = "commitment"
    DEFERRAL = "deferral"
    REJECTION = "rejection"
    CLARIFICATION = "clarification"
    EXPERIMENT = "experiment"


# === Core Dataclasses ===

@dataclass
class AmbiguityVector:
    """Four dimensions of ambiguity, each 0.0 (none) to 1.0 (max)."""
    requirements: float = 0.5
    data_model: float = 0.5
    edge_case: float = 0.5
    determinism: float = 0.5

    def average(self) -> float:
        return (self.requirements + self.data_model + self.edge_case + self.determinism) / 4.0

    def all_below(self, threshold: float) -> bool:
        return (self.requirements <= threshold and self.data_model <= threshold
                and self.edge_case <= threshold and self.determinism <= threshold)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Constraint:
    """A locked constraint extracted from user input."""
    key: str
    value: str
    locked_round: int
    source: str = ""  # e.g., "user_input", "evaluation"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Decision:
    """A recorded decision with context."""
    round: int
    decision_type: DecisionType
    description: str
    reasoning: str = ""
    confidence: float = 0.8
    timestamp: float = 0.0
    ambiguity_at_time: Optional[AmbiguityVector] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["decision_type"] = self.decision_type.value
        if self.ambiguity_at_time:
            d["ambiguity_at_time"] = self.ambiguity_at_time.to_dict()
        return d


@dataclass
class TokenBudget:
    """Per-round/session token tracking."""
    per_round_limit: int = 4000
    session_limit: int = 32000
    round_usage: list[int] = field(default_factory=list)
    saturation_alert: bool = False

    def saturation_percent(self) -> float:
        total = sum(self.round_usage)
        return round((total / self.session_limit) * 100, 1) if self.session_limit else 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QuestionQualityIndex:
    """Rolling score average for question quality."""
    scores: list[float] = field(default_factory=list)

    def average(self) -> float:
        return round(sum(self.scores) / len(self.scores), 2) if self.scores else 0.0

    def to_dict(self) -> dict:
        return {"average": self.average(), "scores": self.scores}


@dataclass
class UserSatisfactionDelta:
    """Cumulative satisfaction tracking with trend."""
    cumulative: float = 0.0
    deltas: list[float] = field(default_factory=list)

    def trend(self) -> str:
        if len(self.deltas) < 2:
            return "→"
        recent = self.deltas[-3:]
        avg = sum(recent) / len(recent)
        if avg > 0.3:
            return "↑"
        elif avg < -0.3:
            return "↓"
        return "→"

    def to_dict(self) -> dict:
        return {"cumulative": self.cumulative, "trend": self.trend(), "deltas": self.deltas}


@dataclass
class TemporalVelocity:
    """Round timing metrics."""
    round_times: list[float] = field(default_factory=list)
    start_time: float = 0.0

    def avg_duration(self) -> float:
        return round(sum(self.round_times) / len(self.round_times), 2) if self.round_times else 0.0

    def to_dict(self) -> dict:
        return {"rounds": len(self.round_times), "avg_duration": self.avg_duration(), "total_elapsed": round(time.time() - self.start_time, 1) if self.start_time else 0.0}


@dataclass
class TopicCoverage:
    """8-bit bitmask tracking ARCH, SEC, DATA, PERF, SCAL, TEST, DEPL, UX."""
    mask: int = 0

    TOPICS = ["ARCH", "SEC", "DATA", "PERF", "SCAL", "TEST", "DEPL", "UX"]

    def set_topic(self, topic: str):
        if topic in self.TOPICS:
            idx = self.TOPICS.index(topic)
            self.mask |= (1 << idx)

    def has_topic(self, topic: str) -> bool:
        if topic in self.TOPICS:
            idx = self.TOPICS.index(topic)
            return bool(self.mask & (1 << idx))
        return False

    def coverage_percent(self) -> float:
        return round((bin(self.mask).count("1") / 8) * 100, 1)

    def covered_topics(self) -> list[str]:
        return [t for i, t in enumerate(self.TOPICS) if self.mask & (1 << i)]

    def to_dict(self) -> dict:
        return {"mask": self.mask, "coverage_percent": self.coverage_percent(), "covered": self.covered_topics()}


@dataclass
class Contradiction:
    """A detected contradiction between constraints."""
    constraint_a: str
    constraint_b: str
    description: str
    resolved: bool = False
    resolution: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Checkpoint:
    """A saved state snapshot for fork/rollback."""
    round: int
    ambiguity: AmbiguityVector
    decisions: list[Decision]
    constraints: list[Constraint]
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "ambiguity": self.ambiguity.to_dict(),
            "decisions": [d.to_dict() for d in self.decisions],
            "constraints": [c.to_dict() for c in self.constraints],
            "timestamp": self.timestamp,
        }


@dataclass
class SessionMeta:
    """Session identification and configuration."""
    session_id: str = "default"
    use_case: UseCase = UseCase.ALIGNMENT
    execution_mode: ExecutionMode = ExecutionMode.HYBRID
    max_rounds: int = 5
    depth: int = 2  # 1=Shallow, 2=Standard, 3=Deep
    open_questions_per_round: int = 3
    mcq_options_per_question: int = 3
    created_at: float = 0.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["use_case"] = self.use_case.value
        d["execution_mode"] = self.execution_mode.value
        return d


@dataclass
class Telemetry:
    """RRP v2.0 telemetry suite."""
    token_budget: TokenBudget = field(default_factory=TokenBudget)
    question_quality: QuestionQualityIndex = field(default_factory=QuestionQualityIndex)
    satisfaction: UserSatisfactionDelta = field(default_factory=UserSatisfactionDelta)
    velocity: TemporalVelocity = field(default_factory=TemporalVelocity)
    topic_coverage: TopicCoverage = field(default_factory=TopicCoverage)
    transaction_ledger: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "token_budget": self.token_budget.to_dict(),
            "question_quality": self.question_quality.to_dict(),
            "satisfaction": self.satisfaction.to_dict(),
            "velocity": self.velocity.to_dict(),
            "topic_coverage": self.topic_coverage.to_dict(),
            "ledger_entries": len(self.transaction_ledger),
        }


@dataclass
class RRPState:
    """Complete RRP session state — the single source of truth."""

    # Core
    session: SessionMeta = field(default_factory=SessionMeta)
    current_round: int = 0
    status: str = "initialized"  # initialized | active | completed | early_term | halted

    # Ambiguity
    ambiguity: AmbiguityVector = field(default_factory=AmbiguityVector)
    ambiguity_history: list[dict] = field(default_factory=list)

    # Constraints & Decisions
    constraints: list[Constraint] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)

    # Telemetry v2.0
    telemetry: Telemetry = field(default_factory=Telemetry)

    # Session lifecycle
    checkpoints: list[Checkpoint] = field(default_factory=list)
    agent_personas: list[str] = field(default_factory=list)
    current_agent: str = "default"
    summary: str = ""

    # Input/Output history
    round_inputs: list[str] = field(default_factory=list)
    round_outputs: list[str] = field(default_factory=list)

    # Version
    rrp_version: str = "2.1"

    @property
    def is_completed(self) -> bool:
        return self.status in ("completed", "early_term", "halted")

    @property
    def use_case_value(self) -> int:
        return self.session.use_case.value

    @property
    def execution_mode_value(self) -> int:
        return self.session.execution_mode.value

    def to_dict(self) -> dict:
        return {
            "rrp_version": self.rrp_version,
            "session": self.session.to_dict(),
            "current_round": self.current_round,
            "status": self.status,
            "ambiguity": self.ambiguity.to_dict(),
            "ambiguity_history": self.ambiguity_history[-20:],
            "constraints": [c.to_dict() for c in self.constraints],
            "decisions": [d.to_dict() for d in self.decisions[-20:]],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "telemetry": self.telemetry.to_dict(),
            "checkpoints": len(self.checkpoints),
            "agent_personas": self.agent_personas,
            "current_agent": self.current_agent,
            "summary": self.summary,
            "round_count": self.current_round,
            "is_completed": self.is_completed,
        }

    # === Mutators (pure, no IO) ===

    def set_ambiguity(self, requirements: Optional[float] = None,
                      data_model: Optional[float] = None,
                      edge_case: Optional[float] = None,
                      determinism: Optional[float] = None) -> 'RRPState':
        """Set ambiguity dimensions and record history."""
        if requirements is not None:
            self.ambiguity.requirements = max(0.0, min(1.0, requirements))
        if data_model is not None:
            self.ambiguity.data_model = max(0.0, min(1.0, data_model))
        if edge_case is not None:
            self.ambiguity.edge_case = max(0.0, min(1.0, edge_case))
        if determinism is not None:
            self.ambiguity.determinism = max(0.0, min(1.0, determinism))

        self.ambiguity_history.append({
            "round": self.current_round,
            "ambiguity": self.ambiguity.to_dict(),
            "timestamp": time.time(),
        })
        return self

    def add_constraint(self, key: str, value: str, source: str = "user") -> 'RRPState':
        """Lock a constraint. Detects contradictions with existing constraints."""
        # Check for contradictions
        for existing in self.constraints:
            if existing.key.lower() == key.lower() and existing.value.lower() != value.lower():
                self.contradictions.append(Contradiction(
                    constraint_a=f"{existing.key}={existing.value}",
                    constraint_b=f"{key}={value}",
                    description=f"Contradiction detected: {existing.key} was '{existing.value}' but new input says '{value}'",
                ))

        self.constraints.append(Constraint(
            key=key, value=value, locked_round=self.current_round, source=source
        ))
        return self

    def add_decision(self, decision_type: DecisionType, description: str,
                     reasoning: str = "", confidence: float = 0.8) -> 'RRPState':
        """Record a decision at the current round."""
        self.decisions.append(Decision(
            round=self.current_round,
            decision_type=decision_type,
            description=description,
            reasoning=reasoning,
            confidence=confidence,
            ambiguity_at_time=AmbiguityVector(
                requirements=self.ambiguity.requirements,
                data_model=self.ambiguity.data_model,
                edge_case=self.ambiguity.edge_case,
                determinism=self.ambiguity.determinism,
            ),
        ))
        return self

    def next_round(self) -> 'RRPState':
        """Advance to the next round."""
        self.current_round += 1
        self.status = "active"
        self.telemetry.velocity.round_times.append(time.time())
        return self

    def check_early_termination(self) -> bool:
        """Check if session should terminate early.

        Conditions (v2.1):
          1. round >= max(3, floor(Z * 0.7))
          2. All 4 ambiguity dimensions <= 0.05
          OR safety valve: 100% topic coverage AND avg ambiguity <= 0.15
        """
        min_rounds = max(3, int(self.session.max_rounds * 0.7))

        if self.current_round < min_rounds:
            return False

        condition_a = self.ambiguity.all_below(0.05)

        topic_full = self.telemetry.topic_coverage.coverage_percent() >= 100.0
        avg_low = self.ambiguity.average() <= 0.15
        condition_b = topic_full and avg_low

        if condition_a or condition_b:
            self.status = "early_term"
            return True
        return False

    def auto_compile_summary(self) -> str:
        """Generate a rolling summary of the session."""
        parts = []
        parts.append(f"RRP v{self.rrp_version} | Session: {self.session.session_id}")
        parts.append(f"Use Case: U{self.session.use_case.value} | Rounds: {self.current_round}/{self.session.max_rounds}")
        parts.append(f"Ambiguity: req={self.ambiguity.requirements:.2f} dm={self.ambiguity.data_model:.2f} ec={self.ambiguity.edge_case:.2f} det={self.ambiguity.determinism:.2f}")
        parts.append(f"Decisions: {len(self.decisions)} | Constraints: {len(self.constraints)} | Contradictions: {len(self.contradictions)}")

        if self.decisions:
            latest = self.decisions[-1]
            parts.append(f"Latest: {latest.decision_type.value} — {latest.description[:60]}")

        self.summary = " | ".join(parts)
        return self.summary

    def checkpoint_save(self) -> 'Checkpoint':
        """Save a checkpoint of current state."""
        cp = Checkpoint(
            round=self.current_round,
            ambiguity=AmbiguityVector(**asdict(self.ambiguity)),
            decisions=list(self.decisions),
            constraints=list(self.constraints),
            timestamp=time.time(),
        )
        self.checkpoints.append(cp)
        return cp

    def checkpoint_rollback(self, checkpoint_id: int = -1) -> bool:
        """Rollback to a previous checkpoint."""
        if not self.checkpoints:
            return False
        cp = self.checkpoints[checkpoint_id]
        self.ambiguity = cp.ambiguity
        self.decisions = cp.decisions
        self.constraints = cp.constraints
        self.current_round = cp.round
        return True
