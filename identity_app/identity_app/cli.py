"""CLI — Rich command-line interface for the Identity App.

Provides interactive terminal access to all identity operations:
status, check, snapshot, values, timeline, crisis, traits, beliefs, config, serve.
"""

import sys
import time
import json
import webbrowser
from pathlib import Path
from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn

from identity_app.core import SelfModel
from identity_app.values import ValueAxiomSystem, ValueAlignment, DriftDetector
from identity_app.snapshot import SnapshotManager, SnapshotDiff, Timeline, SnapshotScheduler
from identity_app.crisis import CrisisMonitor, CrisisPredictor, RecoveryPlanner
from identity_app.storage import Storage, StorageConfig


console = Console()
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


def _get_components(data_dir: str = "data"):
    """Initialize all identity components with a shared storage."""
    storage = Storage(StorageConfig(data_dir=data_dir))
    model = SelfModel(storage=storage)
    axioms = ValueAxiomSystem(model, storage=storage)
    alignment = ValueAlignment(axioms)
    drift = DriftDetector(axioms, model)
    snap_mgr = SnapshotManager(storage=storage)
    snapshot_diff = SnapshotDiff()
    timeline = Timeline(snap_mgr, storage=storage)
    scheduler = SnapshotScheduler(snap_mgr, storage=storage)
    crisis = CrisisMonitor(model, storage=storage)
    predictor = CrisisPredictor(model)
    recovery = RecoveryPlanner(model, storage=storage)
    return {
        "storage": storage,
        "model": model,
        "axioms": axioms,
        "alignment": alignment,
        "drift": drift,
        "snap_mgr": snap_mgr,
        "snapshot_diff": snapshot_diff,
        "timeline": timeline,
        "scheduler": scheduler,
        "crisis": crisis,
        "predictor": predictor,
        "recovery": recovery,
    }


# ── Utility ─────────────────────────────────────────────────────

def _fmt_time(ts: float) -> str:
    if ts <= 0:
        return "never"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _print_json(data: dict):
    console.print_json(json.dumps(data, indent=2, default=str))


# ── CLI Group ───────────────────────────────────────────────────

@click.group(context_settings=CONTEXT_SETTINGS)
@click.option("--data-dir", default="data", help="Data directory path", envvar="IDENTITY_DATA_DIR")
@click.pass_context
def main(ctx, data_dir):
    """🪪  Identity App — Expanded RSIS Identity Layer

    Manage self-modeling, value axioms, identity snapshots, crisis
    detection, and identity evolution.
    """
    ctx.ensure_object(dict)
    ctx.obj["data_dir"] = data_dir
    ctx.obj["components"] = _get_components(data_dir)


# ── Status ──────────────────────────────────────────────────────

@main.command()
@click.pass_context
def status(ctx):
    """Display current identity state summary."""
    c = ctx.obj["components"]
    model = c["model"]
    crisis = c["crisis"]
    axioms = c["axioms"]

    # Header
    console.print(f"\n[bold cyan]Identity Status[/] [dim]v{model.version}[/]")
    console.print(f"[dim]{'=' * 50}[/]\n")

    # Narrative
    narrative = model.get_narrative()
    if narrative:
        console.print(Panel(narrative[:120], title="📖 Current Narrative", border_style="blue"))
    else:
        console.print("[dim]No narrative set yet.[/]")

    # Layer Scores
    table = Table(title="Layer Scores", box=box.SIMPLE)
    table.add_column("Layer", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Trend", justify="center")
    table.add_column("Status")

    trends = model.get_all_trends()
    for lid in ["L1", "L2", "L3", "L4", "L5", "L6"]:
        score = model.get_layer_score(lid)
        trend = trends.get(lid, 0)
        trend_str = "↑" if trend > 2 else ("↓" if trend < -2 else "→")
        status_str = "✅" if score >= 30 else "⚠️" if score >= 15 else "🚨"
        table.add_row(lid, f"{score:.1f}", trend_str, status_str)
    console.print(table)

    # Traits
    profile = model.get_trait_profile()
    trait_table = Table(title="Identity Traits", box=box.SIMPLE)
    trait_table.add_column("Trait", style="green")
    trait_table.add_column("Score", justify="right")
    for name, score in sorted(profile.items()):
        bar = "█" * max(1, int(score / 10)) + "░" * max(0, 10 - max(1, int(score / 10)))
        trait_table.add_row(name.replace("_", " ").title(), f"{score:.0f}  {bar}")
    console.print(trait_table)

    # Value Axioms
    ax_table = Table(title="Value Axioms", box=box.SIMPLE)
    ax_table.add_column("Axiom", style="yellow")
    ax_table.add_column("Weight", justify="right")
    ax_table.add_column("Reinforcements", justify="right")
    for name, state in axioms.axioms.items():
        ax_table.add_row(name, f"{state.get_effective_weight():.1f}", str(state.reinforced_count))
    console.print(ax_table)

    # Crisis Status
    console.print(f"\n[bold]Crisis Status:[/] {crisis.get_health_summary()}")

    # Stats
    console.print(f"\n[dim]Snapshots: {model.snapshot_count} | "
                  f"Attempts: {model.total_attempts} | "
                  f"Success rate: {model.get_success_rate():.1f}% | "
                  f"Crises survived: {model.crisis_count}[/]")


# ── Check (Health) ──────────────────────────────────────────────

@main.command()
@click.option("--drift/--no-drift", default=True, help="Include drift analysis")
@click.option("--predict/--no-predict", default=True, help="Include crisis prediction")
@click.pass_context
def check(ctx, drift, predict):
    """Run comprehensive health check."""
    c = ctx.obj["components"]
    model = c["model"]
    axioms = c["axioms"]
    drift_detector = c["drift"]
    crisis = c["crisis"]
    predictor = c["predictor"]

    console.print("[bold cyan]Running Health Check...[/]\n")

    # Drift analysis
    drift_report = None
    if drift:
        drift_report = drift_detector.get_full_drift_report()

    # Health check
    health = crisis.check_health(axiom_system=axioms, drift_report=drift_report)

    # Display results
    if health["healthy"]:
        console.print("[bold green]✅ SYSTEM HEALTHY[/]")
    else:
        severity_colors = {"info": "yellow", "warning": "orange1", "critical": "red", "catastrophic": "bold red"}
        color = severity_colors.get(health["severity"], "red")
        console.print(f"[{color}]🚨 CRISIS: {health['severity'].upper()}[/]")

    console.print(f"\nSeverity: [bold]{health['severity']}[/]")
    console.print(f"Active crisis: {health['crisis_active']}")

    if health["violations"]:
        console.print("\n[red]Violations:[/]")
        for v in health["violations"]:
            console.print(f"  • {v}")

    if health["warnings"]:
        console.print("\n[yellow]Warnings:[/]")
        for w in health["warnings"]:
            console.print(f"  • {w}")

    # Prediction
    if predict:
        prediction = predictor.predict()
        console.print(f"\n[bold]Crisis Prediction:[/] Risk level [bold]{prediction['risk_level']}[/] "
                      f"(score: {prediction['overall_risk']:.2f})")
        if prediction["high_risk_layers"]:
            console.print(f"[yellow]High risk layers: {', '.join(prediction['high_risk_layers'])}[/]")

    # Drift
    if drift_report:
        console.print(f"\n[bold]Drift:[/] {'⚠️ Drifting' if drift_report['overall_drifting'] else '✅ Stable'}")

    # Metrics
    m = health["metrics"]
    console.print(f"\n[dim]Pass rate: {m['pass_rate']:.0f}% ({m['total_checks']} checks)[/]")


# ── Snapshot Commands ───────────────────────────────────────────

@main.group()
def snapshot():
    """Manage identity snapshots."""
    pass


@snapshot.command("take")
@click.option("--tag", default="", help="Optional tag for the snapshot")
@click.option("--notes", default="", help="Optional notes")
@click.pass_context
def snapshot_take(ctx, tag, notes):
    """Take a new identity snapshot."""
    c = ctx.obj["components"]
    snap_mgr = c["snap_mgr"]
    model = c["model"]
    axioms = c["axioms"]

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="Capturing identity state...", total=None)
        snapshot = snap_mgr.take_snapshot(model, axiom_system=axioms, tag=tag, notes=notes, origin="manual")

    console.print(f"[green]✅ Snapshot #{snapshot.snapshot_id} captured[/]")
    console.print(f"  Tag: {snapshot.tag or '(none)'}")
    console.print(f"  Time: {_fmt_time(snapshot.timestamp)}")
    console.print(f"  Narr: {snapshot.narrative[:60]}..." if len(snapshot.narrative) > 60 else f"  Narr: {snapshot.narrative}")


@snapshot.command("list")
@click.option("--limit", default=20, help="Number of snapshots to show")
@click.pass_context
def snapshot_list(ctx, limit):
    """List identity snapshots."""
    c = ctx.obj["components"]
    snap_mgr = c["snap_mgr"]

    snapshots = snap_mgr.list_snapshots(limit)
    if not snapshots:
        console.print("[yellow]No snapshots yet.[/]")
        return

    table = Table(title=f"Snapshots (last {len(snapshots)})", box=box.SIMPLE)
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Time", style="dim")
    table.add_column("Tag")
    table.add_column("Origin", justify="center")
    table.add_column("L1", justify="right")
    table.add_column("L2", justify="right")
    table.add_column("L3", justify="right")
    table.add_column("L4", justify="right")
    table.add_column("L5", justify="right")
    table.add_column("L6", justify="right")

    for s in reversed(snapshots):
        scores = s.get("layer_scores_summary", {})
        table.add_row(
            str(s["snapshot_id"]),
            _fmt_time(s["timestamp"]),
            s.get("tag", "") or "—",
            "🔄" if "auto" in s.get("tag", "") else "👤",
            f'{scores.get("L1", 0):.0f}',
            f'{scores.get("L2", 0):.0f}',
            f'{scores.get("L3", 0):.0f}',
            f'{scores.get("L4", 0):.0f}',
            f'{scores.get("L5", 0):.0f}',
            f'{scores.get("L6", 0):.0f}',
        )
    console.print(table)


@snapshot.command("show")
@click.argument("snapshot_id", type=int)
@click.pass_context
def snapshot_show(ctx, snapshot_id):
    """Show details of a specific snapshot."""
    c = ctx.obj["components"]
    snap_mgr = c["snap_mgr"]

    snapshot = snap_mgr.load_snapshot(snapshot_id)
    if not snapshot:
        console.print(f"[red]Snapshot #{snapshot_id} not found.[/]")
        return

    console.print(f"\n[bold cyan]Snapshot #{snapshot.snapshot_id}[/]")
    console.print(f"  Time:     {_fmt_time(snapshot.timestamp)}")
    console.print(f"  Version:  {snapshot.version}")
    console.print(f"  Tag:      {snapshot.tag or '(none)'}")
    console.print(f"  Origin:   {snapshot.origin}")
    console.print(f"  Crisis:   {'🚨 Active' if snapshot.crisis_active else '✅ Normal'}")
    console.print(f"  Notes:    {snapshot.notes or '(none)'}")
    console.print(f"  Narrative: {snapshot.narrative[:100]}" if len(snapshot.narrative) > 100 else f"  Narrative: {snapshot.narrative}")

    # Layer scores
    ls_table = Table(title="Layer Scores", box=box.SIMPLE)
    ls_table.add_column("Layer", style="cyan")
    ls_table.add_column("Score", justify="right")
    for lid, ldata in sorted(snapshot.layer_scores.items()):
        ls_table.add_row(lid, f'{ldata.get("score", 0):.1f}')
    console.print(ls_table)


@snapshot.command("diff")
@click.argument("snapshot_a", type=int)
@click.argument("snapshot_b", type=int)
@click.pass_context
def snapshot_diff(ctx, snapshot_a, snapshot_b):
    """Compare two snapshots."""
    c = ctx.obj["components"]
    snap_mgr = c["snap_mgr"]

    a = snap_mgr.load_snapshot(snapshot_a)
    b = snap_mgr.load_snapshot(snapshot_b)
    if not a or not b:
        console.print("[red]One or both snapshots not found.[/]")
        return

    diff = SnapshotDiff.compare(a, b)

    console.print(f"\n[bold cyan]Diff: #{snapshot_a} → #{snapshot_b}[/]")
    console.print(f"  Time span: {diff['time_span']:.0f}s")
    console.print(f"  Version:   {diff['version_change']}")

    # Layer score changes
    ls_table = Table(title="Layer Score Changes", box=box.SIMPLE)
    ls_table.add_column("Layer", style="cyan")
    ls_table.add_column("From", justify="right")
    ls_table.add_column("To", justify="right")
    ls_table.add_column("Change", justify="right")
    ls_table.add_column("Direction")
    for lid, ld in sorted(diff["layer_scores"].items()):
        direction_icon = "↑" if ld["direction"] == "improved" else ("↓" if ld["direction"] == "declined" else "→")
        color = "green" if ld["direction"] == "improved" else ("red" if ld["direction"] == "declined" else "dim")
        ls_table.add_row(lid, f'{ld["from"]:.1f}', f'{ld["to"]:.1f}',
                         f'{ld["change"]:+.1f}', f"[{color}]{direction_icon}")
    console.print(ls_table)

    # Summary
    if diff["summary"]:
        console.print(f"\n[bold]Summary:[/] {diff['summary']}")


@snapshot.command("prune")
@click.option("--keep", default=50, help="Number of snapshots to keep")
@click.pass_context
def snapshot_prune(ctx, keep):
    """Remove old snapshots beyond keep limit."""
    c = ctx.obj["components"]
    snap_mgr = c["snap_mgr"]
    removed = snap_mgr.prune(keep)
    console.print(f"[green]Pruned {removed} old snapshots, keeping {keep}.[/]")


# ── Values ──────────────────────────────────────────────────────

@main.command()
@click.pass_context
def values(ctx):
    """Show value axiom system status."""
    c = ctx.obj["components"]
    axioms = c["axioms"]
    alignment = c["alignment"]

    console.print("[bold cyan]Value Axiom System[/]\n")

    table = Table(box=box.SIMPLE)
    table.add_column("Axiom", style="yellow")
    table.add_column("Category")
    table.add_column("Weight", justify="right")
    table.add_column("Reinforced", justify="right")
    table.add_column("Confidence", justify="right")
    table.add_column("Last Reinforced")

    for name in axioms.CORE_AXIOMS:
        state = axioms.axioms[name]
        meta = axioms.AXIOM_METADATA.get(name, {})
        table.add_row(
            name,
            meta.get("category", ""),
            f"{state.get_effective_weight():.1f}",
            str(state.reinforced_count),
            f"{state.confidence:.0%}",
            _fmt_time(state.last_reinforced),
        )
    console.print(table)

    # Balance score
    console.print(f"\nBalance Score: [bold]{axioms.get_balance_score():.1f}%[/]")
    console.print(f"Strongest: {', '.join(f'{n}({w:.1f})' for n, w in axioms.get_strongest_axioms(3))}")
    console.print(f"Weakest:  {', '.join(f'{n}({w:.1f})' for n, w in axioms.get_weakest_axioms(3))}")

    # Alignment
    console.print("\n[bold]Layer Alignment:[/]")
    align = alignment.get_overall_alignment()
    for lid, score in sorted(align["per_layer"].items()):
        bar = "█" * max(1, int(score / 10))
        console.print(f"  {lid}: {score:.1f}  {bar}")
    console.print(f"  [bold]Overall: {align['overall']:.1f}[/]")


# ── Timeline ────────────────────────────────────────────────────

@main.command()
@click.pass_context
def timeline(ctx):
    """Show identity snapshot timeline."""
    c = ctx.obj["components"]
    timeline = c["timeline"]

    tl = timeline.get_timeline()
    console.print(f"[bold cyan]Identity Timeline[/]")
    console.print(f"  Snapshots: {tl['snapshot_count']}")
    console.print(f"  Time span: {tl.get('time_span', 'N/A')}")
    console.print(f"  Summary: {tl.get('summary', '')}")

    if tl.get("trends"):
        console.print("\n[bold]Trends:[/]")
        trend_table = Table(box=box.SIMPLE)
        trend_table.add_column("Layer", style="cyan")
        trend_table.add_column("First", justify="right")
        trend_table.add_column("Last", justify="right")
        trend_table.add_column("Min", justify="right")
        trend_table.add_column("Max", justify="right")
        trend_table.add_column("Avg", justify="right")
        trend_table.add_column("Direction")
        for lid, t in sorted(tl["trends"].items()):
            direction_icon = "↑" if t["trend_direction"] == "improving" else ("↓" if t["trend_direction"] == "declining" else "→")
            trend_table.add_row(
                lid, f'{t["first"]:.1f}', f'{t["last"]:.1f}',
                f'{t["min"]:.1f}', f'{t["max"]:.1f}', f'{t["avg"]:.1f}',
                direction_icon,
            )
        console.print(trend_table)

    if tl.get("milestones"):
        console.print(f"\n[bold]Milestones ({len(tl['milestones'])}):[/]")
        for m in tl["milestones"]:
            tag_str = f" ({m['tag']})" if m.get("tag") else ""
            console.print(f"  • Snapshot #{m['snapshot_id']}{tag_str}: {', '.join(m['reasons'])}")


# ── Traits ──────────────────────────────────────────────────────

@main.command()
@click.pass_context
def traits(ctx):
    """Display identity traits."""
    c = ctx.obj["components"]
    model = c["model"]

    console.print("[bold cyan]Identity Traits[/]\n")

    table = Table(box=box.SIMPLE)
    table.add_column("Trait", style="green")
    table.add_column("Score", justify="right")
    table.add_column("Confidence", justify="right")
    table.add_column("Updated")

    for name in sorted(model.traits.keys()):
        trait = model.traits[name]
        table.add_row(
            name.replace("_", " ").title(),
            f"{trait.score:.0f}",
            f"{trait.confidence:.0%}",
            _fmt_time(trait.last_updated),
        )
    console.print(table)


# ── Beliefs ─────────────────────────────────────────────────────

@main.command()
@click.option("--category", default=None, help="Filter by category (core, derived, operational, aspirational)")
@click.option("--min-confidence", default=0.0, type=float, help="Minimum confidence filter")
@click.pass_context
def beliefs(ctx, category, min_confidence):
    """Display active beliefs."""
    c = ctx.obj["components"]
    model = c["model"]

    console.print("[bold cyan]Belief System[/]\n")
    beliefs_list = list(model.beliefs.values())
    if category:
        beliefs_list = [b for b in beliefs_list if b.category == category]
    beliefs_list = [b for b in beliefs_list if b.active and b.confidence >= min_confidence]

    if not beliefs_list:
        console.print("[dim]No beliefs match criteria.[/]")
        return

    table = Table(box=box.SIMPLE)
    table.add_column("Belief", style="bold")
    table.add_column("Statement")
    table.add_column("Confidence", justify="right")
    table.add_column("Category")
    table.add_column("Evidence", justify="right")

    for b in sorted(beliefs_list, key=lambda x: x.confidence, reverse=True):
        table.add_row(
            b.name,
            b.statement[:50] + "..." if len(b.statement) > 50 else b.statement,
            f"{b.confidence:.0%}",
            b.category,
            str(len(b.evidence)),
        )
    console.print(table)


# ── Crisis Commands ─────────────────────────────────────────────

@main.group()
def crisis():
    """Crisis monitoring and management."""
    pass


@crisis.command("status")
@click.pass_context
def crisis_status(ctx):
    """Show current crisis status."""
    c = ctx.obj["components"]
    crisis = c["crisis"]
    status = crisis.get_status()

    console.print("[bold cyan]Crisis Status[/]\n")
    if status.get("active"):
        console.print(f"  State:     [red]🚨 ACTIVE ({status.get('severity', 'unknown').upper()})[/]")
        console.print(f"  Triggered: {_fmt_time(status.get('triggered_at', 0))}")
        console.print(f"  By:        {status.get('triggered_by', 'unknown')}")
    else:
        console.print("  State:     [green]✅ Inactive[/]")

    history = crisis.get_crisis_history(5)
    if history:
        console.print("\n[bold]Recent History:[/]")
        for h in history:
            console.print(f"  • {h.get('severity', '?')} crisis triggered by '{h.get('triggered_by', '')[:40]}' "
                          f"→ resolved at {_fmt_time(h.get('resolved_at', 0))}")


@crisis.command("resolve")
@click.argument("resolution", default="Manual resolution via CLI")
@click.pass_context
def crisis_resolve(ctx, resolution):
    """Resolve the current crisis."""
    c = ctx.obj["components"]
    crisis = c["crisis"]
    result = crisis.resolve_crisis(resolution)
    console.print(f"[green]✅ Crisis resolved: {result.get('resolution', '')}[/]")


@crisis.command("history")
@click.option("--limit", default=20, help="Number of entries")
@click.pass_context
def crisis_history(ctx, limit):
    """Show crisis history."""
    c = ctx.obj["components"]
    crisis = c["crisis"]
    history = crisis.get_crisis_history(limit)

    if not history:
        console.print("[dim]No crisis history.[/]")
        return

    table = Table(box=box.SIMPLE)
    table.add_column("Severity")
    table.add_column("Triggered")
    table.add_column("Triggered By")
    table.add_column("Resolved")
    for h in history:
        table.add_row(
            h.get("severity", "?"),
            _fmt_time(h.get("triggered_at", 0)),
            h.get("triggered_by", "")[:40],
            _fmt_time(h.get("resolved_at", 0)),
        )
    console.print(table)


@crisis.command("predict")
@click.option("--steps", default=5, help="Prediction horizon steps")
@click.pass_context
def crisis_predict(ctx, steps):
    """Show crisis prediction."""
    c = ctx.obj["components"]
    predictor = c["predictor"]
    prediction = predictor.predict(steps)

    console.print(f"[bold cyan]Crisis Prediction[/] (horizon: {steps} steps)")
    console.print(f"  Risk:      [bold]{prediction['risk_level'].upper()}[/] ({prediction['overall_risk']:.2f})")
    console.print(f"  At risk:   {', '.join(prediction['high_risk_layers']) if prediction['high_risk_layers'] else 'none'}")
    console.print(f"  Advisory:  {prediction['recommendation']}")

    pred_table = Table(box=box.SIMPLE)
    pred_table.add_column("Layer", style="cyan")
    pred_table.add_column("Current", justify="right")
    pred_table.add_column("Trend", justify="right")
    pred_table.add_column("Projected", justify="right")
    pred_table.add_column("Risk", justify="right")
    for lid, p in sorted(prediction["predictions"].items()):
        pred_table.add_row(
            lid, f'{p["current"]:.1f}', f'{p["trend"]:+.1f}',
            f'{p["projected"]:.1f}', f'{p["risk"]:.2f}',
        )
    console.print(pred_table)


# ── Config ──────────────────────────────────────────────────────

@main.group()
def config():
    """Manage configuration."""
    pass


@config.command("show")
@click.pass_context
def config_show(ctx):
    """Show scheduler configuration."""
    c = ctx.obj["components"]
    scheduler = c["scheduler"]
    status = scheduler.get_status()

    console.print("[bold cyan]Scheduler Configuration[/]\n")
    console.print(f"  Enabled:        {'✅' if status['enabled'] else '❌'} {status['enabled']}")
    console.print(f"  Interval:       {status['interval_seconds']}s")
    console.print(f"  Retention:      {status['retention_count']} snapshots")
    console.print(f"  Last run:       {_fmt_time(status['last_run'])}")
    console.print(f"  Next run:       {_fmt_time(status['next_run'])}")
    console.print(f"  Due now:        {'✅' if status['due'] else '❌'}")
    console.print(f"  Triggers:       {status['conditional_triggers']}")


@config.command("set")
@click.option("--enabled", type=bool, default=None, help="Enable/disable scheduler")
@click.option("--interval", type=int, default=None, help="Interval in seconds")
@click.option("--retention", type=int, default=None, help="Snapshots to keep")
@click.pass_context
def config_set(ctx, enabled, interval, retention):
    """Update scheduler configuration."""
    c = ctx.obj["components"]
    scheduler = c["scheduler"]
    kwargs = {}
    if enabled is not None:
        kwargs["enabled"] = enabled
    if interval is not None:
        kwargs["interval_seconds"] = interval
    if retention is not None:
        kwargs["retention_count"] = retention
    scheduler.configure(**kwargs)
    console.print("[green]✅ Configuration updated[/]")


# ── Serve ───────────────────────────────────────────────────────

@main.command()
@click.option("--port", default=8000, help="Port for API server")
@click.option("--host", default="127.0.0.1", help="Host for API server")
@click.pass_context
def serve(ctx, port, host):
    """Start the REST API server."""
    console.print(f"[bold cyan]Starting Identity API server on {host}:{port}...[/]")
    console.print("[dim]Press Ctrl+C to stop[/]\n")

    import uvicorn
    from identity_app.api import create_app

    # Pre-initialize components so the API uses the same data
    c = ctx.obj["components"]
    app = create_app(c)

    uvicorn.run(app, host=host, port=port, log_level="info")


# ── Dashboard ───────────────────────────────────────────────────

@main.command()
@click.option("--port", default=8500, help="Port for dashboard")
@click.option("--host", default="127.0.0.1", help="Host for dashboard")
@click.pass_context
def dashboard(ctx, port, host):
    """Start the web dashboard."""
    console.print(f"[bold cyan]Starting Identity Dashboard on {host}:{port}...[/]")
    console.print("[dim]Press Ctrl+C to stop[/]\n")

    import uvicorn
    from identity_app.dashboard import create_dashboard_app

    c = ctx.obj["components"]
    app = create_dashboard_app(c)

    webbrowser.open(f"http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


# ── JSON output ─────────────────────────────────────────────────

@main.command()
@click.pass_context
def json_status(ctx):
    """Output full identity state as JSON."""
    c = ctx.obj["components"]
    model = c["model"]
    print(json.dumps(model.to_dict(), indent=2, default=str))


# ── Entry ───────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
