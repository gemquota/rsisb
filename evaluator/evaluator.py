"""Evaluator module — 4-phase reasoning report engine.

This module implements the EvaluatorClient used during every L2 execution
cycle. Because the system operates in mode="local", the operating agent
manually produces evaluation reports by inspecting context, verifying
constraints, and rendering structured 4-phase judgments.

Phase sequence:
  1. goal_analysis       — Examine target functions, adjacent modules, structural intent
  2. constraint_extraction — Map explicit RRP rule matches, required invariants
  3. ambiguity_assessment — Isolate unmapped behaviors, structural gaps, missing inputs
  4. evaluation           — Final synthesis against test expectations and architectural principles
"""

import json
import time
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class GoalAnalysis:
    reasoning: str
    conclusion: str


@dataclass
class ConstraintExtraction:
    reasoning: str
    constraints: dict


@dataclass
class AmbiguityAssessment:
    reasoning: str
    ambiguity: dict


@dataclass
class Evaluation:
    reasoning: str
    decision: str  # PASS | DISMISS | HOLD
    confidence: float
    suggestion: str


@dataclass
class EvaluationReport:
    phase_goal_analysis: GoalAnalysis
    phase_constraint_extraction: ConstraintExtraction
    phase_ambiguity_assessment: AmbiguityAssessment
    phase_evaluation: Evaluation
    target: str = ""
    timestamp: str = ""
    pulse_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "timestamp": self.timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pulse_id": self.pulse_id,
            "phases": {
                "goal_analysis": asdict(self.phase_goal_analysis),
                "constraint_extraction": asdict(self.phase_constraint_extraction),
                "ambiguity_assessment": asdict(self.phase_ambiguity_assessment),
                "evaluation": asdict(self.phase_evaluation),
            },
        }

    def to_json(self, indent=2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class EvaluatorClient:
    """Manual oracle evaluator operating in mode='local'.

    The evaluate() method expects structured phase inputs from the operating
    agent. It validates the phase schema and returns a formatted report.
    """

    VALID_DECISIONS = {"PASS", "DISMISS", "HOLD"}

    def __init__(self, mode: str = "local"):
        self.mode = mode

    def evaluate(
        self,
        target: str,
        pulse_id: Optional[int] = None,
        goal_analysis: Optional[GoalAnalysis] = None,
        constraint_extraction: Optional[ConstraintExtraction] = None,
        ambiguity_assessment: Optional[AmbiguityAssessment] = None,
        evaluation: Optional[Evaluation] = None,
    ) -> EvaluationReport:
        if self.mode != "local":
            raise RuntimeError(f"EvaluatorClient only supports mode='local', got '{self.mode}'")

        if evaluation is not None and evaluation.decision not in self.VALID_DECISIONS:
            raise ValueError(
                f"Invalid decision '{evaluation.decision}'. Must be one of {self.VALID_DECISIONS}"
            )

        report = EvaluationReport(
            target=target,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            pulse_id=pulse_id,
            phase_goal_analysis=goal_analysis or GoalAnalysis(
                reasoning="No goal analysis provided.",
                conclusion="Skipped.",
            ),
            phase_constraint_extraction=constraint_extraction or ConstraintExtraction(
                reasoning="No constraint extraction provided.",
                constraints={},
            ),
            phase_ambiguity_assessment=ambiguity_assessment or AmbiguityAssessment(
                reasoning="No ambiguity assessment provided.",
                ambiguity={},
            ),
            phase_evaluation=evaluation or Evaluation(
                reasoning="No evaluation provided.",
                decision="HOLD",
                confidence=0.0,
                suggestion="Manual review required.",
            ),
        )
        return report


def load_report(path: str) -> EvaluationReport:
    """Load an EvaluationReport from a JSON file."""
    with open(path) as f:
        data = json.load(f)
    phases = data["phases"]
    return EvaluationReport(
        target=data.get("target", ""),
        timestamp=data.get("timestamp", ""),
        pulse_id=data.get("pulse_id"),
        phase_goal_analysis=GoalAnalysis(**phases["goal_analysis"]),
        phase_constraint_extraction=ConstraintExtraction(**phases["constraint_extraction"]),
        phase_ambiguity_assessment=AmbiguityAssessment(**phases["ambiguity_assessment"]),
        phase_evaluation=Evaluation(**phases["evaluation"]),
    )
