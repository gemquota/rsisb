"""RRP Persistence — Atomic JSON state snapshots with session isolation.

Each session is stored as an atomic JSON file. Writes use temp file +
atomic rename to prevent corruption. Sessions are fully isolated.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from rrp.state_machine import RRPState
from rrp.protocol import RRPEngine


DEFAULT_STATE_DIR = "rack/rrp_sessions"


class RRPPersistence:
    """Manages RRP session state files with atomic writes."""

    def __init__(self, state_dir: str = DEFAULT_STATE_DIR):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def session_path(self, session_id: str) -> Path:
        return self.state_dir / f"{session_id}.json"

    def save(self, engine: RRPEngine, session_id: Optional[str] = None) -> str:
        """Atomically save an RRPEngine's state to a JSON file."""
        sid = session_id or engine.state.session.session_id
        path = self.session_path(sid)

        data = engine.get_state_dict()
        data["_session_id"] = sid

        # Atomic write: temp file → rename
        fd, tmp_path = tempfile.mkstemp(dir=str(self.state_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        return sid

    def load(self, session_id: str) -> Optional[RRPEngine]:
        """Load an RRPEngine from a saved state file."""
        path = self.session_path(session_id)
        if not path.exists():
            return None
        with open(path) as f:
            data = json.load(f)

        engine = RRPEngine()
        engine.init_session(
            session_id=session_id,
            use_case=data.get("session", {}).get("use_case", 1),
            mode=data.get("session", {}).get("execution_mode", 1),
            max_rounds=data.get("session", {}).get("max_rounds", 5),
            depth=data.get("session", {}).get("depth", 2),
            questions_per_round=data.get("session", {}).get("open_questions_per_round", 3),
            mcq_options=data.get("session", {}).get("mcq_options_per_question", 3),
        )

        # Restore ambiguity
        amb = data.get("ambiguity", {})
        engine.state.set_ambiguity(
            requirements=amb.get("requirements"),
            data_model=amb.get("data_model"),
            edge_case=amb.get("edge_case"),
            determinism=amb.get("determinism"),
        )

        # Restore rounds and status
        engine.state.current_round = data.get("current_round", 0)
        engine.state.status = data.get("status", "initialized")

        # Restore constraints
        for c in data.get("constraints", []):
            engine.state.add_constraint(c["key"], c["value"], c.get("source", "restored"))

        # Restore decisions
        from rrp.state_machine import DecisionType, Decision
        for d in data.get("decisions", []):
            try:
                dt = DecisionType(d.get("decision_type", "clarification"))
            except ValueError:
                dt = DecisionType.CLARIFICATION
            engine.state.decisions.append(Decision(
                round=d.get("round", 0),
                decision_type=dt,
                description=d.get("description", ""),
                reasoning=d.get("reasoning", ""),
                confidence=d.get("confidence", 0.8),
            ))

        return engine

    def list_sessions(self) -> list[dict]:
        """List all saved sessions with metadata."""
        sessions = []
        for path in sorted(self.state_dir.glob("*.json")):
            try:
                with open(path) as f:
                    data = json.load(f)
                sid = path.stem
                sessions.append({
                    "session_id": sid,
                    "status": data.get("status", "unknown"),
                    "rounds": data.get("current_round", 0),
                    "max_rounds": data.get("session", {}).get("max_rounds", 0),
                    "use_case": data.get("session", {}).get("use_case", 1),
                    "decisions": len(data.get("decisions", [])),
                    "constraints": len(data.get("constraints", [])),
                    "ambiguity_avg": round(sum(data.get("ambiguity", {}).values()) / 4, 2) if data.get("ambiguity") else 0,
                    "file": path.name,
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session state file."""
        path = self.session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False
