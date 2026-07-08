"""Tests for the evaluator module."""

import json
import tempfile
import os

import pytest

from evaluator.evaluator import (
    EvaluatorClient,
    GoalAnalysis,
    ConstraintExtraction,
    AmbiguityAssessment,
    Evaluation,
    EvaluationReport,
    load_report,
)


class TestEvaluatorClient:
    def test_default_mode_is_local(self):
        client = EvaluatorClient()
        assert client.mode == "local"

    def test_evaluate_returns_report(self):
        client = EvaluatorClient()
        report = client.evaluate(
            target="test_target.py",
            pulse_id=1,
            goal_analysis=GoalAnalysis(reasoning="test", conclusion="ok"),
            constraint_extraction=ConstraintExtraction(reasoning="test", constraints={"x": "LOCKED"}),
            ambiguity_assessment=AmbiguityAssessment(reasoning="test", ambiguity={"y": 0.0}),
            evaluation=Evaluation(reasoning="test", decision="PASS", confidence=0.95, suggestion="go"),
        )
        assert isinstance(report, EvaluationReport)
        assert report.phase_evaluation.decision == "PASS"

    def test_raises_on_invalid_decision(self):
        client = EvaluatorClient()
        with pytest.raises(ValueError, match="Invalid decision"):
            client.evaluate(
                target="t.py",
                evaluation=Evaluation(reasoning="x", decision="INVALID", confidence=0.5, suggestion=""),
            )

    def test_raises_on_non_local_mode(self):
        client = EvaluatorClient(mode="remote")
        with pytest.raises(RuntimeError, match="only supports mode='local'"):
            client.evaluate(target="t.py")

    def test_default_fallback_phases(self):
        client = EvaluatorClient()
        report = client.evaluate(target="t.py")
        assert report.phase_goal_analysis.conclusion == "Skipped."
        assert report.phase_evaluation.decision == "HOLD"
        assert report.phase_evaluation.confidence == 0.0

    def test_report_to_dict(self):
        client = EvaluatorClient()
        report = client.evaluate(
            target="t.py",
            pulse_id=5,
            evaluation=Evaluation(reasoning="all good", decision="PASS", confidence=1.0, suggestion=""),
        )
        d = report.to_dict()
        assert d["target"] == "t.py"
        assert d["pulse_id"] == 5
        assert d["phases"]["evaluation"]["decision"] == "PASS"

    def test_report_to_json_round_trip(self):
        client = EvaluatorClient()
        report = client.evaluate(
            target="t.py",
            pulse_id=3,
            evaluation=Evaluation(reasoning="ok", decision="PASS", confidence=0.9, suggestion="proceed"),
        )
        tmp = os.path.join(tempfile.mkdtemp(), "report.json")
        with open(tmp, "w") as f:
            f.write(report.to_json())
        loaded = load_report(tmp)
        assert loaded.target == "t.py"
        assert loaded.pulse_id == 3
        assert loaded.phase_evaluation.decision == "PASS"

    def test_timestamp_is_set(self):
        client = EvaluatorClient()
        report = client.evaluate(target="t.py")
        assert report.timestamp != ""
        assert "T" in report.timestamp


class TestGoalAnalysis:
    def test_dataclass(self):
        ga = GoalAnalysis(reasoning="check", conclusion="done")
        assert ga.reasoning == "check"
        assert ga.conclusion == "done"


class TestConstraintExtraction:
    def test_dataclass(self):
        ce = ConstraintExtraction(reasoning="check", constraints={"a": "LOCKED"})
        assert ce.constraints["a"] == "LOCKED"


class TestAmbiguityAssessment:
    def test_dataclass(self):
        aa = AmbiguityAssessment(reasoning="check", ambiguity={"b": 0.5})
        assert aa.ambiguity["b"] == 0.5


class TestEvaluation:
    def test_valid_decisions(self):
        for d in ("PASS", "DISMISS", "HOLD"):
            e = Evaluation(reasoning="x", decision=d, confidence=0.5, suggestion="")
            assert e.decision == d


class TestEvaluationReport:
    def test_to_dict_structure(self):
        report = EvaluationReport(
            target="t.py",
            timestamp="2026-01-01T00:00:00Z",
            pulse_id=1,
            phase_goal_analysis=GoalAnalysis(reasoning="r", conclusion="c"),
            phase_constraint_extraction=ConstraintExtraction(reasoning="r", constraints={}),
            phase_ambiguity_assessment=AmbiguityAssessment(reasoning="r", ambiguity={}),
            phase_evaluation=Evaluation(reasoning="r", decision="PASS", confidence=1.0, suggestion=""),
        )
        d = report.to_dict()
        assert "phases" in d
        assert "goal_analysis" in d["phases"]
        assert "evaluation" in d["phases"]
