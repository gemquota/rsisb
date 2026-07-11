"""Value Reinforcement Tracker — Tracks value axiom alignment and reinforcement.

Each time a goal is achieved that aligns with a core value axiom, that
axiom's reinforced_count increments, increasing its influence over
priority calculations.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


VALUE_AXIOMS = [
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


@dataclass
class AxiomState:
    reinforced_count: int = 0
    last_reinforced: float = 0.0
    total_applications: int = 0


class ValueReinforcementTracker:
    """Tracks reinforcement counts and weights for the 9 core value axioms.

    Each reinforcement increases the axiom's weight in priority calculations.
    The tracker persists state to the self_model's value_axioms section.
    """

    def __init__(self, self_model_path: str = "rack/shared/self_model.json"):
        self.path = self_model_path
        self.axioms: dict[str, AxiomState] = {a: AxiomState() for a in VALUE_AXIOMS}
        self._load()

    def _load(self):
        p = Path(self.path)
        if not p.exists():
            return
        with open(p) as f:
            data = json.load(f)
        va = data.get("value_axioms", {})
        for axiom_name, state in va.items():
            if axiom_name in self.axioms:
                self.axioms[axiom_name] = AxiomState(
                    reinforced_count=state.get("reinforced_count", 0),
                    last_reinforced=state.get("last_reinforced", 0.0),
                    total_applications=state.get("total_applications", 0),
                )

    def _save(self):
        """Persist axiom states to the self_model file."""
        p = Path(self.path)
        if not p.exists():
            return
        with open(p) as f:
            data = json.load(f)
        data["value_axioms"] = {
            name: asdict(state) for name, state in self.axioms.items()
        }
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def reinforce(self, axiom_name: str, count: int = 1) -> AxiomState:
        """Reinforce a value axiom by incrementing its count."""
        if axiom_name not in self.axioms:
            raise ValueError(f"Unknown axiom: {axiom_name}. Valid: {VALUE_AXIOMS}")
        state = self.axioms[axiom_name]
        state.reinforced_count += count
        state.total_applications += count
        state.last_reinforced = time.time()
        self._save()
        return state

    def get_weight(self, axiom_name: str) -> float:
        """Get the current weight of an axiom (base 1.0 + 0.1 per reinforcement)."""
        state = self.axioms.get(axiom_name)
        if not state:
            return 1.0
        return 1.0 + (state.reinforced_count * 0.1)

    def get_alignment_score(self, value_list: list[str]) -> float:
        """Calculate combined alignment score for a list of value axioms."""
        return sum(self.get_weight(v) for v in value_list)

    def to_dict(self) -> dict:
        return {name: asdict(state) for name, state in self.axioms.items()}
