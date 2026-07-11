"""Queue Manager — Balances the active priority queue for L2 execution.

Manages goal priorities, handles eviction when the queue is full,
and applies value-axiom weighting to ensure high-value goals are
executed first.
"""

import time
from typing import Optional

from l3_self_direction.goal_generator import Goal


class QueueManager:
    """Manages the L3 goal queue with priority ordering and eviction.

    Integrates with the GoalGenerator to receive goals and with the
    StateMachine to feed them into L2 execution.
    """

    def __init__(self, max_size: int = 30):
        self.max_size = max_size
        self.queue: list[Goal] = []

    def enqueue(self, goal: Goal) -> Optional[Goal]:
        """Add a goal to the queue. Returns evicted goal if queue was full."""
        goal.status = "queued"
        self.queue.append(goal)
        self._resort()

        evicted = None
        if len(self.queue) > self.max_size:
            evicted = self.queue.pop()  # Remove lowest priority
            evicted.status = "archived"

        return evicted

    def enqueue_many(self, goals: list[Goal]) -> list[Goal]:
        """Add multiple goals. Returns list of evicted goals."""
        evicted = []
        for g in goals:
            e = self.enqueue(g)
            if e:
                evicted.append(e)
        return evicted

    def next_goal(self) -> Optional[Goal]:
        """Return the highest-priority goal and mark it executing."""
        if not self.queue:
            return None
        goal = self.queue.pop(0)
        goal.status = "executing"
        return goal

    def complete_goal(self, goal_id: str, result: str = ""):
        """Mark a goal as completed."""
        for g in self.queue:
            if g.id == goal_id:
                g.status = "completed"
                self.queue.remove(g)
                return

    def fail_goal(self, goal_id: str):
        """Mark a goal as failed (re-queues with lowered priority)."""
        for g in self.queue:
            if g.id == goal_id:
                g.priority *= 0.5  # Halve priority on failure
                g.status = "queued"
                self._resort()
                return

    def get_queue_state(self) -> dict:
        return {
            "size": len(self.queue),
            "max_size": self.max_size,
            "fill_percent": round((len(self.queue) / self.max_size) * 100, 1),
            "top_priorities": [{"id": g.id, "priority": g.priority, "desc": g.description[:60]}
                               for g in self.queue[:5]],
        }

    def _resort(self):
        """Sort queue by priority descending, then by creation time."""
        self.queue.sort(key=lambda g: (-g.priority, g.created_at))
