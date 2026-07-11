"""Identity App — Expanded RSIS Identity Layer.

A standalone, greatly expanded identity management application extracted
from the RSIS (Recursive Self-Improving System) architecture.

Manages self-modeling, value axioms, identity snapshots, crisis detection,
and identity evolution — originally Layer 6 (L6) of RSIS.
"""

__version__ = "1.1.0"
__all__ = [
    "SelfModel",
    "IdentitySnapshot",
    "SnapshotManager",
    "SnapshotDiff",
    "Timeline",
    "SnapshotScheduler",
    "ValueAxiomSystem",
    "ValueAlignment",
    "DriftDetector",
    "CrisisMonitor",
    "CrisisPredictor",
    "RecoveryPlanner",
    "Storage",
]

from identity_app.core import SelfModel
from identity_app.snapshot import IdentitySnapshot, SnapshotManager, SnapshotDiff, Timeline, SnapshotScheduler
from identity_app.values import ValueAxiomSystem, ValueAlignment, DriftDetector
from identity_app.crisis import CrisisMonitor, CrisisPredictor, RecoveryPlanner
from identity_app.storage import Storage
