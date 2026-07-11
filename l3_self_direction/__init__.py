"""L3 Self-Direction Loop — Signal detection, goal generation, and priority queue management.

This module implements the L3 layer of the RSIS architecture:
  - Signal Watcher: polls the filesystem for changes (increases signal_coverage)
  - Goal Generator: produces ranked goals from signals + system state (increases goal_generation/diversity)
  - Queue Manager: balances the active priority queue (increases queue_health)
"""
from l3_self_direction.signal_watcher import SignalWatcher
from l3_self_direction.goal_generator import GoalGenerator
from l3_self_direction.queue_manager import QueueManager
__all__ = ["SignalWatcher", "GoalGenerator", "QueueManager"]
