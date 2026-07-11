"""RRP — Recursive Refinement Protocol.

A structured dialogue protocol for systematic refinement of engineering
problems through iterative conversation rounds, ambiguity tracking,
constraint locking, and decision capture.

Layers:
  L1 (Conversational): Pacing, UX, summaries, agent interaction
  L2 (System Integrity): Ambiguity vectors, constraint locking, contradiction detection
"""

from rrp.state_machine import RRPState, AmbiguityVector, Decision, Constraint, SessionMeta, Telemetry
from rrp.protocol import RRPEngine
from rrp.compact import encode_compact, decode_compact
from rrp.persistence import RRPPersistence

__all__ = [
    "RRPState", "AmbiguityVector", "Decision", "Constraint", "SessionMeta", "Telemetry",
    "RRPEngine", "encode_compact", "decode_compact", "RRPPersistence",
]
