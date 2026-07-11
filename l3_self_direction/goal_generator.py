"""Goal Generator — Produces ranked goals from signals, system state, and value axioms.

Consumes signals from the SignalWatcher and generates structured goals
ranked by priority. Goals are pushed into the QueueManager for execution.
"""

import time
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable

from l3_self_direction.signal_watcher import Signal


@dataclass
class Goal:
    """A structured goal for the L2 execution loop."""
    id: str
    description: str
    priority: float  # 0.0 (low) to 1.0 (critical)
    source_signal: Optional[str] = None
    value_alignment: list[str] = field(default_factory=list)
    suggested_tasks: list[str] = field(default_factory=list)
    created_at: float = 0.0
    status: str = "pending"  # pending | queued | executing | completed | archived

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict:
        return asdict(self)


class GoalGenerator:
    """Generates goals from signals and system state.

    Each signal is analyzed against the current system state and value
    axioms to produce a ranked goal. Goals with higher priority (closer
    to 1.0) should be executed first.
    """

    def __init__(self):
        self.goals: list[Goal] = []
        self._generated_count = 0
        self._custom_handlers: list[Callable] = []

    def register_handler(self, handler: Callable):
        """Register a custom signal-to-goal handler function.

        The handler receives (signal, system_state) and returns a Goal
        or None.
        """
        self._custom_handlers.append(handler)

    def process_signal(self, signal: Signal, system_state: Optional[dict] = None) -> Optional[Goal]:
        """Process a single signal and generate a goal if appropriate."""
        # Try custom handlers first
        for handler in self._custom_handlers:
            try:
                goal = handler(signal, system_state or {})
                if goal is not None:
                    self._generated_count += 1
                    self.goals.append(goal)
                    return goal
            except Exception:
                continue

        # Default handlers based on signal type
        if signal.signal_type == "file_created" and signal.source.endswith(".py"):
            goal = self._make_goal(
                description=f"New Python file detected: {signal.source}",
                priority=0.4,
                source_signal=signal.source,
                value_alignment=["growth", "learning"],
                suggested_tasks=[f"Review {signal.source} for stubs", "Add to test suite"],
            )
            self._generated_count += 1
            self.goals.append(goal)
            return goal

        if signal.signal_type == "file_modified" and signal.source.endswith((".py", ".md")):
            # Check if it's a stub file that needs patching
            goal = self._make_goal(
                description=f"File modified: {signal.source}",
                priority=0.3,
                source_signal=signal.source,
                value_alignment=["maintainability", "stability"],
                suggested_tasks=[f"Check {signal.source} for new stubs", "Run tests"],
            )
            self._generated_count += 1
            self.goals.append(goal)
            return goal

        if signal.signal_type == "file_created" and signal.source.endswith(".md"):
            goal = self._make_goal(
                description=f"Documentation added: {signal.source}",
                priority=0.2,
                source_signal=signal.source,
                value_alignment=["coherence", "maintainability"],
            )
            self._generated_count += 1
            self.goals.append(goal)
            return goal

        return None

    def generate_from_state(self, system_state: dict) -> list[Goal]:
        """Generate goals from system state analysis (not from signals)."""
        new_goals = []

        # Check for crisis conditions
        if system_state.get("crisis_active"):
            goal = self._make_goal(
                description="Resolve active identity crisis",
                priority=0.95,
                value_alignment=["stability", "identity"],
                suggested_tasks=["Analyze crisis violations", "Improve affected metrics"],
            )
            new_goals.append(goal)

        # Check for low layer scores
        layer_scores = system_state.get("layer_scores", {})
        for lid, score in layer_scores.items():
            if isinstance(score, (int, float)) and score < 15:
                goal = self._make_goal(
                    description=f"Boost {lid} score from {score}",
                    priority=0.7 + (15 - min(score, 15)) / 100,
                    value_alignment=["robustness", "growth"],
                    suggested_tasks=[f"Analyze {lid} metrics", "Plan improvement cycle"],
                )
                new_goals.append(goal)

        # Check for empty metrics (score of 0)
        metrics = system_state.get("metrics", {})
        for layer_id, layer_metrics in metrics.items():
            for metric_name, metric_value in layer_metrics.items():
                if metric_value == 0:
                    priority = 0.3
                    goal = self._make_goal(
                        description=f"Initialize {layer_id}.{metric_name} (currently 0)",
                        priority=priority,
                        value_alignment=["learning", "growth"],
                        suggested_tasks=[f"Build pipeline for {metric_name}", "Add telemetry capture"],
                    )
                    new_goals.append(goal)

        self.goals.extend(new_goals)
        self._generated_count += len(new_goals)
        return new_goals

    def get_active_goals(self, limit: int = 10) -> list[Goal]:
        """Return pending/queued goals sorted by priority descending."""
        active = [g for g in self.goals if g.status in ("pending", "queued")]
        active.sort(key=lambda g: -g.priority)
        return active[:limit]

    def get_stats(self) -> dict:
        return {
            "total_generated": self._generated_count,
            "active": len(self.get_active_goals()),
            "total_goals": len(self.goals),
        }

    def _make_goal(self, description: str, priority: float,
                   source_signal: Optional[str] = None,
                   value_alignment: Optional[list[str]] = None,
                   suggested_tasks: Optional[list[str]] = None) -> Goal:
        self._generated_count += 1
        return Goal(
            id=f"goal-{self._generated_count:04d}",
            description=description,
            priority=priority,
            source_signal=source_signal,
            value_alignment=value_alignment or [],
            suggested_tasks=suggested_tasks or [],
        )
