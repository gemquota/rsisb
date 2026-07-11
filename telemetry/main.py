"""RSIS Telemetry API — FastAPI server.

Provides REST endpoints for system status, layer scores, pulse logs,
self-model, identity snapshots, L3 self-direction, and RRP protocol.

Serves no frontend. The dashboard is a self-contained static app in
dashboard/index.html that connects to any telemetry API address.
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from identity.self_model import SelfModel
from identity.value_reinforcement import ValueReinforcementTracker
from identity.snapshot import SnapshotManager
from identity.crisis_monitor import CrisisMonitor

app = FastAPI(title="RSIS Telemetry API", version="0.0.9")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Initialize modules ---
self_model = SelfModel()
value_tracker = ValueReinforcementTracker()
snapshot_manager = SnapshotManager()
crisis_monitor = CrisisMonitor()
RACK_DIR = Path("rack")
PULSES_DIR = RACK_DIR / "pulses"


# === Core API Endpoints ===


@app.get("/api/status")
def get_status():
    total = self_model.total_attempts or 1
    return {
        "version": self_model.version,
        "layer_scores": {
            lid: {"score": ls.score, "metrics": ls.metrics}
            for lid, ls in self_model.layer_scores.items()
        },
        "total_attempts": self_model.total_attempts,
        "successful_applications": self_model.successful_applications,
        "success_rate": round((self_model.successful_applications / total) * 100, 1),
        "snapshot_count": self_model.snapshot_count,
        "kg_nodes_raw": self_model.kg_nodes_raw,
        "kg_nodes_consolidated": self_model.kg_nodes_consolidated,
    }


@app.get("/api/layers")
def get_layers():
    return {
        "layers": {
            lid: {"score": ls.score, "metrics": ls.metrics}
            for lid, ls in self_model.layer_scores.items()
        }
    }


@app.get("/api/pulses")
def list_pulses(limit: int = 20):
    pulses = []
    if PULSES_DIR.exists():
        for p in sorted(PULSES_DIR.glob("pulse-*.json"), reverse=True)[:limit]:
            try:
                with open(p) as f:
                    data = json.load(f)
                pulses.append({
                    "pulse_id": data.get("pulse_id"),
                    "phase": data.get("phase"),
                    "decision": data.get("decision"),
                    "timestamp": data.get("timestamp"),
                    "summary": data.get("summary", "")[:200],
                })
            except (json.JSONDecodeError, KeyError):
                continue
    return {"pulses": pulses, "total": len(pulses)}


@app.get("/api/pulses/latest")
def get_latest_pulse():
    latest_path = PULSES_DIR / "latest.json"
    if not latest_path.exists():
        raise HTTPException(status_code=404, detail="No pulses found")
    with open(latest_path) as f:
        return json.load(f)


@app.get("/api/pulses/{pulse_id}")
def get_pulse(pulse_id: int):
    path = PULSES_DIR / f"pulse-{pulse_id:03d}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Pulse {pulse_id} not found")
    with open(path) as f:
        return json.load(f)


@app.get("/api/self-model")
def get_self_model():
    return self_model.to_dict()


@app.get("/api/self-model/concept")
def get_self_concept():
    return {
        "purpose": self_model.self_concept.purpose,
        "self_description": self_model.self_concept.self_description,
        "aspirations": self_model.self_concept.aspirations,
        "core_beliefs": self_model.self_concept.core_beliefs,
        "current_narrative": self_model.self_concept.current_narrative,
        "last_updated": self_model.self_concept.last_updated,
    }


@app.post("/api/self-model/narrative")
def set_narrative(req: dict):
    narrative = req.get("narrative", "")
    self_model.set_narrative(narrative)
    return {"status": "updated", "narrative": narrative}


@app.get("/api/snapshots")
def list_snapshots():
    return {"snapshots": snapshot_manager.list_snapshots()}


@app.get("/api/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: int):
    snap = snapshot_manager.load_snapshot(snapshot_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return snap.to_dict()


@app.post("/api/snapshots/take")
def take_snapshot():
    snap = snapshot_manager.take_snapshot(self_model, value_tracker)
    self_model.snapshot_count += 1
    return snap.to_dict()


@app.get("/api/value-axioms")
def get_value_axioms():
    return {
        "axioms": value_tracker.to_dict(),
        "weights": {a: value_tracker.get_weight(a) for a in value_tracker.axioms},
    }


@app.post("/api/value-axioms/reinforce")
def reinforce_axiom(req: dict):
    axiom_name = req.get("axiom_name", "")
    count = req.get("count", 1)
    try:
        state = value_tracker.reinforce(axiom_name, count)
        return {"axiom": axiom_name, "state": state}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/knowledge-graph")
def get_knowledge_graph():
    kg_path = RACK_DIR / "shared" / "knowledge_graph.json"
    if not kg_path.exists():
        return {"nodes": [], "relationships": [], "total_nodes_raw": 0}
    with open(kg_path) as f:
        return json.load(f)


@app.get("/api/health")
def get_health():
    report = crisis_monitor.check_health(self_model)
    return report


@app.post("/api/crisis/resolve")
def resolve_crisis(req: dict):
    resolution = req.get("resolution", "Manual resolution")
    return crisis_monitor.resolve_crisis(resolution)


@app.get("/api/metrics/timeline")
def get_metrics_timeline():
    snaps = snapshot_manager.list_snapshots()
    timeline = []
    for s in snaps:
        entry = {"snapshot_id": s["snapshot_id"], "timestamp": s["timestamp"]}
        for lid, ldata in s.get("layer_scores", {}).items():
            entry[lid] = ldata.get("score", 0)
        timeline.append(entry)
    return {"timeline": timeline}


# === L3 Self-Direction Endpoints ===


from l3_self_direction.signal_watcher import SignalWatcher
from l3_self_direction.goal_generator import GoalGenerator
from l3_self_direction.queue_manager import QueueManager

_l3_watcher = SignalWatcher(watch_paths=["."], poll_interval=30.0)
_l3_generator = GoalGenerator()
_l3_queue = QueueManager(max_size=10)


@app.get("/api/l3/signals")
def get_l3_signals(limit: int = 20):
    new_sigs = _l3_watcher.poll()
    return {
        "new_signals": len(new_sigs),
        "total_signals": _l3_watcher.get_signal_count(),
        "recent": _l3_watcher.get_recent_signals(limit),
    }


@app.post("/api/l3/poll")
def poll_signals():
    signals = _l3_watcher.poll()
    if len(signals) > 0:
        self_model.update_layer_metric("L3", "signal_coverage",
                                        min(100.0, 85.0 + len(signals)))
    return {"signals_detected": len(signals), "total": _l3_watcher.get_signal_count()}


@app.get("/api/l3/goals")
def get_l3_goals():
    state = {
        "crisis_active": crisis_monitor.state.active,
        "layer_scores": {lid: self_model.get_layer_score(lid)
                         for lid in ["L1","L2","L3","L4","L5","L6"]},
        "metrics": {lid: ls.metrics for lid, ls in self_model.layer_scores.items()},
    }
    _l3_generator.generate_from_state(state)
    active = _l3_generator.get_active_goals(20)
    return {"stats": _l3_generator.get_stats(), "active_goals": [g.to_dict() for g in active]}


@app.get("/api/l3/queue")
def get_l3_queue():
    return _l3_queue.get_queue_state()


@app.post("/api/l3/queue/next")
def dequeue_next_goal():
    goal = _l3_queue.next_goal()
    if goal is None:
        return {"goal": None, "message": "Queue empty"}
    return {"goal": goal.to_dict()}


# === RRP Protocol Endpoints ===


from rrp.protocol import RRPEngine
from rrp.persistence import RRPPersistence
from rrp.compact import encode_compact

_rrp_persist = RRPPersistence()
_rrp_engines: dict[str, RRPEngine] = {}


class RRPInitRequest(BaseModel):
    session_id: str = "default"
    use_case: int = 1
    mode: int = 1
    max_rounds: int = 5
    depth: int = 2
    questions_per_round: int = 3
    mcq_options: int = 3


class RRPProcessRequest(BaseModel):
    text: str


class RRPAmbiguityRequest(BaseModel):
    requirements: float = None
    data_model: float = None
    edge_case: float = None
    determinism: float = None


class RRPDecisionRequest(BaseModel):
    decision_type: str = "clarification"
    description: str = ""
    reasoning: str = ""
    confidence: float = 0.8


def _get_rrp(session_id: str) -> RRPEngine:
    if session_id in _rrp_engines:
        return _rrp_engines[session_id]
    loaded = _rrp_persist.load(session_id)
    if loaded:
        _rrp_engines[session_id] = loaded
    return loaded


@app.get("/api/rrp/sessions")
def list_rrp_sessions():
    return {"sessions": _rrp_persist.list_sessions()}


@app.post("/api/rrp/init")
def init_rrp_session(req: RRPInitRequest):
    engine = RRPEngine().init_session(
        session_id=req.session_id, use_case=req.use_case, mode=req.mode,
        max_rounds=req.max_rounds, depth=req.depth,
        questions_per_round=req.questions_per_round, mcq_options=req.mcq_options,
    )
    _rrp_persist.save(engine)
    _rrp_engines[req.session_id] = engine
    return {
        "status": "initialized",
        "session_id": req.session_id,
        "compact": encode_compact(engine.state),
        "state": engine.get_state_dict(),
    }


@app.post("/api/rrp/{session_id}/process")
def process_rrp_input(session_id: str, req: RRPProcessRequest):
    engine = _get_rrp(session_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    result = engine.process_user_input(req.text)
    _rrp_persist.save(engine)
    return {"result": result, "state": engine.get_state_dict(),
            "compact": encode_compact(engine.state)}


@app.post("/api/rrp/{session_id}/ambiguity")
def rate_rrp_ambiguity(session_id: str, req: RRPAmbiguityRequest):
    engine = _get_rrp(session_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    engine.apply_semantic_ambiguity_json(
        requirements=req.requirements, data_model=req.data_model,
        edge_case=req.edge_case, determinism=req.determinism,
    )
    _rrp_persist.save(engine)
    return {"ambiguity": engine.state.ambiguity.to_dict(),
            "compact": encode_compact(engine.state)}


@app.post("/api/rrp/{session_id}/decision")
def add_rrp_decision(session_id: str, req: RRPDecisionRequest):
    engine = _get_rrp(session_id)
    if not engine:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    engine.add_decision(req.decision_type, req.description, req.reasoning, req.confidence)
    _rrp_persist.save(engine)
    return {"decisions": len(engine.state.decisions),
            "compact": encode_compact(engine.state)}


@app.get("/api/rrp/{session_id}")
def get_rrp_session(session_id: str):
    engine = _get_rrp(session_id)
    if not engine:
        engine = _rrp_persist.load(session_id)
        if not engine:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        _rrp_engines[session_id] = engine
    return {"state": engine.get_state_dict(), "compact": encode_compact(engine.state)}


@app.get("/api/rrp/{session_id}/compact")
def get_rrp_compact(session_id: str):
    engine = _get_rrp(session_id)
    if not engine:
        engine = _rrp_persist.load(session_id)
        if not engine:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"compact": encode_compact(engine.state)}
