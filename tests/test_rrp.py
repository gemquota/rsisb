"""Tests for the RRP Protocol Engine."""

import pytest
import os
from rrp.state_machine import (
    RRPState, AmbiguityVector, DecisionType,
    UseCase, ExecutionMode, TopicCoverage,
)
from rrp.protocol import RRPEngine
from rrp.compact import encode_compact, decode_compact
from rrp.persistence import RRPPersistence


class TestRRPState:
    def test_init(self):
        s = RRPState()
        assert s.status == "initialized"
        assert s.rrp_version == "2.1"
        assert s.ambiguity.average() == 0.5

    def test_set_ambiguity(self):
        s = RRPState()
        s.set_ambiguity(requirements=0.2, data_model=0.3)
        assert s.ambiguity.requirements == 0.2
        assert s.ambiguity.data_model == 0.3
        assert s.ambiguity.edge_case == 0.5
        assert len(s.ambiguity_history) == 1

    def test_add_constraint(self):
        s = RRPState()
        s.add_constraint("language", "Python")
        assert len(s.constraints) == 1
        # Values are stored as-is in the state machine (lowercasing happens in protocol layer)
        assert s.constraints[0].key == "language"
        assert s.constraints[0].value == "Python"

    def test_contradiction_detection(self):
        s = RRPState()
        s.add_constraint("database", "PostgreSQL")
        s.add_constraint("database", "MongoDB")
        assert len(s.contradictions) == 1
        assert "PostgreSQL" in s.contradictions[0].constraint_a

    def test_add_decision(self):
        s = RRPState()
        s.current_round = 2
        s.add_decision(DecisionType.COMMITMENT, "Use Python", "Team preference", 0.9)
        assert len(s.decisions) == 1
        assert s.decisions[0].round == 2

    def test_early_termination_below_threshold(self):
        s = RRPState()
        s.current_round = 5
        s.session.max_rounds = 5
        s.set_ambiguity(requirements=0.04, data_model=0.03, edge_case=0.02, determinism=0.01)
        assert s.check_early_termination() is True
        assert s.status == "early_term"

    def test_early_termination_topic_coverage(self):
        s = RRPState()
        s.current_round = 5
        s.session.max_rounds = 5
        for t in TopicCoverage.TOPICS:
            s.telemetry.topic_coverage.set_topic(t)
        s.set_ambiguity(requirements=0.1, data_model=0.1, edge_case=0.1, determinism=0.1)
        assert s.check_early_termination() is True

    def test_no_early_termination_too_few_rounds(self):
        s = RRPState()
        s.current_round = 2
        s.session.max_rounds = 10
        s.set_ambiguity(requirements=0.01, data_model=0.01, edge_case=0.01, determinism=0.01)
        assert s.check_early_termination() is False

    def test_checkpoint_rollback(self):
        s = RRPState()
        s.add_constraint("key1", "val1")
        s.checkpoint_save()
        s.add_constraint("key2", "val2")
        assert len(s.constraints) == 2
        s.checkpoint_rollback()
        assert len(s.constraints) == 1


class TestRRPEngine:
    def test_init_session(self):
        engine = RRPEngine().init_session("test", use_case=3, mode=2, max_rounds=8, depth=3)
        assert engine.state.session.session_id == "test"
        assert engine.state.session.use_case == UseCase.CONVERGENCE
        assert engine.state.session.execution_mode == ExecutionMode.BATCH
        assert engine.state.session.max_rounds == 8

    def test_process_user_input(self):
        engine = RRPEngine().init_session("test")
        result = engine.process_user_input("The API architecture must use RESTful design for endpoints")
        assert result["round"] == 1
        assert len(result["extracted_constraints"]) >= 1
        assert "ARCH" in result["topics_covered"]

    def test_apply_ambiguity_json(self):
        engine = RRPEngine().init_session("test")
        engine.apply_semantic_ambiguity_json(requirements=0.1, data_model=0.2)
        assert engine.state.ambiguity.requirements == 0.1
        assert engine.state.ambiguity.data_model == 0.2


class TestCompact:
    def test_encode_decode_roundtrip(self):
        engine = RRPEngine().init_session("test", use_case=5, mode=1, max_rounds=8, depth=2)
        engine.process_user_input("We need a data schema for users")
        engine.apply_semantic_ambiguity_json(requirements=0.2, data_model=0.3)
        compact = encode_compact(engine.state)
        decoded = decode_compact(compact)
        assert decoded.get("use_case") == 5
        assert decoded.get("status") == "active"
        assert decoded.get("ambiguity_avg", 1.0) < 0.5

    def test_compact_length(self):
        engine = RRPEngine().init_session("test", use_case=6, mode=3, max_rounds=10, depth=3)
        for _ in range(3):
            engine.process_user_input("Testing architecture security data performance scalability deployment UX")
        engine.apply_semantic_ambiguity_json(requirements=0.1, data_model=0.2, edge_case=0.15, determinism=0.05)
        compact = encode_compact(engine.state)
        assert len(compact) < 130, f"Compact too long: {len(compact)} chars"


class TestPersistence:
    def test_save_load_roundtrip(self):
        engine = RRPEngine().init_session("persist_test", use_case=2, mode=1, max_rounds=3)
        engine.process_user_input("Test input for persistence")
        engine.add_decision("commitment", "Test decision")
        persist = RRPPersistence()
        persist.save(engine)
        loaded = persist.load("persist_test")
        assert loaded is not None
        assert loaded.state.current_round == 1
        assert len(loaded.state.decisions) == 1
        sf = persist.session_path("persist_test")
        if sf.exists():
            sf.unlink()

    def test_list_sessions(self):
        persist = RRPPersistence()
        engine = RRPEngine().init_session("list_test")
        persist.save(engine)
        sessions = persist.list_sessions()
        ids = [s["session_id"] for s in sessions]
        assert "list_test" in ids
        sf = persist.session_path("list_test")
        if sf.exists():
            sf.unlink()
