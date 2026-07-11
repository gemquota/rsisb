"""API — FastAPI REST API for the Identity App.

Provides HTTP access to all identity operations with OpenAPI docs.
"""

import time
from typing import Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from identity_app.core import SelfModel
from identity_app.values import ValueAxiomSystem, ValueAlignment, DriftDetector
from identity_app.snapshot import SnapshotManager, SnapshotDiff, Timeline, SnapshotScheduler
from identity_app.crisis import CrisisMonitor, CrisisPredictor, RecoveryPlanner


# ── Pydantic Models ─────────────────────────────────────────────

class HealthCheckResponse(BaseModel):
    healthy: bool
    severity: str
    crisis_active: bool
    violations: list[str]
    warnings: list[str]
    metrics: dict

class SnapshotResponse(BaseModel):
    snapshot_id: int
    timestamp: float
    version: str
    narrative: str
    layer_scores: dict
    value_axioms: dict
    traits: dict
    tag: str
    origin: str

class StatusResponse(BaseModel):
    version: str
    layer_scores: dict
    traits: dict
    snapshot_count: int
    total_attempts: int
    success_rate: float
    crisis_count: int
    crisis_active: bool
    current_narrative: str

class DiffResponse(BaseModel):
    snapshot_a: int
    snapshot_b: int
    time_span: float
    layer_scores: dict
    value_axioms: dict
    traits: dict
    summary: str

class ValueSystemResponse(BaseModel):
    axioms: dict
    balance_score: float
    strongest: list
    weakest: list

class PredictionResponse(BaseModel):
    overall_risk: float
    risk_level: str
    high_risk_layers: list
    predictions: dict
    recommendation: str

class CrisisStateResponse(BaseModel):
    active: bool
    severity: str
    triggered_at: float
    triggered_by: str
    history: list

class RecoveryPlanResponse(BaseModel):
    plan_id: str
    name: str
    status: str
    progress: float
    current_step: Optional[dict]

class ReinforceRequest(BaseModel):
    axiom_name: str
    count: int = 1

class SnapshotTakeRequest(BaseModel):
    tag: str = ""
    notes: str = ""

class NarrativeUpdateRequest(BaseModel):
    narrative: str

class TraitUpdateRequest(BaseModel):
    delta: float
    confidence_delta: float = 0.05

class ResolveCrisisRequest(BaseModel):
    resolution: str = "Manual resolution via API"


# ── App Factory ─────────────────────────────────────────────────

def create_app(components: Optional[dict] = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        components: Optional pre-initialized component dict.
                    If None, creates new instances.
    """
    app = FastAPI(
        title="Identity App API",
        description="Expanded RSIS Identity Layer — self-modeling, value axioms, snapshots, crisis detection",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Component initialization ────────────────────────────────
    c = components or {}

    @app.on_event("startup")
    async def startup():
        if not components:
            from identity_app.storage import Storage, StorageConfig
            storage = Storage()
            model = SelfModel(storage=storage)
            axioms = ValueAxiomSystem(model, storage=storage)
            c["storage"] = storage
            c["model"] = model
            c["axioms"] = axioms
            c["alignment"] = ValueAlignment(axioms)
            c["drift"] = DriftDetector(axioms, model)
            c["snap_mgr"] = SnapshotManager(storage=storage)
            c["timeline"] = Timeline(c["snap_mgr"], storage=storage)
            c["scheduler"] = SnapshotScheduler(c["snap_mgr"], storage=storage)
            c["crisis"] = CrisisMonitor(model, storage=storage)
            c["predictor"] = CrisisPredictor(model)
            c["recovery"] = RecoveryPlanner(model, storage=storage)

    # ── Helpers ─────────────────────────────────────────────────

    def _get_crisis_monitor():
        return c.get("crisis") or CrisisMonitor(_get_model())

    def _get_model():
        return c.get("model") or SelfModel()

    def _get_snapshot_mgr():
        return c.get("snap_mgr") or SnapshotManager()

    def _get_axioms():
        return c.get("axioms") or ValueAxiomSystem(_get_model())

    # ── Routes ──────────────────────────────────────────────────

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "app": "Identity App",
            "version": "1.0.0",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    @app.get("/status", response_model=StatusResponse, tags=["Identity"])
    async def get_status():
        """Get full identity status summary."""
        model = _get_model()
        crisis = _get_crisis_monitor()
        return StatusResponse(
            version=model.version,
            layer_scores={lid: ls.get("score", 0) for lid, ls in model.layer_scores.items()},
            traits=model.get_trait_profile(),
            snapshot_count=model.snapshot_count,
            total_attempts=model.total_attempts,
            success_rate=model.get_success_rate(),
            crisis_count=model.crisis_count,
            crisis_active=crisis.state.get("active", False),
            current_narrative=model.get_narrative(),
        )

    # ── Self-Model ──────────────────────────────────────────────

    @app.get("/self", tags=["Identity"])
    async def get_self_model():
        """Get the full self-model data."""
        return _get_model().to_dict()

    @app.get("/self/narrative", tags=["Identity"])
    async def get_narrative():
        """Get current narrative."""
        return {"narrative": _get_model().get_narrative()}

    @app.put("/self/narrative", tags=["Identity"])
    async def update_narrative(req: NarrativeUpdateRequest):
        """Update current narrative."""
        _get_model().set_narrative(req.narrative)
        return {"status": "updated", "narrative": req.narrative}

    @app.get("/self/traits", tags=["Identity"])
    async def get_traits():
        """Get identity trait profile."""
        model = _get_model()
        return model.get_trait_profile_with_confidence()

    @app.put("/self/traits/{trait_name}", tags=["Identity"])
    async def update_trait(trait_name: str, req: TraitUpdateRequest):
        """Update a specific trait."""
        model = _get_model()
        if trait_name not in model.traits:
            raise HTTPException(404, f"Unknown trait: {trait_name}")
        model.update_trait(trait_name, req.delta, req.confidence_delta)
        return {"status": "updated", "trait": trait_name, "new_score": model.traits[trait_name].score}

    @app.get("/self/beliefs", tags=["Beliefs"])
    async def get_beliefs(category: Optional[str] = None, min_confidence: float = 0.0):
        """Get active beliefs."""
        model = _get_model()
        beliefs = list(model.beliefs.values())
        if category:
            beliefs = [b for b in beliefs if b.category == category]
        beliefs = [b for b in beliefs if b.active and b.confidence >= min_confidence]
        return {b.name: b.to_dict() for b in beliefs}

    @app.get("/self/beliefs/{name}", tags=["Beliefs"])
    async def get_belief(name: str):
        """Get a specific belief."""
        belief = _get_model().get_belief(name)
        if not belief:
            raise HTTPException(404, f"Belief '{name}' not found")
        return belief.to_dict()

    @app.post("/self/beliefs", tags=["Beliefs"])
    async def add_belief(name: str, statement: str, category: str = "derived", confidence: float = 0.5):
        """Add a new belief."""
        belief = _get_model().add_belief(name, statement, category, confidence)
        return {"status": "created", "belief": belief.to_dict()}

    # ── Value Axioms ────────────────────────────────────────────

    @app.get("/values", response_model=ValueSystemResponse, tags=["Values"])
    async def get_values():
        """Get value axiom system status."""
        axioms = _get_axioms()
        return ValueSystemResponse(
            axioms={n: s.to_dict() for n, s in axioms.axioms.items()},
            balance_score=axioms.get_balance_score(),
            strongest=axioms.get_strongest_axioms(5),
            weakest=axioms.get_weakest_axioms(5),
        )

    @app.post("/values/reinforce", tags=["Values"])
    async def reinforce_axiom(req: ReinforceRequest):
        """Reinforce a value axiom."""
        axioms = _get_axioms()
        if req.axiom_name not in axioms.axioms:
            raise HTTPException(404, f"Unknown axiom: {req.axiom_name}")
        state = axioms.reinforce(req.axiom_name, req.count)
        return {"status": "reinforced", "axiom": req.axiom_name, "state": state.to_dict()}

    @app.get("/values/alignment", tags=["Values"])
    async def get_alignment():
        """Get value alignment across layers."""
        axioms = _get_axioms()
        alignment = ValueAlignment(axioms)
        return alignment.get_overall_alignment()

    @app.get("/values/drift", tags=["Values"])
    async def get_drift():
        """Get drift analysis."""
        model = _get_model()
        axioms = _get_axioms()
        drift = DriftDetector(axioms, model)
        return drift.get_full_drift_report()

    # ── Snapshots ───────────────────────────────────────────────

    @app.get("/snapshots", tags=["Snapshots"])
    async def list_snapshots(limit: int = Query(50, le=200)):
        """List snapshots."""
        return _get_snapshot_mgr().list_snapshots(limit)

    @app.post("/snapshots", tags=["Snapshots"])
    async def take_snapshot(req: SnapshotTakeRequest):
        """Take a new identity snapshot."""
        model = _get_model()
        axioms = _get_axioms()
        snap_mgr = _get_snapshot_mgr()
        snapshot = snap_mgr.take_snapshot(model, axiom_system=axioms, tag=req.tag, notes=req.notes)
        return {"snapshot_id": snapshot.snapshot_id, "timestamp": snapshot.timestamp,
                "tag": snapshot.tag, "narrative": snapshot.narrative}

    @app.get("/snapshots/{snapshot_id}", tags=["Snapshots"])
    async def get_snapshot(snapshot_id: int = Path(ge=1)):
        """Get a specific snapshot."""
        snapshot = _get_snapshot_mgr().load_snapshot(snapshot_id)
        if not snapshot:
            raise HTTPException(404, f"Snapshot #{snapshot_id} not found")
        return snapshot.to_dict()

    @app.delete("/snapshots/{snapshot_id}", tags=["Snapshots"])
    async def delete_snapshot(snapshot_id: int = Path(ge=1)):
        """Delete a specific snapshot."""
        deleted = _get_snapshot_mgr().delete_snapshot(snapshot_id)
        if not deleted:
            raise HTTPException(404, f"Snapshot #{snapshot_id} not found")
        return {"status": "deleted", "snapshot_id": snapshot_id}

    @app.get("/snapshots/diff/{a}/{b}", tags=["Snapshots"])
    async def diff_snapshots(a: int = Path(ge=1), b: int = Path(ge=1)):
        """Compare two snapshots."""
        snap_mgr = _get_snapshot_mgr()
        sa = snap_mgr.load_snapshot(a)
        sb = snap_mgr.load_snapshot(b)
        if not sa or not sb:
            raise HTTPException(404, "One or both snapshots not found")
        return SnapshotDiff.compare(sa, sb)

    @app.get("/timeline", tags=["Snapshots"])
    async def get_timeline():
        """Get identity timeline analysis."""
        model = _get_model()
        axioms = _get_axioms()
        storage = (model.storage if hasattr(model, 'storage') else None)
        from identity_app.storage import Storage
        return Timeline(_get_snapshot_mgr(), storage or Storage()).get_timeline()

    # ── Crisis ──────────────────────────────────────────────────

    @app.get("/crisis", response_model=CrisisStateResponse, tags=["Crisis"])
    async def get_crisis_status():
        """Get current crisis status."""
        monitor = _get_crisis_monitor()
        status = monitor.get_status()
        return CrisisStateResponse(
            active=status.get("active", False),
            severity=status.get("severity", "none"),
            triggered_at=status.get("triggered_at", 0.0),
            triggered_by=status.get("triggered_by", ""),
            history=status.get("history", []),
        )

    @app.get("/crisis/check", response_model=HealthCheckResponse, tags=["Crisis"])
    async def check_health():
        """Run comprehensive health check."""
        model = _get_model()
        axioms = _get_axioms()
        monitor = _get_crisis_monitor()
        drift = DriftDetector(axioms, model)
        drift_report = drift.get_full_drift_report()
        health = monitor.check_health(axiom_system=axioms, drift_report=drift_report)
        return HealthCheckResponse(
            healthy=health["healthy"],
            severity=health["severity"],
            crisis_active=health["crisis_active"],
            violations=health["violations"],
            warnings=health["warnings"],
            metrics=health["metrics"],
        )

    @app.post("/crisis/resolve", tags=["Crisis"])
    async def resolve_crisis(req: ResolveCrisisRequest):
        """Resolve the current crisis."""
        return _get_crisis_monitor().resolve_crisis(req.resolution)

    @app.get("/crisis/history", tags=["Crisis"])
    async def get_crisis_history(limit: int = 20):
        """Get crisis history."""
        return _get_crisis_monitor().get_crisis_history(limit)

    @app.get("/crisis/predict", response_model=PredictionResponse, tags=["Crisis"])
    async def predict(horizon: int = Query(5, alias="horizon", ge=1, le=20)):
        """Get crisis prediction."""
        model = _get_model()
        predictor = CrisisPredictor(model)
        pred = predictor.predict(horizon)
        return PredictionResponse(
            overall_risk=pred["overall_risk"],
            risk_level=pred["risk_level"],
            high_risk_layers=pred["high_risk_layers"],
            predictions=pred["predictions"],
            recommendation=pred["recommendation"],
        )

    # ── Recovery Plans ──────────────────────────────────────────

    @app.get("/recovery", tags=["Recovery"])
    async def list_recovery_plans(status: Optional[str] = None):
        """List recovery plans."""
        model = _get_model()
        planner = RecoveryPlanner(model)
        return planner.list_plans(status)

    @app.get("/recovery/{plan_id}", tags=["Recovery"])
    async def get_recovery_plan(plan_id: str):
        """Get recovery plan details."""
        model = _get_model()
        planner = RecoveryPlanner(model)
        plan = planner.get_plan(plan_id)
        if not plan:
            raise HTTPException(404, f"Plan '{plan_id}' not found")
        return plan

    @app.get("/recovery/{plan_id}/progress", tags=["Recovery"])
    async def get_recovery_progress(plan_id: str):
        """Get recovery plan progress."""
        model = _get_model()
        planner = RecoveryPlanner(model)
        return planner.get_progress(plan_id)

    @app.post("/recovery/auto", tags=["Recovery"])
    async def auto_recover():
        """Automatically create and start a recovery plan."""
        model = _get_model()
        axioms = _get_axioms()
        monitor = _get_crisis_monitor()
        snap_mgr = _get_snapshot_mgr()

        health = monitor.check_health(axiom_system=axioms)
        snapshot = snap_mgr.take_snapshot(model, axiom_system=axioms,
                                          tag="pre-recovery", origin="auto_recovery")

        planner = RecoveryPlanner(model)
        plan = planner.auto_recover(health, snapshot.snapshot_id)
        if not plan:
            return {"message": "System is healthy, no recovery needed"}
        return {"message": "Recovery plan created and started", "plan": plan}

    # ── Scheduler ───────────────────────────────────────────────

    @app.get("/scheduler", tags=["Scheduler"])
    async def get_scheduler_status():
        """Get scheduler status."""
        model = _get_model()
        planner = RecoveryPlanner(model)
        scheduler = SnapshotScheduler(_get_snapshot_mgr())
        return scheduler.get_status()

    @app.put("/scheduler", tags=["Scheduler"])
    async def configure_scheduler(enabled: Optional[bool] = None,
                                  interval: Optional[int] = None,
                                  retention: Optional[int] = None):
        """Configure scheduler."""
        model = _get_model()
        scheduler = SnapshotScheduler(_get_snapshot_mgr())
        kwargs = {}
        if enabled is not None:
            kwargs["enabled"] = enabled
        if interval is not None:
            kwargs["interval_seconds"] = interval
        if retention is not None:
            kwargs["retention_count"] = retention
        return scheduler.configure(**kwargs)

    return app


# ── Direct Run ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
