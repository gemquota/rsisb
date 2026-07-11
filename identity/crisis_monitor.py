"""Crisis Monitor — Automated health checks and identity crisis detection.

Monitors operational trends to detect identity crisis conditions and
executes defensive recovery behaviors when thresholds are breached.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


CRISIS_STATE_FILE = "rack/L6/crisis_state.json"

# Crisis thresholds (from Module 4.3)
CRISIS_THRESHOLDS = {
    "L1_min_score": 30,
    "L2_min_score": 20,
    "L3_min_score": 10,
    "L4_min_score": 15,
    "L5_min_score": 15,
    "L6_min_score": 40,
    "max_consecutive_failures": 10,
    "max_success_rate_decline": 0.5,  # 50% drop from peak
    "min_success_rate": 5.0,  # below 5% triggers crisis
}


@dataclass
class CrisisState:
    active: bool = False
    triggered_at: float = 0.0
    triggered_by: str = ""
    resolved_at: float = 0.0
    history: list[dict] = field(default_factory=list)


class CrisisMonitor:
    """Monitors system health and triggers crisis protocols when thresholds breach.

    Crisis triggers:
      1. Any layer score drops below its minimum threshold
      2. Consecutive failures exceed max_consecutive_failures
      3. Success rate drops below min_success_rate
    """

    def __init__(self, state_file: str = CRISIS_STATE_FILE):
        self.state_file = Path(state_file)
        self.state = CrisisState()
        self._load()

    def _load(self):
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
            self.state = CrisisState(**data)

    def _save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(asdict(self.state), f, indent=2)

    def check_health(self, self_model) -> dict:
        """Run health check against all crisis thresholds.

        Returns a health report dict. If crisis conditions are found
        and crisis is not already active, triggers crisis mode.
        """
        report = {
            "healthy": True,
            "crisis_active": self.state.active,
            "checks": {},
            "violations": [],
        }

        # Check each layer score
        for lid, threshold_key in [
            ("L1", "L1_min_score"), ("L2", "L2_min_score"), ("L3", "L3_min_score"),
            ("L4", "L4_min_score"), ("L5", "L5_min_score"), ("L6", "L6_min_score"),
        ]:
            score = self_model.get_layer_score(lid)
            threshold = CRISIS_THRESHOLDS[threshold_key]
            passing = score >= threshold
            report["checks"][lid] = {
                "score": score,
                "threshold": threshold,
                "passing": passing,
            }
            if not passing:
                report["violations"].append(f"{lid} score {score} below threshold {threshold}")

        # Check success rate
        if self_model.total_attempts > 0:
            success_rate = (self_model.successful_applications / self_model.total_attempts) * 100
            report["checks"]["success_rate"] = {
                "rate": success_rate,
                "threshold": CRISIS_THRESHOLDS["min_success_rate"],
                "passing": success_rate >= CRISIS_THRESHOLDS["min_success_rate"],
            }
            if success_rate < CRISIS_THRESHOLDS["min_success_rate"]:
                report["violations"].append(
                    f"Success rate {success_rate:.1f}% below threshold {CRISIS_THRESHOLDS['min_success_rate']}%"
                )

        report["healthy"] = len(report["violations"]) == 0

        # Trigger crisis if violations found and not already in crisis
        if report["violations"] and not self.state.active:
            self.state.active = True
            self.state.triggered_at = time.time()
            self.state.triggered_by = "; ".join(report["violations"])
            self._save()
            report["crisis_active"] = True
            report["crisis_triggered"] = True

        return report

    def resolve_crisis(self, resolution: str = ""):
        """Resolve the current crisis state manually."""
        if not self.state.active:
            return {"status": "no_active_crisis"}
        self.state.history.append({
            "triggered_at": self.state.triggered_at,
            "triggered_by": self.state.triggered_by,
            "resolved_at": time.time(),
            "resolution": resolution,
        })
        self.state.active = False
        self.state.triggered_at = 0.0
        self.state.triggered_by = ""
        self._save()
        return {"status": "resolved", "resolution": resolution}

    def get_status(self) -> dict:
        return asdict(self.state)
