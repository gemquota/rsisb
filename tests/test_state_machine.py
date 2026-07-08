"""Tests for the lifecycle state machine."""

import tempfile
import os

import pytest

from state_machine import StateMachine, Task, TaskState, EvictionPolicy


@pytest.fixture
def sm():
    return StateMachine(max_queue_size=5)


def make_task(task_id, rank=1, description="test", value_alignment=None):
    return Task(id=task_id, description=description, rank=rank,
                value_alignment=value_alignment or [])


class TestTaskLifecycle:
    def test_propose_to_complete(self, sm):
        t = make_task("t1", rank=5)
        sm.propose(t)
        assert t.state == TaskState.PROPOSED
        sm.enqueue("t1")
        assert t.state == TaskState.QUEUED
        sm.start("t1")
        assert t.state == TaskState.EXECUTING
        assert t.attempts == 1
        sm.complete("t1", result="done")
        assert t.state == TaskState.COMPLETED

    def test_propose_duplicate_raises(self, sm):
        t = make_task("t1")
        sm.propose(t)
        with pytest.raises(ValueError, match="already exists"):
            sm.propose(t)

    def test_invalid_transition_raises(self, sm):
        t = make_task("t1")
        sm.propose(t)
        with pytest.raises(ValueError, match="state PROPOSED"):
            sm.start("t1")  # must enqueue first


class TestRetryLogic:
    def test_fail_requeues_up_to_max(self, sm):
        t = make_task("t1", rank=10)
        sm.propose(t)
        sm.enqueue("t1")
        sm.start("t1")   # attempt 1
        sm.fail("t1", error="e1")
        assert t.state == TaskState.QUEUED
        assert t.attempts == 1
        sm.start("t1")   # attempt 2
        sm.fail("t1", error="e2")
        assert t.state == TaskState.QUEUED
        assert t.attempts == 2

    def test_fail_archives_after_max_attempts(self, sm):
        t = make_task("t1", rank=10)
        sm.propose(t)
        sm.enqueue("t1")
        for _ in range(3):
            sm.start("t1")
            sm.fail("t1", error="fail")
        assert t.state == TaskState.ARCHIVED
        assert t.attempts == 3

    def test_max_attempts_configurable(self, sm):
        t = Task(id="t1", description="test", rank=10, max_attempts=2)
        sm.propose(t)
        sm.enqueue("t1")
        sm.start("t1"); sm.fail("t1")
        assert t.state == TaskState.QUEUED
        sm.start("t1"); sm.fail("t1")
        assert t.state == TaskState.ARCHIVED


class TestPriorityQueue:
    def test_evicts_lowest_rank(self):
        sm = StateMachine(max_queue_size=2)
        for i in range(3):
            t = make_task(f"t{i}", rank=i)
            sm.propose(t)
            if i < 2:
                sm.enqueue(t.id)
        # third enqueue triggers eviction
        sm.propose(make_task("t3", rank=3))
        sm.enqueue("t3")
        # t0 (rank 0) should be evicted
        assert sm.get_task("t0").state == TaskState.ARCHIVED
        assert sm.queue_size() == 2

    def test_next_ready_returns_highest_rank(self, sm):
        for i in range(3):
            t = make_task(f"t{i}", rank=i)
            sm.propose(t)
            sm.enqueue(t.id)
        next_t = sm.next_ready()
        assert next_t.rank == 2  # highest rank


class TestPersistence:
    def test_save_and_load(self, sm):
        for i in range(3):
            t = make_task(f"t{i}", rank=i)
            sm.propose(t)
            sm.enqueue(t.id)
        sm.start("t2")
        sm.complete("t2", result="done")

        tmp = os.path.join(tempfile.mkdtemp(), "state.json")
        sm.save(tmp)
        sm2 = StateMachine.load(tmp)

        assert len(sm2.tasks) == 3
        assert sm2.get_task("t2").state == TaskState.COMPLETED
        assert sm2.get_task("t2").result == "done"
        assert sm2.queue_size() == 2  # t0 and t1 still queued

    def test_transition_log_preserved(self, sm):
        t = make_task("t1")
        sm.propose(t)
        sm.enqueue("t1")
        tmp = os.path.join(tempfile.mkdtemp(), "state.json")
        sm.save(tmp)
        sm2 = StateMachine.load(tmp)
        assert len(sm2.transition_log) >= 2
