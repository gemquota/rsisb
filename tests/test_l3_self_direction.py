"""Tests for the L3 Self-Direction Loop."""

import tempfile
import os
import time

import pytest

from l3_self_direction.signal_watcher import SignalWatcher, Signal
from l3_self_direction.goal_generator import GoalGenerator, Goal
from l3_self_direction.queue_manager import QueueManager


class TestSignalWatcher:
    def test_initial_poll_detects_files(self):
        sw = SignalWatcher(watch_paths=["."], poll_interval=0.0)
        signals = sw.poll()
        assert len(signals) > 0
        assert sw.get_signal_count() == len(signals)

    def test_poll_interval_respects_minimum(self):
        sw = SignalWatcher(watch_paths=["."], poll_interval=3600.0)
        signals = sw.poll()  # First poll runs regardless
        signals2 = sw.poll()  # Second poll should be skipped
        assert len(signals2) == 0

    def test_clear_signals(self):
        sw = SignalWatcher(watch_paths=["."], poll_interval=0.0)
        sw.poll()
        assert sw.get_signal_count() > 0
        sw.clear_signals()
        assert sw.get_signal_count() == 0

    def test_get_recent_signals(self):
        sw = SignalWatcher(watch_paths=["."], poll_interval=0.0)
        sw.poll()
        recent = sw.get_recent_signals(5)
        assert len(recent) <= 5


class TestGoalGenerator:
    def test_process_file_created_signal(self):
        gg = GoalGenerator()
        signal = Signal(signal_type="file_created", source="/test/new_module.py", timestamp=time.time())
        goal = gg.process_signal(signal)
        assert goal is not None
        assert "new_module.py" in goal.description
        assert goal.priority == 0.4

    def test_process_md_signal(self):
        gg = GoalGenerator()
        signal = Signal(signal_type="file_created", source="/test/docs.md", timestamp=time.time())
        goal = gg.process_signal(signal)
        assert goal is not None
        assert goal.priority == 0.2

    def test_crisis_state_generates_top_goal(self):
        gg = GoalGenerator()
        state = {"crisis_active": True, "layer_scores": {}, "metrics": {}}
        goals = gg.generate_from_state(state)
        assert any("crisis" in g.description.lower() for g in goals)
        crisis_goal = [g for g in goals if "crisis" in g.description.lower()][0]
        assert crisis_goal.priority >= 0.9

    def test_low_layer_score_generates_goal(self):
        gg = GoalGenerator()
        state = {"crisis_active": False, "layer_scores": {"L3": 9.8}, "metrics": {}}
        goals = gg.generate_from_state(state)
        assert any("L3" in g.description for g in goals)
        l3_goal = [g for g in goals if "L3" in g.description][0]
        assert l3_goal.priority > 0.5


class TestQueueManager:
    def test_enqueue_orders_by_priority(self):
        qm = QueueManager(max_size=10)
        g1 = Goal(id="g1", description="low", priority=0.2)
        g2 = Goal(id="g2", description="high", priority=0.9)
        g3 = Goal(id="g3", description="mid", priority=0.5)
        qm.enqueue(g1)
        qm.enqueue(g2)
        qm.enqueue(g3)
        assert qm.next_goal().id == "g2"
        assert qm.next_goal().id == "g3"
        assert qm.next_goal().id == "g1"

    def test_max_size_eviction(self):
        qm = QueueManager(max_size=2)
        for i in range(4):
            g = Goal(id=f"g{i}", description=f"Goal {i}", priority=i * 0.2)
            evicted = qm.enqueue(g)
        assert qm.get_queue_state()["size"] == 2

    def test_empty_queue_returns_none(self):
        qm = QueueManager()
        assert qm.next_goal() is None
