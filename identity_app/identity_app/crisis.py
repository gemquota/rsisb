"""Crisis System — Multi-severity health monitoring, prediction, and automated recovery.

Extends the original RSIS CrisisMonitor with:
- 4 severity levels (info, warning, critical, catastrophic)
- Proactive crisis prediction based on trend analysis
- Automated recovery plans with step-by-step execution
- Crisis analytics and post-mortem history
- Escalation workflows
"""

import math
import random
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from identity_app.storage import Storage


CRISIS_THRESHOLDS = {
    "L1_min_score": 30,
    "L2_min_score": 20,
    "L3_min_score": 10,
    "L4_min_score": 15,
    "L5_min_score": 15,
    "L6_min_score": 40,
    "max_consecutive_failures": 10,
    "max_success_rate_decline": 0.5,
    "min_success_rate": 5.0,
}

SEVERITY_LEVELS = [
    "none",
    "info",
    "warning",
    "critical",
    "catastrophic",
]

SEVERITY_THRESHOLDS = {
    "info": {"min_violations": 1, "score_drop_threshold": 5},
    "warning": {"min_violations": 2, "score_drop_threshold": 15},
    "critical": {"min_violations": 3, "score_drop_threshold": 30},
    "catastrophic": {"min_violations": 4, "score_drop_threshold": 50},
}


# ── CrisisMonitor ───────────────────────────────────────────────

class CrisisMonitor:
    """Multi-severity health monitoring with proactive detection.

    Detects crisis conditions across multiple dimensions:
    1. Layer scores below minimum thresholds
    2. Success rate decline
    3. Trait instability (sudden trait changes)
    4. Value drift severity
    5. Rapid score volatility
    """

    def __init__(self, self_model, storage: Optional[Storage] = None):
        self.self_model = self_model
        self.storage = storage or Storage()
        self.state = self.storage.load_crisis_state()

    def _save(self):
        """Persist crisis state."""
        self.storage.save_crisis_state(self.state)

    def check_health(self, axiom_system=None, drift_report: Optional[dict] = None) -> dict:
        """Run comprehensive health check across all crisis dimensions.

        Returns a detailed health report with severity assessment.
        """
        report = {
            "healthy": True,
            "severity": "none",
            "crisis_active": self.state.get("active", False),
            "checks": {},
            "violations": [],
            "warnings": [],
            "metrics": {},
        }

        # 1. Layer score checks
        for lid, threshold_key in [
            ("L1", "L1_min_score"), ("L2", "L2_min_score"), ("L3", "L3_min_score"),
            ("L4", "L4_min_score"), ("L5", "L5_min_score"), ("L6", "L6_min_score"),
        ]:
            score = self.self_model.get_layer_score(lid)
            threshold = CRISIS_THRESHOLDS[threshold_key]
            passing = score >= threshold
            report["checks"][lid] = {
                "type": "layer_score",
                "score": score,
                "threshold": threshold,
                "passing": passing,
                "gap": max(0, threshold - score),
            }
            if not passing:
                report["violations"].append(
                    f"{lid} score {score:.1f} below threshold {threshold}"
                )

        # 2. Success rate check
        if self.self_model.total_attempts > 0:
            success_rate = self.self_model.get_success_rate()
            report["checks"]["success_rate"] = {
                "type": "success_rate",
                "rate": success_rate,
                "threshold": CRISIS_THRESHOLDS["min_success_rate"],
                "passing": success_rate >= CRISIS_THRESHOLDS["min_success_rate"],
            }
            if success_rate < CRISIS_THRESHOLDS["min_success_rate"]:
                report["violations"].append(
                    f"Success rate {success_rate:.1f}% below threshold {CRISIS_THRESHOLDS['min_success_rate']}%"
                )

        # 3. Trait stability check
        if hasattr(self.self_model, 'traits'):
            for name, trait in self.self_model.traits.items():
                if len(trait.history) >= 2:
                    recent = trait.history[-3:]
                    if len(recent) >= 2:
                        changes = [abs(recent[i][1] - recent[i - 1][1]) for i in range(1, len(recent))]
                        avg_volatility = sum(changes) / len(changes)
                        if avg_volatility > 15:
                            report["warnings"].append(
                                f"Trait '{name}' volatile (avg change {avg_volatility:.1f})"
                            )

        # 4. Drift check (if report provided)
        if drift_report and drift_report.get("overall_drifting"):
            report["warnings"].append("Active value/layer drift detected")

        # 5. Score volatility
        temporal = self.self_model.temporal_history
        if len(temporal) >= 3:
            for lid in self.self_model.layer_scores:
                scores_3 = [h["scores"].get(lid, 0) for h in temporal[-3:] if lid in h.get("scores", {})]
                if len(scores_3) >= 3:
                    volatility = max(scores_3) - min(scores_3)
                    if volatility > 20:
                        report["warnings"].append(
                            f"{lid} high volatility ({volatility:.1f}pts over last 3 records)"
                        )

        # Assess severity
        report["severity"] = self._assess_severity(report)
        report["healthy"] = report["severity"] == "none" and len(report["violations"]) == 0

        # Track metrics
        report["metrics"] = {
            "violation_count": len(report["violations"]),
            "warning_count": len(report["warnings"]),
            "total_checks": len(report["checks"]),
            "pass_rate": round(
                sum(1 for c in report["checks"].values() if c.get("passing", False))
                / max(len(report["checks"]), 1) * 100, 1
            ),
        }

        # Trigger crisis if needed
        if report["severity"] in ("critical", "catastrophic") and not self.state.get("active"):
            self._trigger_crisis(report)

        return report

    def _assess_severity(self, report: dict) -> str:
        """Determine severity level based on violations and warnings."""
        violation_count = len(report["violations"])
        warning_count = len(report["warnings"])

        # Count how many layers are significantly below threshold
        severe_drops = sum(
            1 for c in report["checks"].values()
            if isinstance(c, dict) and c.get("type") == "layer_score"
            and not c.get("passing", True) and c.get("gap", 0) > 20
        )

        if severe_drops >= 3 or violation_count >= 5:
            return "catastrophic"
        elif severe_drops >= 1 or violation_count >= 3:
            return "critical"
        elif violation_count >= 1 or warning_count >= 3:
            return "warning"
        elif warning_count >= 1:
            return "info"
        return "none"

    def _trigger_crisis(self, report: dict) -> None:
        """Activate crisis state."""
        self.state["active"] = True
        self.state["severity"] = report["severity"]
        self.state["triggered_at"] = time.time()
        self.state["triggered_by"] = "; ".join(report["violations"][:3])
        self.state["violations_at_trigger"] = report["violations"]
        self.state["warnings_at_trigger"] = report["warnings"]
        self._save()

        # Update self_model
        self.self_model.crisis_count += 1
        self.self_model.last_crisis_at = time.time()
        self.self_model.save()

    def resolve_crisis(self, resolution: str = "", recovery_plan: Optional[dict] = None) -> dict:
        """Resolve the current crisis with an optional recovery plan link."""
        if not self.state.get("active"):
            return {"status": "no_active_crisis"}

        history_entry = {
            "triggered_at": self.state.get("triggered_at", 0),
            "triggered_by": self.state.get("triggered_by", ""),
            "severity": self.state.get("severity", "none"),
            "resolved_at": time.time(),
            "resolution": resolution,
        }
        if recovery_plan:
            history_entry["recovery_plan_id"] = recovery_plan.get("plan_id")

        history = self.state.get("history", [])
        history.append(history_entry)
        self.state = {
            "active": False,
            "severity": "none",
            "triggered_at": 0.0,
            "triggered_by": "",
            "resolved_at": time.time(),
            "history": history,
            "prediction": self.state.get("prediction", {}),
        }
        self._save()
        return {"status": "resolved", "resolution": resolution, "entry": history_entry}

    def get_status(self) -> dict:
        """Get current crisis status."""
        return dict(self.state)

    def get_crisis_history(self, limit: int = 20) -> list[dict]:
        """Get crisis history entries."""
        return list(reversed(self.state.get("history", [])))[:limit]

    def get_health_summary(self) -> str:
        """Get a one-line health summary."""
        state = self.state
        if state.get("active"):
            return f"🚨 CRISIS: {state.get('severity', 'unknown').upper()} - {state.get('triggered_by', '')[:60]}"
        recent = state.get("history", [])
        if recent:
            last = recent[-1]
            return f"✅ Healthy (last crisis: {last.get('severity', 'unknown')} resolved {time.time() - last.get('resolved_at', 0):.0f}s ago)"
        return "✅ Healthy (no crisis history)"


# ── CrisisPredictor ─────────────────────────────────────────────

class CrisisPredictor:
    """Proactively predicts crisis conditions using trend analysis.

    Analyzes historical trends in layer scores, traits, and success
    rates to predict potential crisis events before they occur.
    """

    def __init__(self, self_model):
        self.self_model = self_model

    def predict(self, horizon_steps: int = 5) -> dict:
        """Predict crisis risk over a given horizon.

        Analyzes current trends and projects forward to assess
        the likelihood of hitting crisis thresholds.
        """
        predictions = {}
        overall_risk = 0.0
        weights = {}

        # Layer score predictions
        for lid, threshold_key in [
            ("L1", "L1_min_score"), ("L2", "L2_min_score"), ("L3", "L3_min_score"),
            ("L4", "L4_min_score"), ("L5", "L5_min_score"), ("L6", "L6_min_score"),
        ]:
            threshold = CRISIS_THRESHOLDS[threshold_key]
            current = self.self_model.get_layer_score(lid)
            trend = self.self_model.get_score_trend(lid)

            projected = current + (trend * horizon_steps)
            risk = max(0, (threshold - projected) / max(threshold, 1))
            risk = min(1.0, risk)

            days_to_threshold = "N/A"
            if trend < 0:
                days_to_threshold = abs((current - threshold) / max(abs(trend), 0.1))
                days_to_threshold = round(days_to_threshold, 1)

            predictions[lid] = {
                "current": current,
                "trend": trend,
                "projected": max(0, min(100, projected)),
                "threshold": threshold,
                "risk": round(risk, 2),
                "days_to_threshold": days_to_threshold,
            }
            weights[lid] = risk

        # Overall risk (weighted average)
        if weights:
            overall_risk = sum(weights.values()) / len(weights)

        # Risk level classification
        if overall_risk >= 0.7:
            risk_level = "high"
        elif overall_risk >= 0.4:
            risk_level = "medium"
        elif overall_risk >= 0.15:
            risk_level = "low"
        else:
            risk_level = "minimal"

        high_risk_layers = [lid for lid, p in predictions.items() if p["risk"] >= 0.5]

        return {
            "timestamp": time.time(),
            "overall_risk": round(overall_risk, 3),
            "risk_level": risk_level,
            "horizon_steps": horizon_steps,
            "high_risk_layers": high_risk_layers,
            "predictions": predictions,
            "recommendation": self._recommendation(risk_level, high_risk_layers),
        }

    def _recommendation(self, risk_level: str, high_risk_layers: list[str]) -> str:
        """Generate a recommendation based on prediction."""
        if risk_level == "high" and high_risk_layers:
            return (f"PROACTIVE ALERT: {len(high_risk_layers)} layer(s) at high crisis risk "
                    f"({', '.join(high_risk_layers)}). Take snapshot and run health check immediately.")
        if risk_level == "medium":
            return "CAUTION: Moderate crisis risk detected. Consider reviewing declining layers."
        if risk_level == "low":
            return "MONITOR: Low risk detected. Continue normal operations with awareness."
        return "CLEAR: No significant crisis risk predicted."


# ── RecoveryPlanner ─────────────────────────────────────────────

class RecoveryPlanner:
    """Generates and executes automated recovery plans for crisis events.

    Provides:
    - Plan templates for common crisis types
    - Step-by-step recovery execution
    - Progress tracking
    - Post-recovery analysis
    """

    RECOVERY_TEMPLATES = {
        "layer_score_crisis": {
            "name": "Layer Score Recovery",
            "description": "Restore layer scores above minimum thresholds",
            "steps": [
                {"id": "1", "action": "take_snapshot", "description": "Capture pre-recovery state", "optional": False},
                {"id": "2", "action": "identify_declining_metrics", "description": "Identify which metrics caused the drop", "optional": False},
                {"id": "3", "action": "prioritize_recovery", "description": "Prioritize metrics with largest gap to threshold", "optional": False},
                {"id": "4", "action": "apply_corrections", "description": "Apply targeted corrections to each metric", "optional": False},
                {"id": "5", "action": "verify_scores", "description": "Re-check layer scores after corrections", "optional": False},
                {"id": "6", "action": "take_snapshot", "description": "Capture post-recovery state", "optional": False},
            ],
        },
        "success_rate_crisis": {
            "name": "Success Rate Recovery",
            "description": "Improve application success rate above minimum",
            "steps": [
                {"id": "1", "action": "take_snapshot", "description": "Capture pre-recovery state", "optional": False},
                {"id": "2", "action": "analyze_failures", "description": "Analyze recent failure patterns", "optional": False},
                {"id": "3", "action": "reduce_attempts_temporarily", "description": "Temporarily reduce attempt rate to focus on quality", "optional": True},
                {"id": "4", "action": "fix_common_failures", "description": "Address the most common failure modes", "optional": False},
                {"id": "5", "action": "verify_success_rate", "description": "Verify success rate improvement", "optional": False},
                {"id": "6", "action": "take_snapshot", "description": "Capture post-recovery state", "optional": False},
            ],
        },
        "general_crisis": {
            "name": "General Crisis Recovery",
            "description": "Comprehensive recovery from any crisis condition",
            "steps": [
                {"id": "1", "action": "halt_non_critical", "description": "Halt non-critical operations", "optional": False},
                {"id": "2", "action": "take_snapshot", "description": "Capture pre-recovery state", "optional": False},
                {"id": "3", "action": "full_health_check", "description": "Run comprehensive health check", "optional": False},
                {"id": "4", "action": "identify_root_causes", "description": "Identify root causes of crisis", "optional": False},
                {"id": "5", "action": "apply_recovery_actions", "description": "Apply targeted recovery actions", "optional": False},
                {"id": "6", "action": "verify_recovery", "description": "Verify all systems recovered", "optional": False},
                {"id": "7", "action": "take_snapshot", "description": "Capture post-recovery state", "optional": False},
                {"id": "8", "action": "resume_operations", "description": "Resume normal operations", "optional": False},
            ],
        },
    }

    def __init__(self, self_model, storage: Optional[Storage] = None):
        self.self_model = self_model
        self.storage = storage or Storage()
        self.active_plans: dict = {}
        self._load_plans()

    def _load_plans(self):
        """Load active plans from storage."""
        data = self.storage.read_json(self.storage._path("recovery_plans.json"))
        if data:
            self.active_plans = data.get("active_plans", {})

    def _save_plans(self):
        """Save active plans to storage."""
        self.storage.write_json(
            self.storage._path("recovery_plans.json"),
            {"active_plans": self.active_plans}
        )

    def create_plan(self, crisis_type: str = "general_crisis",
                    triggered_by: str = "", snapshot_id: int = 0) -> dict:
        """Create a recovery plan for a given crisis type."""
        template = self.RECOVERY_TEMPLATES.get(crisis_type)
        if not template:
            template = self.RECOVERY_TEMPLATES["general_crisis"]

        plan_id = f"recovery_{int(time.time())}_{random.randint(0, 9999):04d}"
        plan = {
            "plan_id": plan_id,
            "name": template["name"],
            "description": template["description"],
            "crisis_type": crisis_type,
            "triggered_by": triggered_by,
            "snapshot_id": snapshot_id,
            "created_at": time.time(),
            "status": "created",  # created, in_progress, completed, failed
            "current_step_index": 0,
            "steps": [
                {**step, "status": "pending"}
                for step in template["steps"]
            ],
            "completed_at": None,
            "notes": "",
        }
        self.active_plans[plan_id] = plan
        self._save_plans()
        return plan

    def get_plan(self, plan_id: str) -> Optional[dict]:
        """Get a recovery plan by ID."""
        return self.active_plans.get(plan_id)

    def list_plans(self, status: Optional[str] = None) -> list[dict]:
        """List all recovery plans, optionally filtered by status."""
        plans = list(self.active_plans.values())
        if status:
            plans = [p for p in plans if p["status"] == status]
        return sorted(plans, key=lambda p: p.get("created_at", 0), reverse=True)

    def start_plan(self, plan_id: str) -> dict:
        """Start executing a recovery plan."""
        plan = self.active_plans.get(plan_id)
        if not plan:
            return {"error": f"Plan {plan_id} not found"}
        plan["status"] = "in_progress"
        plan["current_step_index"] = 0
        if plan["steps"]:
            plan["steps"][0]["status"] = "in_progress"
        self._save_plans()
        return plan

    def advance_plan(self, plan_id: str, step_result: str = "completed",
                     notes: str = "") -> dict:
        """Advance to the next step in a recovery plan."""
        plan = self.active_plans.get(plan_id)
        if not plan:
            return {"error": f"Plan {plan_id} not found"}

        current = plan["current_step_index"]
        if current < len(plan["steps"]):
            plan["steps"][current]["status"] = step_result
            plan["steps"][current]["completed_at"] = time.time()
            plan["steps"][current]["notes"] = notes

        next_step = current + 1
        if next_step >= len(plan["steps"]):
            plan["status"] = "completed"
            plan["completed_at"] = time.time()
        else:
            plan["current_step_index"] = next_step
            plan["steps"][next_step]["status"] = "in_progress"

        self._save_plans()
        return plan

    def fail_plan(self, plan_id: str, reason: str = "") -> dict:
        """Mark a recovery plan as failed."""
        plan = self.active_plans.get(plan_id)
        if not plan:
            return {"error": f"Plan {plan_id} not found"}
        plan["status"] = "failed"
        plan["notes"] = reason
        plan["completed_at"] = time.time()
        self._save_plans()
        return plan

    def get_progress(self, plan_id: str) -> dict:
        """Get the progress of a recovery plan as a percentage."""
        plan = self.active_plans.get(plan_id)
        if not plan or not plan["steps"]:
            return {"plan_id": plan_id, "progress": 0.0, "status": "unknown"}

        completed = sum(1 for s in plan["steps"] if s["status"] == "completed")
        progress = (completed / len(plan["steps"])) * 100.0

        return {
            "plan_id": plan_id,
            "status": plan["status"],
            "progress": round(progress, 1),
            "completed_steps": completed,
            "total_steps": len(plan["steps"]),
            "current_step": plan["steps"][plan["current_step_index"]] if plan["current_step_index"] < len(plan["steps"]) else None,
        }

    def auto_recover(self, health_report: dict, snapshot_id: int = 0) -> Optional[dict]:
        """Automatically create and start a recovery plan based on health report.

        Analyzes the health check violations and selects the best
        recovery template automatically.
        """
        if health_report.get("healthy", True):
            return None

        # Determine crisis type from violations
        violations = health_report.get("violations", [])
        crisis_type = "general_crisis"
        layer_violations = [v for v in violations if "score" in v]
        success_rate_violations = [v for v in violations if "Success" in v]

        if layer_violations and not success_rate_violations:
            crisis_type = "layer_score_crisis"
        elif success_rate_violations and not layer_violations:
            crisis_type = "success_rate_crisis"

        triggered_by = "; ".join(violations[:3])
        plan = self.create_plan(crisis_type, triggered_by, snapshot_id)
        plan = self.start_plan(plan["plan_id"])
        return plan
