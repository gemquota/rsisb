"""Lifecycle State Machine — 5-state task lifecycle with priority queue.

States: PROPOSED -> QUEUED -> EXECUTING -> COMPLETED
                                    |              |
                                    v              v
                                QUEUED (retry)  ARCHIVED (exhausted)

Task retention: max 3 execution attempts.
Queue eviction: when full, drops lowest-ranked tasks (value-alignment weighted).
"""

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskState(Enum):
    PROPOSED = "PROPOSED"
    QUEUED = "QUEUED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class EvictionPolicy(Enum):
    VALUE_WEIGHTED = "value_weighted"  # Evict lowest value-alignment weight first
    RANK_THEN_AGE = "rank_then_age"    # Evict lowest rank, then oldest


@dataclass
class Task:
    """A single task in the lifecycle state machine."""

    id: str
    description: str
    rank: int
    value_alignment: list[str] = field(default_factory=list)
    state: TaskState = TaskState.PROPOSED
    attempts: int = 0
    max_attempts: int = 3
    created_at: float = 0.0
    updated_at: float = 0.0
    result: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        now = time.time()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "rank": self.rank,
            "value_alignment": self.value_alignment,
            "state": self.state.value,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        data = dict(data)
        data["state"] = TaskState(data["state"])
        return cls(**data)


class StateMachine:
    """Manages task lifecycle transitions and priority queue.

    The state machine enforces:
      - Max 3 execution attempts per task
      - Value-weighted eviction when queue is full
      - Logging of every state transition to telemetry
    """

    def __init__(self, max_queue_size: int = 30, eviction_policy: EvictionPolicy = EvictionPolicy.VALUE_WEIGHTED):
        self.tasks: dict[str, Task] = {}
        self.queue_order: list[str] = []  # Ordered list of task IDs in QUEUED state
        self.max_queue_size = max_queue_size
        self.eviction_policy = eviction_policy
        self.transition_log: list[dict] = []

    # --- Task creation ---

    def propose(self, task: Task) -> Task:
        """Register a new task in PROPOSED state."""
        if task.id in self.tasks:
            raise ValueError(f"Task '{task.id}' already exists")
        task.state = TaskState.PROPOSED
        self.tasks[task.id] = task
        self._log_transition(task.id, None, TaskState.PROPOSED)
        return task

    # --- State transitions ---

    def enqueue(self, task_id: str) -> Task:
        """Transition a task from PROPOSED to QUEUED."""
        task = self._get_task(task_id)
        self._assert_state(task, TaskState.PROPOSED)
        task.state = TaskState.QUEUED
        task.updated_at = time.time()
        self.queue_order.append(task_id)
        self._enforce_queue_capacity()
        self._log_transition(task_id, TaskState.PROPOSED, TaskState.QUEUED)
        return task

    def start(self, task_id: str) -> Task:
        """Transition a task from QUEUED to EXECUTING."""
        task = self._get_task(task_id)
        self._assert_state(task, TaskState.QUEUED)
        task.state = TaskState.EXECUTING
        task.attempts += 1
        task.updated_at = time.time()
        if task_id in self.queue_order:
            self.queue_order.remove(task_id)
        self._log_transition(task_id, TaskState.QUEUED, TaskState.EXECUTING)
        return task

    def complete(self, task_id: str, result: str = "") -> Task:
        """Transition a task from EXECUTING to COMPLETED (success)."""
        task = self._get_task(task_id)
        self._assert_state(task, TaskState.EXECUTING)
        task.state = TaskState.COMPLETED
        task.result = result
        task.updated_at = time.time()
        self._log_transition(task_id, TaskState.EXECUTING, TaskState.COMPLETED)
        return task

    def fail(self, task_id: str, error: str = "") -> Task:
        """Handle a task failure from EXECUTING.

        If attempts < max_attempts, re-queues the task (EXECUTING -> QUEUED).
        If attempts >= max_attempts, archives it (EXECUTING -> ARCHIVED).
        """
        task = self._get_task(task_id)
        self._assert_state(task, TaskState.EXECUTING)
        task.error = error
        task.updated_at = time.time()

        if task.attempts < task.max_attempts:
            task.state = TaskState.QUEUED
            self.queue_order.append(task_id)
            self._log_transition(task_id, TaskState.EXECUTING, TaskState.QUEUED)
        else:
            task.state = TaskState.ARCHIVED
            self._log_transition(task_id, TaskState.EXECUTING, TaskState.ARCHIVED)

        return task

    def archive(self, task_id: str) -> Task:
        """Manually archive a task from any active state."""
        task = self._get_task(task_id)
        prev_state = task.state
        task.state = TaskState.ARCHIVED
        task.updated_at = time.time()
        if task_id in self.queue_order:
            self.queue_order.remove(task_id)
        self._log_transition(task_id, prev_state, TaskState.ARCHIVED)
        return task

    # --- Priority queue ---

    def _enforce_queue_capacity(self):
        """Evict lowest-priority tasks if queue exceeds max size."""
        while len(self.queue_order) > self.max_queue_size:
            victim_id = self._select_victim()
            victim = self.tasks[victim_id]
            prev_state = victim.state
            victim.state = TaskState.ARCHIVED
            victim.updated_at = time.time()
            self.queue_order.remove(victim_id)
            self._log_transition(victim_id, prev_state, TaskState.ARCHIVED)

    def _select_victim(self) -> str:
        """Select the task to evict based on eviction policy."""
        queued_tasks = [self.tasks[tid] for tid in self.queue_order]

        if self.eviction_policy == EvictionPolicy.VALUE_WEIGHTED:
            # Score: lower is more evictable
            def eviction_score(task: Task) -> float:
                # Negative rank: higher rank = more important = harder to evict
                rank_score = task.rank
                # Value alignment weight: sum of axiom weights
                value_weights = {
                    "robustness": 5, "coherence": 4, "efficiency": 3,
                    "maintainability": 4, "autonomy": 3, "identity": 5,
                    "learning": 4, "stability": 5, "growth": 3,
                }
                value_score = sum(value_weights.get(v, 1) for v in task.value_alignment)
                # Age bonus: older tasks (lower timestamp) slightly favored
                age_bonus = task.created_at / 1e9
                return rank_score - value_score + age_bonus

            victim = min(queued_tasks, key=eviction_score)
            return victim.id

        # Default: rank then age
        queued_tasks.sort(key=lambda t: (t.rank, t.created_at))
        return queued_tasks[0].id

    # --- Queries ---

    def next_ready(self) -> Optional[Task]:
        """Return the next QUEUED task (highest rank first, FIFO for ties)."""
        if not self.queue_order:
            return None
        queued = [(self.tasks[tid].rank, idx, tid) for idx, tid in enumerate(self.queue_order)]
        queued.sort(key=lambda x: (-x[0], x[1]))
        return self.tasks[queued[0][2]]

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def get_tasks_by_state(self, state: TaskState) -> list[Task]:
        return [t for t in self.tasks.values() if t.state == state]

    def queue_size(self) -> int:
        return len(self.queue_order)

    # --- Persistence ---

    def to_dict(self) -> dict:
        return {
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "queue_order": list(self.queue_order),
            "max_queue_size": self.max_queue_size,
            "eviction_policy": self.eviction_policy.value,
            "transition_log": self.transition_log[-100:],  # Keep last 100
        }

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "StateMachine":
        with open(path) as f:
            data = json.load(f)
        sm = cls(
            max_queue_size=data.get("max_queue_size", 30),
            eviction_policy=EvictionPolicy(data.get("eviction_policy", "value_weighted")),
        )
        for tid, tdata in data.get("tasks", {}).items():
            sm.tasks[tid] = Task.from_dict(tdata)
        sm.queue_order = list(data.get("queue_order", []))
        sm.transition_log = list(data.get("transition_log", []))
        return sm

    # --- Internal helpers ---

    def _get_task(self, task_id: str) -> Task:
        if task_id not in self.tasks:
            raise KeyError(f"Task '{task_id}' not found")
        return self.tasks[task_id]

    def _assert_state(self, task: Task, expected: TaskState):
        if task.state != expected:
            raise ValueError(
                f"Task '{task.id}' is in state {task.state.value}, expected {expected.value}"
            )

    def _log_transition(self, task_id: str, from_state: Optional[TaskState], to_state: TaskState):
        self.transition_log.append({
            "task_id": task_id,
            "from": from_state.value if from_state else None,
            "to": to_state.value,
            "timestamp": time.time(),
        })
