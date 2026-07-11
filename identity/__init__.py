"""Identity Core — Self-modeling, snapshots, value axioms, and crisis detection.

This package implements L6 of the RSIS architecture: the Identity Layer.
It manages self-model state, generates identity snapshots, tracks value
axiom reinforcement, and monitors for identity crisis conditions.
"""

from identity.self_model import SelfModel
from identity.snapshot import IdentitySnapshot
from identity.value_reinforcement import ValueReinforcementTracker
from identity.crisis_monitor import CrisisMonitor

__all__ = [
    "SelfModel",
    "IdentitySnapshot",
    "ValueReinforcementTracker",
    "CrisisMonitor",
]
