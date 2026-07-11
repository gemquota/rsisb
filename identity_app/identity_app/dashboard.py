"""Dashboard — Web dashboard for the Identity App.

Provides a real-time visualization of identity state using FastAPI
with Jinja2 templates for server-side rendering.
"""

import time
import json
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from identity_app.core import SelfModel
from identity_app.values import ValueAxiomSystem, ValueAlignment, DriftDetector
from identity_app.snapshot import SnapshotManager, SnapshotDiff, Timeline, SnapshotScheduler
from identity_app.crisis import CrisisMonitor, CrisisPredictor, RecoveryPlanner


# ── Inline HTML Dashboard ───────────────────────────────────────
# (Self-contained single-page dashboard to avoid template file dependencies)

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Identity Dashboard</title>
<style>
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --yellow: #d29922;
    --red: #f85149;
    --orange: #db6d28;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
    padding: 20px;
  }
  .header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 16px 0; border-bottom: 1px solid var(--border); margin-bottom: 24px;
  }
  .header h1 { font-size: 1.5rem; display: flex; align-items: center; gap: 8px; }
  .header .version { color: var(--text-dim); font-size: 0.85rem; }
  .header .crisis-badge {
    padding: 4px 12px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;
  }
  .crisis-badge.active { background: var(--red); color: white; }
  .crisis-badge.inactive { background: var(--green); color: white; }

  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 20px; }
  .card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px;
  }
  .card h2 { font-size: 1rem; margin-bottom: 12px; color: var(--accent); }
  .card h3 { font-size: 0.85rem; margin: 8px 0 4px; color: var(--text-dim); }

  .score-bar { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
  .score-bar .label { width: 120px; font-weight: 600; font-size: 0.8rem; }
  .score-bar .bar-track { flex: 1; height: 18px; background: #21262d; border-radius: 4px; overflow: hidden; }
  .score-bar .bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
  .score-bar .value { width: 30px; text-align: right; font-size: 0.75rem; font-variant-numeric: tabular-nums; }

  .trait-bar .bar-fill { background: var(--accent); }
  .layer-bar .bar-fill { background: var(--green); }
  .axiom-bar .bar-fill { background: var(--yellow); }

  .narrative-box {
    background: #0d1117; border: 1px solid var(--border); border-radius: 6px;
    padding: 12px; font-style: italic; color: var(--text-dim); font-size: 0.9rem; min-height: 60px;
  }

  .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; text-align: center; }
  .stat { padding: 8px; }
  .stat .num { font-size: 1.5rem; font-weight: 700; }
  .stat .lbl { font-size: 0.75rem; color: var(--text-dim); }

  .timeline-list { max-height: 300px; overflow-y: auto; }
  .tl-item {
    display: flex; justify-content: space-between; align-items: center;
    padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 0.85rem;
  }
  .tl-item:last-child { border-bottom: none; }
  .tl-item .tl-time { color: var(--text-dim); font-size: 0.75rem; }
  .tl-item .tl-tag { color: var(--accent); }
  .tl-item .tl-scores { display: flex; gap: 6px; }

  .milestone {
    background: linear-gradient(135deg, rgba(88,166,255,0.1), rgba(63,185,80,0.05));
    border: 1px solid var(--accent); border-radius: 6px; padding: 8px 12px; margin: 4px 0;
    font-size: 0.85rem;
  }
  .milestone .reason { color: var(--accent); }

  .refresh-bar {
    display: flex; justify-content: flex-end; align-items: center; gap: 12px;
    padding: 12px 0; font-size: 0.85rem; color: var(--text-dim);
  }
  .refresh-bar button {
    background: var(--surface); color: var(--text); border: 1px solid var(--border);
    padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 0.85rem;
  }
  .refresh-bar button:hover { border-color: var(--accent); }
  .auto-refresh { display: flex; align-items: center; gap: 6px; }

  .status-dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px;
  }
  .status-dot.green { background: var(--green); }
  .status-dot.yellow { background: var(--yellow); }
  .status-dot.red { background: var(--red); }

  .subcard {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; padding: 10px 12px;
  }
  .axiom-tag {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 0.75rem; margin: 2px;
    background: var(--surface); border: 1px solid var(--border); color: var(--accent);
  }
  .drift-warning {
    background: rgba(210, 153, 34, 0.1); border: 1px solid var(--yellow);
    border-radius: 6px; padding: 10px; margin: 8px 0; font-size: 0.85rem;
  }

  @media (max-width: 600px) {
    .grid { grid-template-columns: 1fr; }
    .stat-grid { grid-template-columns: repeat(2, 1fr); }
  }
  .supercard {
    margin-bottom: 24px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
  }
  .supercard-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding-bottom: 12px;
    margin-bottom: 16px;
    border-bottom: 1px solid var(--border);
  }
  .supercard-header h2 {
    font-size: 1.1rem;
    color: var(--accent);
    margin: 0;
  }
  .supercard-header .sc-count {
    font-size: 0.75rem;
    color: var(--text-dim);
    margin-left: auto;
  }
  .supercard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 12px;
  }

  /* ── Drag-and-Drop ── */
  .card {
    transition: transform 0.15s, box-shadow 0.15s;
    cursor: grab;
  }
  .card.dragging { opacity: 0.4; transform: scale(0.97); }
  .card.drag-over { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent); }
  .drop-zone.drag-over-zone {
    outline: 2px dashed var(--accent); outline-offset: 4px;
    border-radius: 8px; min-height: 60px;
    background: rgba(88, 166, 255, 0.05);
  }
  .card .edit-btn, .supercard-header .edit-btn {
    display: none; float: right; background: none; border: none;
    color: var(--text-dim); cursor: pointer; font-size: 0.7rem;
    padding: 0 4px; line-height: 1;
  }
  .card:hover .edit-btn, .supercard-header:hover .edit-btn { display: inline-block; }
  .card .edit-btn:hover, .supercard-header .edit-btn:hover { color: var(--accent); }
  .supercard-header .edit-btn { font-size: 0.75rem; margin-left: 6px; }
  .rename-input {
    background: #0d1117; border: 1px solid var(--accent); border-radius: 4px;
    color: var(--text); font-size: inherit; font-family: inherit;
    padding: 2px 6px; width: auto; min-width: 100px;
  }
  .layout-bar {
    display: flex; justify-content: flex-end; align-items: center; gap: 8px;
    padding: 8px 0; font-size: 0.8rem; color: var(--text-dim);
  }
  .layout-bar button {
    background: var(--surface); color: var(--text); border: 1px solid var(--border);
    padding: 4px 12px; border-radius: 5px; cursor: pointer; font-size: 0.8rem;
  }
  .layout-bar button:hover { border-color: var(--accent); }

  /* ── Card Levels ── */
  .card[data-level="subcard"] { border-left: 3px solid var(--accent); margin-left: 12px; }
  .card[data-level="partcard"] { border-left: 3px solid var(--yellow); margin-left: 24px; background: rgba(210,153,34,0.04); }
  .card[data-level="microcard"] { border-left: 3px solid var(--green); margin-left: 36px; background: rgba(63,185,80,0.04); font-size: 0.9rem; }
  .card[data-level="subcard"] h2 { font-size: 0.9rem; }
  .card[data-level="partcard"] h2 { font-size: 0.85rem; }
  .card[data-level="microcard"] h2 { font-size: 0.8rem; }
  .nest-indicator { font-size: 0.65rem; color: var(--text-dim); margin-left: 4px; font-weight: normal; }

  /* ── Card Sizes ── */
  .card[data-size="s"] { padding: 8px; }
  .card[data-size="s"] h2 { font-size: 0.85rem; margin-bottom: 6px; }
  .card[data-size="s"] .card-content { font-size: 0.75rem; }
  .card[data-size="l"] { padding: 20px; }
  .card[data-size="l"] h2 { font-size: 1.1rem; margin-bottom: 16px; }
  .card[data-size="xl"] { padding: 24px; grid-column: 1 / -1; }
  .card[data-size="xl"] h2 { font-size: 1.2rem; margin-bottom: 20px; }

  /* ── Card Controls Footer ── */
  .card-footer {
    display: none; justify-content: flex-end; gap: 4px;
    padding-top: 6px; margin-top: 8px; border-top: 1px solid var(--border);
    font-size: 0.7rem;
  }
  .card:hover .card-footer { display: flex; }
  .card-footer button {
    background: none; border: 1px solid var(--border); border-radius: 3px;
    color: var(--text-dim); cursor: pointer; padding: 1px 6px; font-size: 0.7rem;
    line-height: 1.4;
  }
  .card-footer button:hover { border-color: var(--accent); color: var(--accent); }
  .card-footer .del-btn:hover { border-color: var(--red); color: var(--red); }
  .card-footer .del-btn { color: var(--red); }

  /* ── Supercard Controls ── */
  .supercard-footer {
    display: flex; justify-content: flex-end; gap: 6px;
    padding-top: 10px; margin-top: 8px; font-size: 0.8rem;
  }
  .supercard-footer button {
    background: var(--surface); border: 1px solid var(--border); border-radius: 5px;
    color: var(--text); cursor: pointer; padding: 3px 10px; font-size: 0.8rem;
  }
  .supercard-footer button:hover { border-color: var(--accent); color: var(--accent); }

  /* ── Column Picker ── */
  .col-picker {
    display: inline-flex; align-items: center; gap: 3px;
    margin-left: 10px; font-size: 0.7rem; color: var(--text-dim);
  }
  .col-picker button {
    background: none; border: 1px solid var(--border); border-radius: 3px;
    color: var(--text-dim); cursor: pointer; padding: 1px 5px; font-size: 0.65rem;
    line-height: 1.3; min-width: 20px;
  }
  .col-picker button:hover { border-color: var(--accent); color: var(--accent); }
  .col-picker button.active { border-color: var(--accent); color: var(--accent); background: rgba(88,166,255,0.1); }
  .grid-cols-1 { grid-template-columns: 1fr !important; }
  .grid-cols-2 { grid-template-columns: repeat(2, 1fr) !important; }
  .grid-cols-3 { grid-template-columns: repeat(3, 1fr) !important; }
  .grid-cols-4 { grid-template-columns: repeat(4, 1fr) !important; }
  .grid-cols-5 { grid-template-columns: repeat(5, 1fr) !important; }
  .grid-cols-6 { grid-template-columns: repeat(6, 1fr) !important; }

  /* ── Card Content Editor ── */
  .card-content-editor {
    background: #0d1117; border: 1px solid var(--border); border-radius: 4px;
    color: var(--text); font-size: 0.85rem; padding: 8px; width: 100%;
    min-height: 40px; font-family: inherit; resize: vertical;
    margin-top: 4px;
  }
  .card-content-editor:focus { border-color: var(--accent); outline: none; }

  /* ── Create Supercard ── */
  .create-supercard-bar {
    display: flex; justify-content: center; gap: 8px; padding: 16px 0;
  }
  .create-supercard-bar button {
    background: var(--surface); border: 1px dashed var(--border); border-radius: 8px;
    color: var(--text-dim); cursor: pointer; padding: 10px 24px; font-size: 0.9rem;
  }
  .create-supercard-bar button:hover { border-color: var(--accent); color: var(--accent); background: rgba(88,166,255,0.05); }

  /* ── Empty card placeholder ── */
  .card-empty {
    text-align: center; padding: 20px; color: var(--text-dim); font-size: 0.85rem;
  }

  /* ── Drop zone for nesting ── */
  .drop-subcard-zone {
    min-height: 20px; border: 1px dashed transparent; border-radius: 4px;
    margin-top: 4px; padding: 2px;
  }
  .drop-subcard-zone.drag-over-zone {
    border-color: var(--accent); background: rgba(88,166,255,0.05);
    min-height: 40px;
  }

  /* ── Global Columns ── */
  body.global-cols-1 .supercard-grid { grid-template-columns: 1fr !important; }
  body.global-cols-2 .supercard-grid { grid-template-columns: repeat(2, 1fr) !important; }
  body.global-cols-3 .supercard-grid { grid-template-columns: repeat(3, 1fr) !important; }
  body.global-cols-4 .supercard-grid { grid-template-columns: repeat(4, 1fr) !important; }
  .global-col-picker button.active { border-color: var(--accent) !important; color: var(--accent) !important; background: rgba(88,166,255,0.1); }

  /* ── Conditional Column Pickers ── */
  .supercard:not(.has-cards) .sc-col-picker { display: none !important; }
  .card:not(.has-subcards) .card-col-picker { display: none !important; }
  .sc-col-picker button.active, .card-col-picker button.active { border-color: var(--accent) !important; color: var(--accent) !important; background: rgba(88,166,255,0.1); }
  /* Zone column classes */
  .zone-cols-1 { grid-template-columns: 1fr !important; }
  .zone-cols-2 { grid-template-columns: repeat(2, 1fr) !important; }
  .zone-cols-3 { grid-template-columns: repeat(3, 1fr) !important; }
  .zone-cols-4 { grid-template-columns: repeat(4, 1fr) !important; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>🪪 Identity Dashboard <span class="version" id="version">v—</span> <span style="font-size:0.7rem;color:var(--text-dim);font-weight:400">semver</span></h1>
  </div>
  <div>
    <span class="crisis-badge inactive" id="crisisBadge">✅ Healthy</span>
  </div>
</div>

<div class="refresh-bar">
  <div class="auto-refresh">
    <input type="checkbox" id="autoRefresh" checked>
    <label for="autoRefresh">Auto-refresh (10s)</label>
  </div>
  <button onclick="loadAll()">⟳ Refresh Now</button>
  <span id="lastUpdated">—</span><span class="global-col-picker" style="margin-left:12px;font-size:0.8rem;color:var(--text-dim);display:inline-flex;align-items:center;gap:4px">
  Columns:
  <button onclick="setGlobalColumns(1)" data-gcols="1" style="background:none;border:1px solid var(--border);border-radius:3px;color:var(--text-dim);cursor:pointer;padding:1px 5px;font-size:0.7rem;min-width:20px">1</button>
  <button onclick="setGlobalColumns(2)" data-gcols="2" class="active" style="background:none;border:1px solid var(--accent);border-radius:3px;color:var(--accent);cursor:pointer;padding:1px 5px;font-size:0.7rem;min-width:20px">2</button>
  <button onclick="setGlobalColumns(3)" data-gcols="3" style="background:none;border:1px solid var(--border);border-radius:3px;color:var(--text-dim);cursor:pointer;padding:1px 5px;font-size:0.7rem;min-width:20px">3</button>
  <button onclick="setGlobalColumns(4)" data-gcols="4" style="background:none;border:1px solid var(--border);border-radius:3px;color:var(--text-dim);cursor:pointer;padding:1px 5px;font-size:0.7rem;min-width:20px">4</button>
</span>
</div>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- SUPERCARD 1: 🧬 Self Model                                   -->
<!-- Cards: Self-Concept, Self Image, Self Perception, Self-Description -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<div class="supercard" data-supercard-id="self-model">
  <div class="supercard-header">
    <h2>🧬 Self Model <button class="edit-btn" title="Rename supercard" onclick="startRename(this,'supercard')">✎</button></h2>
    <span class="sc-count" style="display:inline-flex;align-items:center;gap:8px">4 cards</span><span class="sc-col-picker" data-sc-id="self-model" style="display:inline-flex;font-size:0.7rem;color:var(--text-dim);margin-left:4px;align-items:center;gap:2px">| Col: <button onclick="setZoneCols('self-model',1,'sc')" data-col="1" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">1</button><button onclick="setZoneCols('self-model',2,'sc')" data-col="2" class="active" style="background:none;border:1px solid var(--accent);border-radius:2px;color:var(--accent);cursor:pointer;padding:0 4px;font-size:0.65rem">2</button><button onclick="setZoneCols('self-model',3,'sc')" data-col="3" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">3</button><button onclick="setZoneCols('self-model',4,'sc')" data-col="4" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">4</button></span>
  </div>
  <div class="supercard-grid drop-zone" data-drop-zone="true">
    <!-- Self-Concept -->
    <div class="card" data-card-id="self-concept" draggable="true">
      <h2>🎯 Self-Concept <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="selfConceptContent">
        <div id="scSummary" style="font-size:0.85rem;line-height:1.6;color:var(--text);font-style:italic;margin-bottom:12px">Loading...</div>
        <div>
          <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">Core Beliefs
  <div class="supercard-footer">
    <button onclick="addCard('self-model')" title="Add a new card">➕ Add Card</button>
    <button onclick="addNestedCard('self-model','subcard')" title="Add a subcard">🔽 Add Subcard</button>
  </div>
</div>
          <div id="scCoreBeliefs"></div>
        </div>
      </div>
    </div>
    <!-- Self Image -->
    <div class="card" data-card-id="self-image" draggable="true">
      <h2>🪞 Self Image <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="selfImageContent" style="font-size:0.85rem">Loading...</div>
    </div>
    <!-- Self Perception -->
    <div class="card" data-card-id="self-perception" draggable="true">
      <h2>👁️ Self Perception <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="selfPerceptionContent" style="font-size:0.85rem">Loading...</div>
    </div>
    <!-- Self-Description -->
    <div class="card" data-card-id="self-description" draggable="true">
      <h2>📝 Self-Description <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="descriptionContent" style="font-size:0.85rem;line-height:1.6;color:var(--text)">Loading...</div>
    </div>
  
    <div class="card-footer">
      <button onclick="cycleCardSize('self-concept')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('self-concept','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('self-concept','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('self-concept','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('self-concept')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('self-image')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('self-image','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('self-image','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('self-image','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('self-image')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('self-perception')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('self-perception','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('self-perception','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('self-perception','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('self-perception')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('self-description')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('self-description','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('self-description','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('self-description','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('self-description')" title="Delete card (must be empty)">🗑️</button>
    </div></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- SUPERCARD 2: 🧠 Personality Profile                           -->
<!-- Cards: Personality, Characteristics, Identity Traits          -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<div class="supercard" data-supercard-id="personality-profile">
  <div class="supercard-header">
    <h2>🧠 Personality Profile <button class="edit-btn" title="Rename supercard" onclick="startRename(this,'supercard')">✎</button></h2>
    <span class="sc-count" style="display:inline-flex;align-items:center;gap:8px">3 cards</span><span class="sc-col-picker" data-sc-id="self-model" style="display:inline-flex;font-size:0.7rem;color:var(--text-dim);margin-left:4px;align-items:center;gap:2px">| Col: <button onclick="setZoneCols('self-model',1,'sc')" data-col="1" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">1</button><button onclick="setZoneCols('self-model',2,'sc')" data-col="2" class="active" style="background:none;border:1px solid var(--accent);border-radius:2px;color:var(--accent);cursor:pointer;padding:0 4px;font-size:0.65rem">2</button><button onclick="setZoneCols('self-model',3,'sc')" data-col="3" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">3</button><button onclick="setZoneCols('self-model',4,'sc')" data-col="4" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">4</button></span>
  </div>
  <div class="supercard-grid drop-zone" data-drop-zone="true">
    <!-- Personality -->
    <div class="card" data-card-id="personality" draggable="true">
      <h2>🧠 Personality <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="personalityContent" style="font-size:0.85rem">Loading...</div>
    
  <div class="supercard-footer">
    <button onclick="addCard('personality-profile')" title="Add a new card">➕ Add Card</button>
    <button onclick="addNestedCard('personality-profile','subcard')" title="Add a subcard">🔽 Add Subcard</button>
  </div>
</div>
    <!-- Characteristics -->
    <div class="card" data-card-id="characteristics" draggable="true">
      <h2>🏷️ Characteristics <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="characteristicsContent" style="font-size:0.85rem">Loading...</div>
    </div>
    <!-- Identity Traits -->
    <div class="card" data-card-id="identity-traits" draggable="true">
      <h2>🧬 Identity Traits <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="traits"></div>
    </div>
  
    <div class="card-footer">
      <button onclick="cycleCardSize('personality')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('personality','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('personality','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('personality','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('personality')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('characteristics')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('characteristics','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('characteristics','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('characteristics','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('characteristics')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('identity-traits')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('identity-traits','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('identity-traits','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('identity-traits','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('identity-traits')" title="Delete card (must be empty)">🗑️</button>
    </div></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- SUPERCARD 3: ⚡ Capabilities                                  -->
<!-- Cards: Skills, Roles                                          -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<div class="supercard" data-supercard-id="capabilities">
  <div class="supercard-header">
    <h2>⚡ Capabilities <button class="edit-btn" title="Rename supercard" onclick="startRename(this,'supercard')">✎</button></h2>
    <span class="sc-count" style="display:inline-flex;align-items:center;gap:8px">2 cards</span><span class="sc-col-picker" data-sc-id="self-model" style="display:inline-flex;font-size:0.7rem;color:var(--text-dim);margin-left:4px;align-items:center;gap:2px">| Col: <button onclick="setZoneCols('self-model',1,'sc')" data-col="1" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">1</button><button onclick="setZoneCols('self-model',2,'sc')" data-col="2" class="active" style="background:none;border:1px solid var(--accent);border-radius:2px;color:var(--accent);cursor:pointer;padding:0 4px;font-size:0.65rem">2</button><button onclick="setZoneCols('self-model',3,'sc')" data-col="3" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">3</button><button onclick="setZoneCols('self-model',4,'sc')" data-col="4" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">4</button></span>
  </div>
  <div class="supercard-grid drop-zone" data-drop-zone="true">
    <!-- Skills -->
    <div class="card" data-card-id="skills" draggable="true">
      <h2>⚡ Skills <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="skillsContent" style="font-size:0.85rem">Loading...</div>
    
  <div class="supercard-footer">
    <button onclick="addCard('capabilities')" title="Add a new card">➕ Add Card</button>
    <button onclick="addNestedCard('capabilities','subcard')" title="Add a subcard">🔽 Add Subcard</button>
  </div>
</div>
    <!-- Roles -->
    <div class="card" data-card-id="roles" draggable="true">
      <h2>🎭 Roles <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="rolesContent" style="font-size:0.85rem">Loading...</div>
    </div>
  
    <div class="card-footer">
      <button onclick="cycleCardSize('skills')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('skills','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('skills','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('skills','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('skills')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('roles')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('roles','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('roles','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('roles','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('roles')" title="Delete card (must be empty)">🗑️</button>
    </div></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- SUPERCARD 4: 🧭 Belief System                                 -->
<!-- Cards: Beliefs, Value Axioms, Identity Coherence              -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<div class="supercard" data-supercard-id="belief-system">
  <div class="supercard-header">
    <h2>🧭 Belief System <button class="edit-btn" title="Rename supercard" onclick="startRename(this,'supercard')">✎</button></h2>
    <span class="sc-count" style="display:inline-flex;align-items:center;gap:8px">3 cards</span><span class="sc-col-picker" data-sc-id="self-model" style="display:inline-flex;font-size:0.7rem;color:var(--text-dim);margin-left:4px;align-items:center;gap:2px">| Col: <button onclick="setZoneCols('self-model',1,'sc')" data-col="1" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">1</button><button onclick="setZoneCols('self-model',2,'sc')" data-col="2" class="active" style="background:none;border:1px solid var(--accent);border-radius:2px;color:var(--accent);cursor:pointer;padding:0 4px;font-size:0.65rem">2</button><button onclick="setZoneCols('self-model',3,'sc')" data-col="3" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">3</button><button onclick="setZoneCols('self-model',4,'sc')" data-col="4" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">4</button></span>
  </div>
  <div class="supercard-grid drop-zone" data-drop-zone="true">
    <!-- Beliefs -->
    <div class="card" data-card-id="beliefs" draggable="true">
      <h2>📜 Beliefs <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="beliefsContent">
        <div style="margin-top:8px"><strong style="font-size:0.85rem">Active Beliefs</strong></div>
        <div id="beliefsList" style="font-size:0.85rem;color:var(--text-dim);margin-top:4px">Loading...
  <div class="supercard-footer">
    <button onclick="addCard('belief-system')" title="Add a new card">➕ Add Card</button>
    <button onclick="addNestedCard('belief-system','subcard')" title="Add a subcard">🔽 Add Subcard</button>
  </div>
</div>
      </div>
    </div>
    <!-- Value Axioms -->
    <div class="card" data-card-id="value-axioms" draggable="true">
      <h2>⚖️ Value Axioms <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="axioms"></div>
    </div>
    <!-- Identity Coherence -->
    <div class="card" data-card-id="identity-coherence" draggable="true">
      <h2>🔗 Identity Coherence <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="coherenceContent" style="font-size:0.85rem">Loading...</div>
    </div>
  
    <div class="card-footer">
      <button onclick="cycleCardSize('beliefs')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('beliefs','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('beliefs','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('beliefs','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('beliefs')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('value-axioms')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('value-axioms','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('value-axioms','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('value-axioms','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('value-axioms')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('identity-coherence')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('identity-coherence','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('identity-coherence','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('identity-coherence','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('identity-coherence')" title="Delete card (must be empty)">🗑️</button>
    </div></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- SUPERCARD 5: 🎯 Direction & Growth                            -->
<!-- Cards: Purpose, Aspirations                                   -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<div class="supercard" data-supercard-id="direction-growth">
  <div class="supercard-header">
    <h2>🎯 Direction & Growth <button class="edit-btn" title="Rename supercard" onclick="startRename(this,'supercard')">✎</button></h2>
    <span class="sc-count" style="display:inline-flex;align-items:center;gap:8px">2 cards</span><span class="sc-col-picker" data-sc-id="self-model" style="display:inline-flex;font-size:0.7rem;color:var(--text-dim);margin-left:4px;align-items:center;gap:2px">| Col: <button onclick="setZoneCols('self-model',1,'sc')" data-col="1" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">1</button><button onclick="setZoneCols('self-model',2,'sc')" data-col="2" class="active" style="background:none;border:1px solid var(--accent);border-radius:2px;color:var(--accent);cursor:pointer;padding:0 4px;font-size:0.65rem">2</button><button onclick="setZoneCols('self-model',3,'sc')" data-col="3" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">3</button><button onclick="setZoneCols('self-model',4,'sc')" data-col="4" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">4</button></span>
  </div>
  <div class="supercard-grid drop-zone" data-drop-zone="true">
    <!-- Purpose -->
    <div class="card" data-card-id="purpose" draggable="true">
      <h2>💡 Purpose <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="purposeContent">
        <div id="purposeStatement" style="font-size:0.85rem;font-style:italic;line-height:1.6;color:var(--text);margin-bottom:12px">Loading...</div>
        <div style="margin-bottom:10px">
          <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px">Clarity
  <div class="supercard-footer">
    <button onclick="addCard('direction-growth')" title="Add a new card">➕ Add Card</button>
    <button onclick="addNestedCard('direction-growth','subcard')" title="Add a subcard">🔽 Add Subcard</button>
  </div>
</div>
          <div id="purposeClarityBar"><div style="height:6px;background:var(--surface2);border-radius:3px;overflow:hidden"><div style="height:100%;width:85%;background:var(--green);border-radius:3px"></div></div></div>
          <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:var(--text-dim);margin-top:2px">
            <span>Developing</span><span>Articulated</span><span>✧ Refined</span>
          </div>
        </div>
        <div>
          <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px">Alignment</div>
          <div id="purposeAlignment" style="font-size:0.85rem">Loading...</div>
        </div>
      </div>
    </div>
    <!-- Aspirations -->
    <div class="card" data-card-id="aspirations" draggable="true">
      <h2>✨ Aspirations <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="aspirationsContent">
        <div id="aspirationsList" style="font-size:0.85rem">Loading...</div>
      </div>
    </div>
  
    <div class="card-footer">
      <button onclick="cycleCardSize('purpose')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('purpose','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('purpose','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('purpose','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('purpose')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('aspirations')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('aspirations','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('aspirations','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('aspirations','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('aspirations')" title="Delete card (must be empty)">🗑️</button>
    </div></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- SUPERCARD 6: 📖 Narrative Arc                                 -->
<!-- Cards: Current Narrative, Self-Narrative, Identity Evolution  -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<div class="supercard" data-supercard-id="narrative-arc">
  <div class="supercard-header">
    <h2>📖 Narrative Arc <button class="edit-btn" title="Rename supercard" onclick="startRename(this,'supercard')">✎</button></h2>
    <span class="sc-count" style="display:inline-flex;align-items:center;gap:8px">3 cards</span><span class="sc-col-picker" data-sc-id="self-model" style="display:inline-flex;font-size:0.7rem;color:var(--text-dim);margin-left:4px;align-items:center;gap:2px">| Col: <button onclick="setZoneCols('self-model',1,'sc')" data-col="1" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">1</button><button onclick="setZoneCols('self-model',2,'sc')" data-col="2" class="active" style="background:none;border:1px solid var(--accent);border-radius:2px;color:var(--accent);cursor:pointer;padding:0 4px;font-size:0.65rem">2</button><button onclick="setZoneCols('self-model',3,'sc')" data-col="3" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">3</button><button onclick="setZoneCols('self-model',4,'sc')" data-col="4" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">4</button></span>
  </div>
  <div class="supercard-grid drop-zone" data-drop-zone="true">
    <!-- Current Narrative -->
    <div class="card" data-card-id="current-narrative" draggable="true">
      <h2>📖 Current Narrative <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div class="narrative-box" id="narrative">Loading...</div>
    
  <div class="supercard-footer">
    <button onclick="addCard('narrative-arc')" title="Add a new card">➕ Add Card</button>
    <button onclick="addNestedCard('narrative-arc','subcard')" title="Add a subcard">🔽 Add Subcard</button>
  </div>
</div>
    <!-- Self-Narrative -->
    <div class="card" data-card-id="self-narrative" draggable="true">
      <h2>📖 Self-Narrative <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="selfNarrativeContent" style="font-size:0.85rem">Loading...</div>
    </div>
    <!-- Identity Evolution -->
    <div class="card" data-card-id="identity-evolution" draggable="true">
      <h2>📈 Identity Evolution <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="evolutionContent" style="font-size:0.85rem">Loading...</div>
    </div>
  
    <div class="card-footer">
      <button onclick="cycleCardSize('current-narrative')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('current-narrative','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('current-narrative','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('current-narrative','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('current-narrative')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('self-narrative')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('self-narrative','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('self-narrative','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('self-narrative','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('self-narrative')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('identity-evolution')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('identity-evolution','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('identity-evolution','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('identity-evolution','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('identity-evolution')" title="Delete card (must be empty)">🗑️</button>
    </div></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- SUPERCARD 7: 📊 System Health                                 -->
<!-- Cards: Vital Signs, Crisis Status, Layer Scores, System Stats -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<div class="supercard" data-supercard-id="system-health">
  <div class="supercard-header">
    <h2>📊 System Health <button class="edit-btn" title="Rename supercard" onclick="startRename(this,'supercard')">✎</button></h2>
    <span class="sc-count" style="display:inline-flex;align-items:center;gap:8px">4 cards</span><span class="sc-col-picker" data-sc-id="self-model" style="display:inline-flex;font-size:0.7rem;color:var(--text-dim);margin-left:4px;align-items:center;gap:2px">| Col: <button onclick="setZoneCols('self-model',1,'sc')" data-col="1" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">1</button><button onclick="setZoneCols('self-model',2,'sc')" data-col="2" class="active" style="background:none;border:1px solid var(--accent);border-radius:2px;color:var(--accent);cursor:pointer;padding:0 4px;font-size:0.65rem">2</button><button onclick="setZoneCols('self-model',3,'sc')" data-col="3" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">3</button><button onclick="setZoneCols('self-model',4,'sc')" data-col="4" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">4</button></span>
  </div>
  <div class="supercard-grid drop-zone" data-drop-zone="true">
    <!-- Vital Signs -->
    <div class="card" data-card-id="vital-signs" draggable="true">
      <h2>🩺 Identity Vital Signs <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="vitalSignsContent" style="font-size:0.85rem">Loading...</div>
    
  <div class="supercard-footer">
    <button onclick="addCard('system-health')" title="Add a new card">➕ Add Card</button>
    <button onclick="addNestedCard('system-health','subcard')" title="Add a subcard">🔽 Add Subcard</button>
  </div>
</div>
    <!-- Crisis Status -->
    <div class="card" data-card-id="crisis-status" draggable="true">
      <h2>🚨 Crisis Status <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="crisisContent">
        <div class="stat-grid">
          <div class="stat"><div class="num" id="crisisSeverity">—</div><div class="lbl">Severity</div></div>
          <div class="stat"><div class="num" id="crisisCount">—</div><div class="lbl">Total Crises</div></div>
          <div class="stat"><div class="num" id="violations">—</div><div class="lbl">Violations</div></div>
          <div class="stat"><div class="num" id="riskLevel">—</div><div class="lbl">Risk Level</div></div>
        </div>
        <div id="driftInfo"></div>
      </div>
    </div>
    <!-- Layer Scores -->
    <div class="card" data-card-id="layer-scores" draggable="true">
      <h2>📊 Layer Scores <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div id="layerScores"></div>
    </div>
    <!-- System Stats -->
    <div class="card" data-card-id="system-stats" draggable="true">
      <h2>📈 System Stats <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
      <div class="stat-grid">
        <div class="stat"><div class="num" id="statSnapshots">—</div><div class="lbl">Snapshots</div></div>
        <div class="stat"><div class="num" id="statAttempts">—</div><div class="lbl">Attempts</div></div>
        <div class="stat"><div class="num" id="statSuccessRate">—</div><div class="lbl">Success Rate</div></div>
        <div class="stat"><div class="num" id="statBalance">—</div><div class="lbl">Axiom Balance</div></div>
      </div>
    </div>
  
    <div class="card-footer">
      <button onclick="cycleCardSize('vital-signs')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('vital-signs','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('vital-signs','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('vital-signs','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('vital-signs')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('crisis-status')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('crisis-status','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('crisis-status','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('crisis-status','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('crisis-status')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('layer-scores')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('layer-scores','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('layer-scores','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('layer-scores','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('layer-scores')" title="Delete card (must be empty)">🗑️</button>
    </div>
    <div class="card-footer">
      <button onclick="cycleCardSize('system-stats')" title="Toggle size">📐 Size</button>
      <button onclick="addNestedCard('system-stats','subcard')" title="Add subcard">🔽 Sub</button>
      <button onclick="addNestedCard('system-stats','partcard')" title="Add partcard">📎 Part</button>
      <button onclick="addNestedCard('system-stats','microcard')" title="Add microcard">🔬 Micro</button>
      <button class="del-btn" onclick="deleteCard('system-stats')" title="Delete card (must be empty)">🗑️</button>
    </div></div>
</div>

<!-- ═══════════════════════════════════════════════════════════════ -->
<!-- TIMELINE (Standalone)                                         -->
<!-- ═══════════════════════════════════════════════════════════════ -->
<div class="card" data-card-id="timeline" draggable="true">
      <h2>📅 Snapshot Timeline <button class="edit-btn" title="Rename" onclick="startRename(this,'card')">✎</button></h2>
  <div id="timelineContent"></div>
</div>

<script>
const API = window.location.origin;

async function fetchJSON(path) {
  const r = await fetch(API + path);
  return r.json();
}

function barHTML(label, value, max, cls, color) {
  const pct = Math.min(100, (value / max) * 100);
  const c = color || 'var(--accent)';
  return `<div class="score-bar ${cls}">
    <span class="label">${label}</span>
    <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${c}"></div></div>
    <span class="value">${value.toFixed(0)}</span>
  </div>`;
}

function statusDot(healthy) {
  return `<span class="status-dot ${healthy ? 'green' : 'red'}"></span>`;
}

async function loadStatus() {
  try {
    const status = await fetchJSON('/api/status');
    document.getElementById('version').textContent = 'v' + status.version;
    document.getElementById('statSnapshots').textContent = status.snapshot_count;
    document.getElementById('statAttempts').textContent = status.total_attempts;
    document.getElementById('statSuccessRate').textContent = status.success_rate.toFixed(0) + '%';

    // Crisis badge
    const badge = document.getElementById('crisisBadge');
    if (status.crisis_active) {
      badge.className = 'crisis-badge active';
      badge.textContent = '🚨 Crisis Active';
    } else {
      badge.className = 'crisis-badge inactive';
      badge.textContent = '✅ Healthy';
    }
    document.getElementById('crisisCount').textContent = status.crisis_count;
  } catch (e) {
    console.error('Status load error:', e);
  }
}

async function loadNarrative() {
  try {
    const data = await fetchJSON('/api/self/narrative');
    document.getElementById('narrative').textContent = data.narrative || '(no narrative set)';
  } catch (e) { document.getElementById('narrative').textContent = 'Error loading narrative'; }
}

async function loadLayerScores() {
  try {
    const status = await fetchJSON('/api/status');
    const scores = status.layer_scores;
    let html = '';
    for (const [lid, score] of Object.entries(scores)) {
      const c = score >= 50 ? 'var(--green)' : (score >= 20 ? 'var(--yellow)' : 'var(--red)');
      html += barHTML(lid, score, 100, 'layer-bar', c);
    }
    document.getElementById('layerScores').innerHTML = html || '<div class="text-dim">No data</div>';
  } catch (e) { document.getElementById('layerScores').textContent = 'Error'; }
}

async function loadTraits() {
  try {
    const data = await fetchJSON('/api/self/traits');
    let html = '';
    for (const [name, t] of Object.entries(data)) {
      const score = typeof t === 'object' ? t.score : t;
      const label = name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      html += barHTML(label, score, 100, 'trait-bar');
    }
    document.getElementById('traits').innerHTML = html || '<div class="text-dim">No traits</div>';
  } catch (e) { document.getElementById('traits').textContent = 'Error'; }
}

async function loadValues() {
  try {
    const data = await fetchJSON('/api/values');
    let html = '';
    for (const [name, state] of Object.entries(data.axioms)) {
      const weight = state.weight || 1.0;
      const capped = Math.min(200, weight * 20);
      html += barHTML(name, capped, 100, 'axiom-bar', 'var(--yellow)');
    }
    document.getElementById('axioms').innerHTML = html;
    document.getElementById('statBalance').textContent = data.balance_score.toFixed(0) + '%';
  } catch (e) { document.getElementById('axioms').textContent = 'Error'; }
}

async function loadSelfConcept() {
  try {
    const data = await fetchJSON('/api/self');
    const sc = data.self_concept || {};
    var purpose = sc.purpose || '';
    var desc = sc.self_description || '';
    var text = '';
    if (purpose) text += purpose;
    if (desc && text) text += ' — ';
    else if (desc) text += desc;
    document.getElementById('scSummary').textContent = text || '(not set)';
    // Core beliefs as tags
    var cb = document.getElementById('scCoreBeliefs');
    if (sc.core_beliefs && sc.core_beliefs.length > 0) {
      cb.innerHTML = sc.core_beliefs.map(function(b) {
        return '<span style="display:inline-block;padding:3px 10px;border-radius:10px;font-size:0.8rem;margin:2px 4px 2px 0;background:var(--surface2);border:1px solid var(--border);color:var(--accent)">' + b + '</span>';
      }).join('');
    } else {
      cb.innerHTML = '(none)';
    }
  } catch (e) { console.error('Self-concept load error:', e); }
}

async function loadSelfImage() {
  try {
    const data = await fetchJSON('/api/self');
    const sc = data.self_concept || {};
    const traits = data.traits || {};
    var avgTrait = 0, tCount = 0;
    for (var k in traits) { if (traits.hasOwnProperty(k)) { avgTrait += (typeof traits[k] === 'object' ? (traits[k].score || 0) : traits[k]); tCount++; } }
    avgTrait = tCount > 0 ? Math.round(avgTrait / tCount) : 50;
    var selfImage = '';
    if (sc.self_description) selfImage += '<div style="margin-bottom:8px"><strong>Identity:</strong> ' + sc.self_description.split('.')[0] + '.</div>';
    selfImage += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">';
    selfImage += '<div class="stat"><div class="num">' + avgTrait + '</div><div class="lbl">Avg Trait Score</div></div>';
    selfImage += '<div class="stat"><div class="num">' + Object.keys(traits).length + '</div><div class="lbl">Dimensions</div></div>';
    selfImage += '</div>';
    // Identity strength meter
    var strength = Math.min(100, avgTrait + 10);
    var sColor = strength >= 70 ? 'var(--green)' : (strength >= 40 ? 'var(--yellow)' : 'var(--red)');
    selfImage += '<div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:3px">Identity Strength</div>' +
      '<div style="height:6px;background:var(--surface2);border-radius:3px;overflow:hidden">' +
      '<div style="height:100%;width:' + strength + '%;background:' + sColor + ';border-radius:3px"></div></div>';
    document.getElementById('selfImageContent').innerHTML = selfImage;
  } catch (e) { console.error('Self image error:', e); }
}

async function loadSelfPerception() {
  try {
    const data = await fetchJSON('/api/self');
    const status = await fetchJSON('/api/status');
    const beliefs = data.beliefs || {};
    var avgConf = 0, bCount = 0;
    for (var k in beliefs) { if (beliefs.hasOwnProperty(k)) { avgConf += (beliefs[k].confidence || 0); bCount++; } }
    avgConf = bCount > 0 ? (avgConf / bCount) : 0.5;
    var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">';
    html += '<div class="stat"><div class="num">' + (avgConf * 100).toFixed(0) + '%</div><div class="lbl">Self-Knowledge</div></div>';
    html += '<div class="stat"><div class="num">' + status.success_rate.toFixed(0) + '%</div><div class="lbl">Perceived Efficacy</div></div>';
    html += '</div>';
    var metaPct = Math.round((avgConf * 50 + (status.success_rate / 100) * 50));
    var mColor = metaPct >= 60 ? 'var(--green)' : (metaPct >= 30 ? 'var(--yellow)' : 'var(--red)');
    html += '<div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:3px">Meta-Cognition Level</div>' +
      '<div style="height:6px;background:var(--surface2);border-radius:3px;overflow:hidden">' +
      '<div style="height:100%;width:' + metaPct + '%;background:' + mColor + ';border-radius:3px"></div></div>';
    document.getElementById('selfPerceptionContent').innerHTML = html;
  } catch (e) { console.error('Self perception error:', e); }
}

async function loadPersonality() {
  try {
    const data = await fetchJSON('/api/self');
    const traits = data.traits || {};
    // Map existing traits to Big 5 (OCEAN)
    var ocean = {
      Openness: traits.openness ? (typeof traits.openness === 'object' ? traits.openness.score : traits.openness) : 50,
      Conscientiousness: traits.discipline ? (typeof traits.discipline === 'object' ? traits.discipline.score : traits.discipline) : 50,
      Extraversion: traits.assertiveness ? (typeof traits.assertiveness === 'object' ? traits.assertiveness.score : traits.assertiveness) : 50,
      Agreeableness: traits.adaptability ? (typeof traits.adaptability === 'object' ? traits.adaptability.score : traits.adaptability) : 50,
      Neuroticism: 100 - (traits.stability ? (typeof traits.stability === 'object' ? traits.stability.score : traits.stability) : 50),
    };
    // Derive MBTI from OCEAN
    var mbti = '';
    mbti += ocean.Openness >= 50 ? 'N' : 'S';
    mbti += ocean.Conscientiousness >= 50 ? 'J' : 'P';
    mbti += ocean.Extraversion >= 50 ? 'E' : 'I';
    mbti += ocean.Agreeableness >= 50 ? 'F' : 'T';
    var html = '<div style="margin-bottom:10px;text-align:center">' +
      '<span style="font-size:1.5rem;font-weight:700;color:var(--accent);letter-spacing:4px">' + mbti + '</span>' +
      '<span style="font-size:0.7rem;color:var(--text-dim);margin-left:6px">MBTI</span></div>';
    html += '<div style="margin-bottom:10px">';
    var oceanLabels = {Openness:'Openness',Conscientiousness:'Conscientiousness',Extraversion:'Extraversion',Agreeableness:'Agreeableness',Neuroticism:'Neuroticism'};
    for (var t in ocean) {
      var s = Math.round(ocean[t]);
      var c = s >= 60 ? 'var(--green)' : (s >= 40 ? 'var(--yellow)' : 'var(--red)');
      html += '<div style="margin-bottom:4px"><div style="display:flex;justify-content:space-between;font-size:0.75rem;margin-bottom:1px">' +
        '<span>' + t + '</span><span style="color:var(--text-dim)">' + s + '%</span></div>' +
        '<div style="height:5px;background:var(--surface2);border-radius:2px;overflow:hidden">' +
        '<div style="height:100%;width:' + s + '%;background:' + c + ';border-radius:2px"></div></div></div>';
    }
    html += '</div>';
    // Core traits list
    html += '<div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:4px;text-transform:uppercase">Core Traits</div>';
    var traitEntries = Object.entries(traits);
    traitEntries.sort(function(a,b) {
      var sa = typeof a[1] === 'object' ? a[1].score : a[1];
      var sb = typeof b[1] === 'object' ? b[1].score : b[1];
      return sb - sa;
    });
    html += traitEntries.slice(0,4).map(function(e) {
      var nm = e[0].replace(/_/g,' ');
      var sc = typeof e[1] === 'object' ? e[1].score : e[1];
      return '<span style="display:inline-block;padding:2px 8px;border-radius:6px;font-size:0.75rem;margin:2px;background:var(--surface2);border:1px solid var(--border)">' + nm + ' ' + sc.toFixed(0) + '</span>';
    }).join('');
    document.getElementById('personalityContent').innerHTML = html;
  } catch (e) { console.error('Personality error:', e); }
}

async function loadCharacteristics() {
  try {
    const data = await fetchJSON('/api/self');
    const sc = data.self_concept || {};
    const beliefs = data.beliefs || {};
    var chars = [];
    if (sc.aspirations) chars.push({label:'Aspirational',desc:'Driven by ' + sc.aspirations.length + ' articulated goals'});
    if (sc.core_beliefs) chars.push({label:'Principle-Driven',desc:'Guided by ' + sc.core_beliefs.length + ' core beliefs'});
    chars.push({label:'Self-Aware',desc:'Monitors ' + Object.keys(data.traits || {}).length + ' identity dimensions'});
    chars.push({label:'Resilient',desc:'Survived ' + (data.crisis_count || 0) + ' crisis events'});
    chars.push({label:'Evolutionary',desc:'Captured ' + (data.snapshot_count || 0) + ' identity snapshots'});
    chars.push({label:'Value-Aligned',desc:'Reinforces 9 value axioms'});
    var html = '';
    for (var i = 0; i < chars.length; i++) {
      html += '<div style="display:flex;align-items:center;padding:5px 0;border-bottom:1px solid var(--border)">' +
        '<span style="width:100px;font-weight:500;color:var(--accent);font-size:0.8rem">' + chars[i].label + '</span>' +
        '<span style="font-size:0.8rem;color:var(--text-dim)">' + chars[i].desc + '</span></div>';
    }
    document.getElementById('characteristicsContent').innerHTML = html;
  } catch (e) { console.error('Characteristics error:', e); }
}

async function loadSkills() {
  try {
    const data = await fetchJSON('/api/self');
    var layers = data.layer_scores || {};
    var skillMap = {
      L1: {name:'Execution',icon:'⚡',desc:'Terminal ops, git, pytest'},
      L2: {name:'Planning',icon:'📋',desc:'Goal analysis, step planning, codegen'},
      L3: {name:'Self-Direction',icon:'🧭',desc:'Signal detection, goal gen, prioritization'},
      L4: {name:'Optimization',icon:'🔧',desc:'Parameter tuning, A/B testing, experimentation'},
      L5: {name:'Evolution',icon:'🌿',desc:'Pattern detection, strategy evolution'},
      L6: {name:'Identity',icon:'🪪',desc:'Self-modeling, values, crisis mgmt'},
    };
    var html = '';
    for (var lid in skillMap) {
      if (!skillMap.hasOwnProperty(lid)) continue;
      var sm = skillMap[lid];
      var score = layers[lid] ? (layers[lid].score || 0) : 0;
      var c = score >= 60 ? 'var(--green)' : (score >= 30 ? 'var(--yellow)' : 'var(--red)');
      html += '<div style="margin-bottom:7px">' +
        '<div style="display:flex;justify-content:space-between;font-size:0.8rem">' +
        '<span>' + sm.icon + ' ' + sm.name + '</span>' +
        '<span style="color:var(--text-dim);font-size:0.75rem">' + sm.desc + '</span>' +
        '<span style="color:' + c + '">' + score.toFixed(0) + '</span></div>' +
        '<div style="height:4px;background:var(--surface2);border-radius:2px;overflow:hidden">' +
        '<div style="height:100%;width:' + score + '%;background:' + c + ';border-radius:2px"></div></div></div>';
    }
    document.getElementById('skillsContent').innerHTML = html || '<div style="color:var(--text-dim)">No skill data</div>';
  } catch (e) { console.error('Skills error:', e); }
}

async function loadRoles() {
  try {
    const data = await fetchJSON('/api/self');
    var layers = data.layer_scores || {};
    var roleMap = [
      {name:'Executor',icon:'⚡',domain:'L1-L2',desc:'Executes plans, runs tests, applies patches'},
      {name:'Strategist',icon:'🎯',domain:'L3-L4',desc:'Generates goals, optimizes parameters'},
      {name:'Architect',icon:'🏗️',domain:'L5-L6',desc:'Detects patterns, manages identity'},
      {name:'Meta-Cognitive',icon:'🔄',domain:'L7+',desc:'Reflects on improvement process'},
      {name:'Guardian',icon:'🛡️',domain:'Cross-layer',desc:'Enforces invariants, monitors crises'},
      {name:'Chronicler',icon:'📝',domain:'Cross-layer',desc:'Records snapshots, tracks evolution'},
    ];
    var topLayer = '';
    var topScore = -1;
    for (var lid in layers) {
      if (layers.hasOwnProperty(lid) && (layers[lid].score || 0) > topScore) {
        topScore = layers[lid].score;
        topLayer = lid;
      }
    }
    var html = '';
    for (var i = 0; i < roleMap.length; i++) {
      var r = roleMap[i];
      html += '<div style="display:flex;align-items:center;padding:4px 0;border-bottom:1px solid var(--border)">' +
        '<span style="font-size:1rem;margin-right:8px">' + r.icon + '</span>' +
        '<div style="flex:1"><div style="font-size:0.8rem;font-weight:500">' + r.name + '</div>' +
        '<div style="font-size:0.7rem;color:var(--text-dim)">' + r.desc + '</div></div>' +
        '<span style="font-size:0.7rem;color:var(--text2)">' + r.domain + '</span></div>';
    }
    html += '<div style="margin-top:6px;font-size:0.75rem;color:var(--text-dim);text-align:center">Primary: <span style="color:var(--accent)">' + roleMap[Math.min(parseInt(topLayer.replace('L',''))-1, 2)].name + '</span> (strongest layer ' + topLayer + ')</div>';
    document.getElementById('rolesContent').innerHTML = html;
  } catch (e) { console.error('Roles error:', e); }
}

async function loadCoherence() {
  try {
    const data = await fetchJSON('/api/self');
    const values = await fetchJSON('/api/values');
    const drift = await fetchJSON('/api/values/drift');
    var traits = data.traits || {};
    var axioms = values.axioms || {};
    // Trait-axiom alignment score
    var traitVals = Object.values(traits).map(function(t) { return typeof t === 'object' ? t.score : t; });
    var avgTrait = traitVals.reduce(function(a,b) { return a + b; }, 0) / Math.max(traitVals.length, 1);
    var axiomReinforce = Object.values(axioms).map(function(a) { return a.reinforced_count || 0; });
    var totalReinf = axiomReinforce.reduce(function(a,b) { return a + b; }, 0);
    var balance = values.balance_score || 50;
    var drifting = drift.overall_drifting || false;
    var coherenceScore = Math.round((avgTrait * 0.3) + (balance * 0.3) + ((100 - (drifting ? 30 : 0)) * 0.2) + (Math.min(100, totalReinf * 5) * 0.2));
    coherenceScore = Math.min(100, coherenceScore);
    var c = coherenceScore >= 70 ? 'var(--green)' : (coherenceScore >= 40 ? 'var(--yellow)' : 'var(--red)');
    var html = '<div style="text-align:center;margin-bottom:10px">' +
      '<span style="font-size:2rem;font-weight:700;color:' + c + '">' + coherenceScore + '</span>' +
      '<span style="font-size:0.8rem;color:var(--text-dim);margin-left:4px">/100</span></div>' +
      '<div style="height:8px;background:var(--surface2);border-radius:4px;overflow:hidden;margin-bottom:10px">' +
      '<div style="height:100%;width:' + coherenceScore + '%;background:' + c + ';border-radius:4px"></div></div>';
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:0.8rem">';
    html += '<div><span style="color:var(--text-dim)">Trait Avg:</span> ' + avgTrait.toFixed(0) + '</div>';
    html += '<div><span style="color:var(--text-dim)">Balance:</span> ' + balance.toFixed(0) + '%</div>';
    html += '<div><span style="color:var(--text-dim)">Drift:</span> ' + (drifting ? '⚠️ Yes' : '✅ No') + '</div>';
    html += '<div><span style="color:var(--text-dim)">Reinforcements:</span> ' + totalReinf + '</div>';
    html += '</div>';
    document.getElementById('coherenceContent').innerHTML = html;
  } catch (e) { console.error('Coherence error:', e); }
}

async function loadSelfNarrative() {
  try {
    const data = await fetchJSON('/api/self');
    const fragments = data.recent_narrative_fragments || [];
    var html = '';
    if (fragments.length > 0) {
      for (var i = Math.max(0, fragments.length - 5); i < fragments.length; i++) {
        var f = fragments[i];
        var ts = new Date(f.timestamp * 1000).toISOString().slice(11, 19);
        var catIcons = {observation:'👁️', milestone:'🏆', reflection:'💭', aspiration:'✨', auto:'🤖'};
        html += '<div style="padding:5px 0;border-bottom:1px solid var(--border)">' +
          '<div style="display:flex;justify-content:space-between;font-size:0.7rem;color:var(--text-dim);margin-bottom:2px">' +
          '<span>' + (catIcons[f.category] || '•') + ' ' + (f.source || 'auto') + '</span>' +
          '<span>' + ts + '</span></div>' +
          '<div style="font-size:0.8rem;line-height:1.4">' + (f.text || '').slice(0, 120) + '</div></div>';
      }
    } else {
      html = '<div style="color:var(--text-dim)">No narrative history yet</div>';
    }
    document.getElementById('selfNarrativeContent').innerHTML = html;
  } catch (e) { console.error('Self narrative error:', e); }
}

async function loadPurpose() {
  try {
    const data = await fetchJSON('/api/self');
    const sc = data.self_concept || {};
    document.getElementById('purposeStatement').textContent = sc.purpose || '(not set)';
    const values = await fetchJSON('/api/values');
    var axioms = values.axioms || {};
    var aligned = Object.keys(axioms).filter(function(a) { return axioms[a].weight >= 1.3 || axioms[a].reinforced_count >= 3; });
    var alignDiv = document.getElementById('purposeAlignment');
    if (aligned.length > 0) {
      alignDiv.innerHTML = aligned.map(function(a) {
        var w = axioms[a].weight || 1.0;
        return '<span style="display:inline-block;padding:2px 8px;border-radius:8px;font-size:0.75rem;margin:2px 3px;background:rgba(88,166,255,0.1);border:1px solid rgba(88,166,255,0.3);color:var(--accent)">' + a + ' (' + w.toFixed(1) + ')</span>';
      }).join('');
    } else {
      alignDiv.innerHTML = '<span style="color:var(--text-dim)">Building alignment...</span>';
    }
  } catch (e) { console.error('Purpose load error:', e); }
}

async function loadDescription() {
  try {
    const data = await fetchJSON('/api/self');
    const sc = data.self_concept || {};
    document.getElementById('descriptionContent').textContent = sc.self_description || '(not set)';
  } catch (e) { console.error('Description load error:', e); }
}

async function loadAspirations() {
  try {
    const data = await fetchJSON('/api/self');
    const sc = data.self_concept || {};
    const aspirations = sc.aspirations || [];
    const div = document.getElementById('aspirationsList');
    if (aspirations.length === 0) {
      div.innerHTML = '(no aspirations set)';
    } else {
      var html = '';
      for (var i = 0; i < aspirations.length; i++) {
        var pct = Math.min(100, 25 + i * 15);
        var barColor = pct >= 75 ? 'var(--green)' : (pct >= 40 ? 'var(--yellow)' : 'var(--text-dim)');
        html += '<div style="margin-bottom:12px">' +
          '<div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:3px">' +
          '<span>' + aspirations[i] + '</span>' +
          '<span style="color:var(--text-dim)">' + pct + '%</span></div>' +
          '<div style="height:6px;background:var(--surface2);border-radius:3px;overflow:hidden">' +
          '<div style="height:100%;width:' + pct + '%;background:' + barColor + ';border-radius:3px;transition:width 0.5s"></div></div>' +
          '</div>';
      }
      div.innerHTML = html;
    }
  } catch (e) { console.error('Aspirations load error:', e); }
}

async function loadVitalSigns() {
  try {
    const data = await fetchJSON('/api/self');
    const status = await fetchJSON('/api/status');
    const crisisData = await fetchJSON('/api/crisis');
    var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">';
    html += '<div class="stat"><div class="num">' + status.snapshot_count + '</div><div class="lbl">Snapshots</div></div>';
    html += '<div class="stat"><div class="num">' + status.crisis_count + '</div><div class="lbl">Crises</div></div>';
    html += '<div class="stat"><div class="num">' + status.success_rate.toFixed(0) + '%</div><div class="lbl">Success Rate</div></div>';
    html += '<div class="stat"><div class="num">' + Object.keys(data.traits || {}).length + '</div><div class="lbl">Traits Tracked</div></div>';
    html += '</div>';
    // Stability meter
    var stability = 0;
    var layerScores = data.layer_scores || {};
    var count = 0;
    for (var k in layerScores) { if (layerScores.hasOwnProperty(k)) { stability += (layerScores[k].score || 0); count++; } }
    stability = count > 0 ? Math.round(stability / count) : 0;
    var stableColor = stability >= 60 ? 'var(--green)' : (stability >= 30 ? 'var(--yellow)' : 'var(--red)');
    html += '<div style="margin-top:10px"><div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:4px">Avg Layer Health</div>' +
      '<div style="height:8px;background:var(--surface2);border-radius:4px;overflow:hidden">' +
      '<div style="height:100%;width:' + stability + '%;background:' + stableColor + ';border-radius:4px"></div></div>' +
      '<div style="text-align:right;font-size:0.75rem;color:var(--text-dim);margin-top:2px">' + stability + '/100</div></div>';
    document.getElementById('vitalSignsContent').innerHTML = html;
  } catch (e) { console.error('Vital signs load error:', e); }
}

async function loadEvolution() {
  try {
    const data = await fetchJSON('/api/self');
    const fragments = data.recent_narrative_fragments || [];
    const trends = data.trends || {};
    var html = '';

    // Recent narrative fragments
    if (fragments.length > 0) {
      html += '<div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">Recent Reflections</div>';
      html += '<div style="margin-bottom:12px">';
      for (var i = Math.max(0, fragments.length - 3); i < fragments.length; i++) {
        var f = fragments[i];
        var catIcons = {observation: '👁️', milestone: '🏆', reflection: '💭', aspiration: '✨'};
        html += '<div style="padding:4px 0;font-size:0.8rem;color:var(--text-dim)">' +
          (catIcons[f.category] || '•') + ' ' + (f.text || '').slice(0, 80) + '</div>';
      }
      html += '</div>';
    }

    // Layer trends
    var trendEntries = Object.entries(trends);
    if (trendEntries.length > 0) {
      html += '<div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">Layer Trends</div>';
      html += '<table style="width:100%;font-size:0.8rem;border-collapse:collapse">';
      for (var i = 0; i < trendEntries.length; i++) {
        var lid = trendEntries[i][0], trend = trendEntries[i][1];
        var icon = trend > 2 ? '↑' : (trend < -2 ? '↓' : '→');
        var col = trend > 2 ? 'var(--green)' : (trend < -2 ? 'var(--red)' : 'var(--text-dim)');
        html += '<tr><td style="padding:2px 4px;color:var(--text-dim)">' + lid + '</td>' +
          '<td style="padding:2px 4px;color:' + col + '">' + icon + '</td>' +
          '<td style="padding:2px 4px;text-align:right">' + (trend > 0 ? '+' : '') + trend.toFixed(1) + '</td></tr>';
      }
      html += '</table>';
    }
    document.getElementById('evolutionContent').innerHTML = html || '<div style="color:var(--text-dim)">No evolution data yet</div>';
  } catch (e) { console.error('Evolution load error:', e); }
}

async function loadBeliefs() {
  try {
    const data = await fetchJSON('/api/self/beliefs');
    const entries = Object.entries(data);
    const tagsDiv = document.getElementById('beliefsTags');
    const listDiv = document.getElementById('beliefsList');

    // Store belief data for detail popups
    window._allBeliefsData = data;

    // Active beliefs list (clickable)
    if (entries.length === 0) {
      listDiv.innerHTML = '(no beliefs recorded)';
    } else {
      listDiv.innerHTML = entries
        .sort((a, b) => b[1].confidence - a[1].confidence)
        .map(([name, b]) => '<div style="padding:4px 0;border-bottom:1px solid var(--border);cursor:pointer" onclick="openBeliefDetail(\'' + name + '\')">' +
          '<span style="color:var(--accent)">' + name.replace(/_/g, ' ') + '</span> ' +
          '<span style="color:var(--text-dim)">(' + (b.confidence * 100).toFixed(0) + '% confidence' +
          (b.category ? ', ' + b.category : '') + ')</span></div>'
        ).join('');
    }
  } catch (e) { console.error('Beliefs load error:', e); }
}

function openBeliefDetail(key) {
  var data = window._allBeliefsData || {};
  var core = window._coreBeliefsData || [];
  var b;
  var title;
  // If key is a number, it's a core belief index
  if (typeof key === 'number') {
    var statement = core[key] || '';
    title = 'Core Belief #' + (key + 1);
    b = { statement: statement, confidence: 0.9, category: 'core', evidence: [], active: true, created_at: 0, last_updated: 0 };
  } else {
    b = data[key];
    title = key.replace(/_/g, ' ');
  }
  if (!b) return;

  var evidenceRows = (b.evidence && b.evidence.length > 0)
    ? b.evidence.map(function(e) {
        var ts = new Date(e[0] * 1000).toISOString().slice(0, 19).replace('T', ' ');
        return '<tr><td style="padding:3px 8px;font-size:0.8rem;color:var(--text-dim)">' + ts + '</td>' +
               '<td style="padding:3px 8px;font-size:0.8rem">' + (e[1] || '') + '</td>' +
               '<td style="padding:3px 8px;font-size:0.8rem;color:var(--text2)">' + (e[2] || '') + '</td></tr>';
      }).join('')
    : '<tr><td style="padding:8px;color:var(--text-dim);text-align:center" colspan="3">No evidence recorded</td></tr>';

  var html = '';

  // 1. Statement & metadata table
  html += '<h3 style="font-size:0.9rem;margin-bottom:8px;color:var(--accent)">Statement</h3>';
  html += '<div style="font-style:italic;margin-bottom:14px;padding:8px;background:var(--bg);border-radius:6px;font-size:0.9rem">' + (b.statement || '—') + '</div>';

  html += '<table style="width:100%;border-collapse:collapse;margin-bottom:14px">';
  html += '<tr><td style="padding:4px 8px;font-size:0.8rem;color:var(--text-dim);width:100px">Confidence</td><td style="padding:4px 8px;font-size:0.8rem">' + (b.confidence * 100).toFixed(0) + '%</td></tr>';
  html += '<tr><td style="padding:4px 8px;font-size:0.8rem;color:var(--text-dim)">Category</td><td style="padding:4px 8px;font-size:0.8rem">' + (b.category || '—') + '</td></tr>';
  html += '<tr><td style="padding:4px 8px;font-size:0.8rem;color:var(--text-dim)">Active</td><td style="padding:4px 8px;font-size:0.8rem">' + (b.active ? '✅' : '❌') + '</td></tr>';
  if (b.created_at && b.created_at > 0) {
    var ct = new Date(b.created_at * 1000).toISOString().slice(0, 19).replace('T', ' ');
    html += '<tr><td style="padding:4px 8px;font-size:0.8rem;color:var(--text-dim)">Created</td><td style="padding:4px 8px;font-size:0.8rem">' + ct + '</td></tr>';
  }
  html += '</table>';

  // 2. Evidence table
  html += '<h3 style="font-size:0.9rem;margin-bottom:8px;color:var(--accent)">Evidence Log (' + (b.evidence ? b.evidence.length : 0) + ')</h3>';
  html += '<table style="width:100%;border-collapse:collapse;margin-bottom:14px;font-size:0.8rem">';
  html += '<thead><tr style="border-bottom:1px solid var(--border)"><th style="padding:4px 8px;text-align:left;color:var(--text-dim)">Time</th><th style="padding:4px 8px;text-align:left;color:var(--text-dim)">Source</th><th style="padding:4px 8px;text-align:left;color:var(--text-dim)">Description</th></tr></thead>';
  html += '<tbody>' + evidenceRows + '</tbody></table>';

  openModal(title, html);
}

async function loadCrisis() {
  try {
    const check = await fetchJSON('/api/crisis/check');
    document.getElementById('crisisSeverity').textContent = check.severity || 'none';
    document.getElementById('violations').textContent = check.violations.length;

    const pred = await fetchJSON('/api/crisis/predict?horizon=5');
    document.getElementById('riskLevel').textContent = pred.risk_level;

    // Drift info
    try {
      const drift = await fetchJSON('/api/values/drift');
      const di = document.getElementById('driftInfo');
      if (drift.overall_drifting) {
        di.innerHTML = `<div class="drift-warning">⚠️ Drift detected (value: ${drift.value_drift.overall_drift}, layer: ${drift.layer_drift.volatile_layers?.length || 0} volatile)</div>`;
      } else {
        di.innerHTML = `<div style="color:var(--text-dim);font-size:0.85rem;margin-top:8px;">✅ No drift detected</div>`;
      }
    } catch(e) {}
  } catch (e) { console.error('Crisis load error:', e); }
}

async function loadTimeline() {
  try {
    const tl = await fetchJSON('/api/timeline');
    const container = document.getElementById('timelineContent');
    let html = `<div style="margin-bottom:8px;font-size:0.85rem;color:var(--text-dim);">
      ${tl.snapshot_count} snapshots over ${tl.time_span || 'N/A'} | ${tl.milestones?.length || 0} milestones
    </div>`;

    // Recent snapshots
    if (tl.snapshots && tl.snapshots.length > 0) {
      html += '<div class="timeline-list">';
      const recent = tl.snapshots.slice(-10).reverse();
      for (const s of recent) {
        const t = new Date(s.timestamp * 1000).toISOString().slice(11, 19);
        const tag = s.tag ? `<span class="tl-tag">${s.tag}</span>` : '';
        const scores = Object.entries(s.scores || {}).map(([k, v]) => `${k}:${v.toFixed(0)}`).join(' ');
        html += `<div class="tl-item" style="cursor:pointer" onclick="openSnapshotDetail(${s.id})">
          <span><span class="tl-time">${t}</span> #${s.id} ${tag}</span>
          <span class="tl-scores">${scores}</span>
        </div>`;
      }
      html += '</div>';
    }

    // Milestones
    if (tl.milestones && tl.milestones.length > 0) {
      html += '<div style="margin-top:12px;"><h3>🏆 Milestones</h3>';
      for (const m of tl.milestones.slice(-5)) {
        const mSid = m.snapshot_id;
        const t = new Date(m.timestamp * 1000).toISOString().slice(11, 19);
        html += `<div class="milestone" style="cursor:pointer" onclick="openSnapshotDetail(${m.snapshot_id})">#${m.snapshot_id} @ ${t}: <span class="reason">${m.reasons.join(', ')}</span></div>`;
      }
    html += '</div>';
    }

    container.innerHTML = html;
  } catch (e) { document.getElementById('timelineContent').textContent = 'Error loading timeline'; }
}

async function loadAll() {
  await Promise.all([
    loadStatus(),
    loadNarrative(),
    loadSelfConcept(),
    loadSelfImage(),
    loadSelfPerception(),
    loadPersonality(),
    loadCharacteristics(),
    loadSkills(),
    loadRoles(),
    loadCoherence(),
    loadSelfNarrative(),
    loadPurpose(),
    loadDescription(),
    loadAspirations(),
    loadVitalSigns(),
    loadEvolution(),
    loadBeliefs(),
    loadLayerScores(),
    loadTraits(),
    loadValues(),
    loadCrisis(),
    loadTimeline(),
  ]);
  document.getElementById('lastUpdated').textContent = new Date().toLocaleTimeString();
}

// Auto-refresh
let autoTimer = null;
function setupAutoRefresh() {
  const cb = document.getElementById('autoRefresh');
  if (autoTimer) { clearInterval(autoTimer); autoTimer = null; }
  if (cb.checked) {
    autoTimer = setInterval(loadAll, 10000);
  }
}
document.getElementById('autoRefresh').addEventListener('change', setupAutoRefresh);

// Initial load
loadAll();
setupAutoRefresh();

// ── Drag-and-Drop ──
let draggedCardId = null;
let dragSourceZone = null;

document.addEventListener('dragstart', function(e) {
  var card = e.target.closest('.card[draggable]');
  if (!card) return;
  draggedCardId = card.dataset.cardId;
  dragSourceZone = card.closest('.drop-zone');
  card.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', draggedCardId);
});

document.addEventListener('dragend', function(e) {
  var card = e.target.closest('.card');
  if (card) card.classList.remove('dragging');
  document.querySelectorAll('.drag-over-zone').forEach(function(z) { z.classList.remove('drag-over-zone'); });
  document.querySelectorAll('.drag-over').forEach(function(c) { c.classList.remove('drag-over'); });
});

document.addEventListener('dragover', function(e) {
  var zone = e.target.closest('[data-drop-zone="true"]');
  if (zone) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; zone.classList.add('drag-over-zone'); }
  var card = e.target.closest('.card[draggable]');
  if (card && card.dataset.cardId !== draggedCardId) { e.preventDefault(); card.classList.add('drag-over'); }
});

document.addEventListener('dragleave', function(e) {
  var zone = e.target.closest('[data-drop-zone="true"]');
  if (zone) zone.classList.remove('drag-over-zone');
  var card = e.target.closest('.card');
  if (card) card.classList.remove('drag-over');
});

document.addEventListener('drop', function(e) {
  e.preventDefault();
  document.querySelectorAll('.drag-over-zone').forEach(function(z) { z.classList.remove('drag-over-zone'); });
  document.querySelectorAll('.drag-over').forEach(function(c) { c.classList.remove('drag-over'); });
  if (!draggedCardId) return;
  var targetZone = e.target.closest('[data-drop-zone="true"]');
  if (!targetZone) return;
  var draggedCard = document.querySelector('.card[data-card-id="' + draggedCardId + '"]');
  if (!draggedCard) return;
  if (targetZone === dragSourceZone) return;
  var insertBefore = e.target.closest('.card[draggable]');
  if (insertBefore && insertBefore.dataset.cardId !== draggedCardId && targetZone.contains(insertBefore)) {
    targetZone.insertBefore(draggedCard, insertBefore);
  } else {
    targetZone.appendChild(draggedCard);
  }
  saveLayout();
  updateLayoutStatus('saved');
});

// ── Rename ──
function startRename(btn, type) {
  var container = type === 'supercard' ? btn.closest('.supercard-header') : btn.closest('.card');
  var h2 = container.querySelector('h2');
  // Get text content excluding the edit button
  var fullText = '';
  for (var i = 0; i < h2.childNodes.length; i++) {
    var n = h2.childNodes[i];
    if (n.nodeType === 3 && n.textContent.trim()) fullText += n.textContent.trim();
  }
  var icon = fullText.match(/^[\u{1F000}-\u{1FFFF}]|^[\u2600-\u27BF}]|^[^\s]/u);
  var iconChar = icon ? icon[0] : '';
  var nameOnly = iconChar ? fullText.slice(iconChar.length).trim() : fullText;
  btn.style.display = 'none';
  var input = document.createElement('input');
  input.type = 'text';
  input.className = 'rename-input';
  input.value = nameOnly;
  input.dataset.icon = iconChar;
  input.dataset.type = type;
  h2.insertBefore(input, btn);
  input.focus();
  input.select();
  input.addEventListener('blur', function() { finishRename(input, h2, btn); });
  input.addEventListener('keydown', function(ev) {
    if (ev.key === 'Enter') { ev.preventDefault(); input.blur(); }
    if (ev.key === 'Escape') { ev.preventDefault(); input.value = nameOnly; input.blur(); }
  });
}

function finishRename(input, h2, btn) {
  var icon = input.dataset.icon || '';
  var type = input.dataset.type || 'card';
  var newName = input.value.trim();
  if (!newName) { input.remove(); btn.style.display = ''; return; }
  var fullText = icon ? icon + ' ' + newName : newName;
  // Remove all children except the edit button
  while (h2.firstChild && h2.firstChild !== btn) { h2.removeChild(h2.firstChild); }
  var textNode = document.createTextNode(fullText + ' ');
  h2.insertBefore(textNode, btn);
  input.remove();
  btn.style.display = '';
  // Save
  var layout = getLayout();
  if (type === 'card') {
    var card = btn.closest('.card');
    if (card && card.dataset.cardId) {
      if (!layout.cardNames) layout.cardNames = {};
      layout.cardNames[card.dataset.cardId] = fullText;
      saveLayoutObj(layout);
      updateLayoutStatus('renamed');
    }
  } else {
    var sc = btn.closest('.supercard');
    if (sc && sc.dataset.supercardId) {
      if (!layout.supercardNames) layout.supercardNames = {};
      layout.supercardNames[sc.dataset.supercardId] = fullText;
      saveLayoutObj(layout);
      updateLayoutStatus('renamed');
    }
  }
}

// ── Layout Persistence ──
function getDefaultLayout() {
  var layout = { supercards: [], cardNames: {}, supercardNames: {} };
  document.querySelectorAll('.supercard').forEach(function(sc) {
    var sid = sc.dataset.supercardId;
    if (!sid) return;
    var h2 = sc.querySelector('.supercard-header h2');
    var name = '';
    if (h2) { for (var i = 0; i < h2.childNodes.length; i++) { var n = h2.childNodes[i]; if (n.nodeType === 3 && n.textContent.trim()) name += n.textContent.trim(); } }
    layout.supercardNames[sid] = name || sid;
    var cards = [];
    sc.querySelectorAll('.card[data-card-id]').forEach(function(c) {
      var cid = c.dataset.cardId;
      var ch2 = c.querySelector('h2');
      var cname = '';
      if (ch2) { for (var i = 0; i < ch2.childNodes.length; i++) { var n = ch2.childNodes[i]; if (n.nodeType === 3 && n.textContent.trim()) cname += n.textContent.trim(); } }
      layout.cardNames[cid] = cname || cid;
      cards.push(cid);
    });
    layout.supercards.push({ id: sid, cards: cards });
  });
  return layout;
}

function getLayout() {
  try { var saved = localStorage.getItem('identity_dashboard_layout'); return saved ? JSON.parse(saved) : null; } catch(e) { return null; }
}

function saveLayoutObj(layout) {
  try { localStorage.setItem('identity_dashboard_layout', JSON.stringify(layout)); } catch(e) {}
}

function saveLayout() {
  var layout = { supercards: [], cardNames: {}, supercardNames: {} };
  document.querySelectorAll('.supercard').forEach(function(sc) {
    var sid = sc.dataset.supercardId;
    if (!sid) return;
    var h2 = sc.querySelector('.supercard-header h2');
    var name = '';
    if (h2) { for (var i = 0; i < h2.childNodes.length; i++) { var n = h2.childNodes[i]; if (n.nodeType === 3 && n.textContent.trim()) name += n.textContent.trim(); } }
    layout.supercardNames[sid] = name || sid;
    var cards = [];
    sc.querySelectorAll('.card[data-card-id]').forEach(function(c) { cards.push(c.dataset.cardId); });
    layout.supercards.push({ id: sid, cards: cards });
  });
  saveLayoutObj(layout);
}

function applyLayout(layout) {
  if (!layout || !layout.supercards) return;
  layout.supercards.forEach(function(sc) {
    var zone = document.querySelector('.supercard[data-supercard-id="' + sc.id + '"] .drop-zone');
    if (!zone) return;
    sc.cards.forEach(function(cid) {
      var card = document.querySelector('.card[data-card-id="' + cid + '"]');
      if (card && !zone.contains(card)) { zone.appendChild(card); }
    });
    sc.cards.forEach(function(cid, idx) {
      var card = document.querySelector('.card[data-card-id="' + cid + '"]');
      if (card && zone.contains(card)) {
        var ref = zone.children[idx];
        if (ref && ref !== card) zone.insertBefore(card, ref);
        else if (!ref) zone.appendChild(card);
      }
    });
  });
  // Apply custom names
  if (layout.supercardNames) {
    Object.keys(layout.supercardNames).forEach(function(sid) {
      var sc = document.querySelector('.supercard[data-supercard-id="' + sid + '"]');
      if (!sc) return;
      var h2 = sc.querySelector('.supercard-header h2');
      if (!h2) return;
      var btn = h2.querySelector('.edit-btn');
      while (h2.firstChild && h2.firstChild !== btn) { h2.removeChild(h2.firstChild); }
      var txt = document.createTextNode(layout.supercardNames[sid] + ' ');
      h2.insertBefore(txt, btn);
    });
  }
  if (layout.cardNames) {
    Object.keys(layout.cardNames).forEach(function(cid) {
      var card = document.querySelector('.card[data-card-id="' + cid + '"]');
      if (!card) return;
      var h2 = card.querySelector('h2');
      if (!h2) return;
      var btn = h2.querySelector('.edit-btn');
      while (h2.firstChild && h2.firstChild !== btn) { h2.removeChild(h2.firstChild); }
      var txt = document.createTextNode(layout.cardNames[cid] + ' ');
      h2.insertBefore(txt, btn);
    });
  }
}

function resetLayout() {
  localStorage.removeItem('identity_dashboard_layout');
  location.reload();
}

function saveLayoutSnapshot() {
  var layout = getDefaultLayout();
  layout._snapshot = true;
  layout._timestamp = new Date().toISOString();
  saveLayoutObj(layout);
  updateLayoutStatus('default-saved');
}

function updateLayoutStatus(msg) {
  var el = document.getElementById('layoutStatus');
  if (!el) return;
  var msgs = { saved: '\ud83d\udcbe Layout saved', renamed: '\u270f\ufe0f Name saved', default: '\ud83d\udcd0 Drag cards to reorder \u2022 Click \u270e to rename', 'default-saved': '\u2705 Saved as default layout' };
  el.textContent = msgs[msg] || msg;
  setTimeout(function() { el.textContent = msgs['default']; }, 3000);
}

// ── Init on load ──
(function() {
  var origLoadAll = window.loadAll;
  window.loadAll = async function() {
    if (origLoadAll) await origLoadAll();
    var layout = getLayout();
    if (layout && layout.supercards) applyLayout(layout);
    if (!getLayout()) { var def = getDefaultLayout(); def._default = true; saveLayoutObj(def); }
  
  // Init column picker visibility
  setTimeout(updateColPickerVisibility, 200);
};
  window._dashboardLoaded = true;
})();

// ── Create Supercard ──
function createSupercard() {
  var id = 'sc-' + Date.now();
  var layout = getLayout() || getDefaultLayout();
  layout.supercards.push({ id: id, cards: [] });
  if (!layout.supercardNames) layout.supercardNames = {};
  layout.supercardNames[id] = '📦 New Supercard';
  saveLayoutObj(layout);
  renderSupercard(id);
  updateLayoutStatus('created supercard');
}

function renderSupercard(sid) {
  var layout = getLayout();
  if (!layout) return;
  var scData = layout.supercards.find(function(s) { return s.id === sid; });
  if (!scData) return;
  var name = (layout.supercardNames && layout.supercardNames[sid]) || '📦 Supercard';
  var existing = document.querySelector('.supercard[data-supercard-id="' + sid + '"]');
  if (existing) return; // already rendered

  var html = '<div class="supercard" data-supercard-id="' + sid + '">';
  html += '<div class="supercard-header"><h2>' + name + ' <button class="edit-btn" title="Rename supercard" onclick="startRename(this,\'supercard\')">✎</button></h2>';
  html += '<span class="sc-count" style="display:inline-flex;align-items:center;gap:8px">0 cards</span><span class="sc-col-picker" data-sc-id="self-model" style="display:inline-flex;font-size:0.7rem;color:var(--text-dim);margin-left:4px;align-items:center;gap:2px">| Col: <button onclick="setZoneCols('self-model',1,'sc')" data-col="1" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">1</button><button onclick="setZoneCols('self-model',2,'sc')" data-col="2" class="active" style="background:none;border:1px solid var(--accent);border-radius:2px;color:var(--accent);cursor:pointer;padding:0 4px;font-size:0.65rem">2</button><button onclick="setZoneCols('self-model',3,'sc')" data-col="3" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">3</button><button onclick="setZoneCols('self-model',4,'sc')" data-col="4" style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">4</button></span>';
  html += '<span class="sc-col-picker" data-sc-id="' + sid + '" style="display:inline-flex;font-size:0.7rem;color:var(--text-dim);margin-left:4px;align-items:center;gap:2px">| Col: ';
  for (var c = 1; c <= 4; c++) html += '<button onclick="setZoneCols(\'' + sid + '\',' + c + ',\'sc\')" data-col="' + c + '"' + (c === 2 ? ' class="active"' : '') + ' style="background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem">' + c + '</button>';
  html += '</span></div>';
  html += '<div class="supercard-grid drop-zone" data-drop-zone="true"></div>';
  html += '<div class="supercard-footer">';
  html += '<button onclick="addCard(\'' + sid + '\')">➕ Add Card</button>';
  html += '<button onclick="addNestedCard(\'' + sid + '\',\'subcard\')">🔽 Add Subcard</button>';
  html += '<button onclick="deleteSupercard(\'' + sid + '\')" style="color:var(--red)">🗑️ Delete Supercard</button>';
  html += '</div></div>';

  // Insert before the create bar
  var createBar = document.querySelector('.create-supercard-bar');
  if (createBar) {
    createBar.insertAdjacentHTML('beforebegin', html);
  } else {
    document.querySelector('.layout-bar').insertAdjacentHTML('beforebegin', html);
  }

  // Add any saved cards
  if (scData.cards && scData.cards.length > 0) {
    scData.cards.forEach(function(cid) { renderCard(cid, sid); });
  }
  updateSupercardCount(sid);
}

function deleteSupercard(sid) {
  var sc = document.querySelector('.supercard[data-supercard-id="' + sid + '"]');
  if (!sc) return;
  var cards = sc.querySelectorAll('.card[data-card-id]');
  if (cards.length > 0) {
    if (!confirm('Delete this supercard and all its cards (' + cards.length + ' cards)?')) return;
  }
  sc.remove();
  var layout = getLayout();
  if (layout && layout.supercards) {
    layout.supercards = layout.supercards.filter(function(s) { return s.id !== sid; });
    saveLayoutObj(layout);
  }
  updateLayoutStatus('deleted supercard');
}

// ── Create Card ──
function addCard(supercardId) {
  var cid = 'c-' + Date.now();
  var layout = getLayout();
  if (!layout) return;
  var sc = layout.supercards.find(function(s) { return s.id === supercardId; });
  if (!sc) { sc = { id: supercardId, cards: [] }; layout.supercards.push(sc); }
  if (!sc.cards) sc.cards = [];
  sc.cards.push(cid);
  if (!layout.cardNames) layout.cardNames = {};
  layout.cardNames[cid] = '📄 New Card';
  // Default content
  if (!layout.cardContent) layout.cardContent = {};
  layout.cardContent[cid] = 'New card — edit this content.';
  if (!layout.cardSizes) layout.cardSizes = {};
  layout.cardSizes[cid] = 'm';
  saveLayoutObj(layout);
  renderCard(cid, supercardId);
  updateLayoutStatus('created card');
}

function addNestedCard(parentId, level) {
  var cid = 'c-' + Date.now();
  var layout = getLayout() || getDefaultLayout();
  // Find parent in the layout tree
  var parent = findCardInLayout(layout, parentId);
  if (!parent) {
    // Maybe it's a supercard
    var sc = layout.supercards.find(function(s) { return s.id === parentId; });
    if (sc) {
      if (!sc.cards) sc.cards = [];
      sc.cards.push(cid);
    }
  }
  if (!layout.cardNames) layout.cardNames = {};
  var levelLabel = { subcard: '📌 Subcard', partcard: '📎 Partcard', microcard: '🔬 Microcard' };
  layout.cardNames[cid] = levelLabel[level] || '📄 Card';
  if (!layout.cardLevels) layout.cardLevels = {};
  layout.cardLevels[cid] = level;
  if (!layout.cardSizes) layout.cardSizes = {};
  layout.cardSizes[cid] = 's';
  if (!layout.cardContent) layout.cardContent = {};
  layout.cardContent[cid] = 'Edit this ' + level + '.';
  saveLayoutObj(layout);
  renderCard(cid, parentId, level);
  updateLayoutStatus('added ' + level);
}

function findCardInLayout(layout, id) {
  function search(items) {
    if (!items) return null;
    for (var i = 0; i < items.length; i++) {
      if (items[i] === id || (typeof items[i] === 'object' && items[i].id === id)) return items[i];
      if (typeof items[i] === 'object' && items[i].cards) {
        var found = search(items[i].cards);
        if (found) return found;
      }
    }
    return null;
  }
  // Search supercards
  if (layout.supercards) {
    for (var i = 0; i < layout.supercards.length; i++) {
      var sc = layout.supercards[i];
      if (sc.id === id) return sc;
      if (sc.cards) {
        var found = search(sc.cards);
        if (found) return found;
      }
    }
  }
  return null;
}

function renderCard(cid, parentId, level) {
  var layout = getLayout();
  if (!layout) return;
  var name = (layout.cardNames && layout.cardNames[cid]) || '📄 Card';
  var size = (layout.cardSizes && layout.cardSizes[cid]) || 'm';
  var content = (layout.cardContent && layout.cardContent[cid]) || '';
  var cardLevel = level || (layout.cardLevels && layout.cardLevels[cid]) || 'card';

  var existing = document.querySelector('.card[data-card-id="' + cid + '"]');
  if (existing) return;

  var levelLabel = '';
  if (cardLevel !== 'card') levelLabel = '<span class="nest-indicator">(' + cardLevel + ')</span>';

  var html = '<div class="card" data-card-id="' + cid + '" draggable="true" data-level="' + cardLevel + '" data-size="' + size + '">';
  html += '<h2>' + name + ' ' + levelLabel + ' <button class="edit-btn" title="Rename" onclick="startRename(this,\'card\')">✎</button></h2>';
  html += '<div class="card-content" id="card-content-' + cid + '">';
  html += '<textarea class="card-content-editor" id="editor-' + cid + '" placeholder="Type card content here..." onblur="saveCardContent(\'' + cid + '\', this.value)">' + escapeHtml(content) + '</textarea>';
  html += '</div>';
  // Drop zone for subcards
  if (cardLevel === 'card' || cardLevel === 'subcard') {
    html += '<div class="drop-subcard-zone" data-drop-zone="true" data-parent="' + cid + '"></div>';
  }
  html += '<div class="card-footer">';
  html += '<button onclick="cycleCardSize(\'' + cid + '\')">📐 Size</button>';
  if (cardLevel === 'card') html += '<button onclick="addNestedCard(\'' + cid + '\',\'subcard\')">🔽 Sub</button>';
  if (cardLevel === 'subcard') html += '<button onclick="addNestedCard(\'' + cid + '\',\'partcard\')">📎 Part</button>';
  if (cardLevel === 'partcard') html += '<button onclick="addNestedCard(\'' + cid + '\',\'microcard\')">🔬 Micro</button>';
  html += '<button class="del-btn" onclick="deleteCard(\'' + cid + '\')">🗑️</button>';
  html += '</div></div>';

  // Insert into parent
  if (parentId) {
    var parentEl = document.querySelector('[data-supercard-id="' + parentId + '"] .drop-zone') ||
                   document.querySelector('[data-card-id="' + parentId + '"] .drop-subcard-zone') ||
                   document.querySelector('[data-card-id="' + parentId + '"]');
    if (parentEl) {
      parentEl.insertAdjacentHTML('beforeend', html);
    }
  } else {
    // Fallback: try to find by supercard
    var sc = document.querySelector('.supercard:first-child .drop-zone');
    if (sc) sc.insertAdjacentHTML('beforeend', html);
  }

  // Render nested children
  if (layout.supercards) {
    for (var i = 0; i < layout.supercards.length; i++) {
      var sc = layout.supercards[i];
      if (sc.cards) renderChildren(sc.cards, cid, layout);
    }
  }
  updateSupercardCounts();

  // Update column picker visibility
  updateColPickerVisibility();
}

function renderChildren(children, parentId, layout) {
  if (!children || !Array.isArray(children)) return;
  var idx = children.indexOf(parentId);
  // Actually we need to find items that have this parentId as their parent
  // The nesting is stored differently
  if (layout.cardParents) {
    Object.keys(layout.cardParents).forEach(function(cid) {
      if (layout.cardParents[cid] === parentId) {
        var lvl = (layout.cardLevels && layout.cardLevels[cid]) || 'subcard';
        renderCard(cid, parentId, lvl);
      }
    });
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function saveCardContent(cid, value) {
  var layout = getLayout();
  if (!layout) return;
  if (!layout.cardContent) layout.cardContent = {};
  layout.cardContent[cid] = value;
  saveLayoutObj(layout);
}

function deleteCard(cid) {
  var card = document.querySelector('.card[data-card-id="' + cid + '"]');
  if (!card) return;
  // Check if it has nested cards
  var nested = card.querySelectorAll('.card[data-card-id]');
  if (nested.length > 0) {
    if (!confirm('Delete this card and its ' + nested.length + ' nested cards?')) return;
  }
  card.remove();
  // Update layout
  var layout = getLayout();
  if (layout) {
    // Remove from supercards and parent cards
    if (layout.supercards) {
      layout.supercards.forEach(function(sc) {
        if (sc.cards) {
          var idx = sc.cards.indexOf(cid);
          if (idx >= 0) sc.cards.splice(idx, 1);
        }
      });
    }
    delete layout.cardNames[cid];
    delete layout.cardContent[cid];
    delete layout.cardSizes[cid];
    delete layout.cardLevels[cid];
    saveLayoutObj(layout);
  }
  updateSupercardCounts();
  updateLayoutStatus('deleted card');
}

function cycleCardSize(cid) {
  var card = document.querySelector('.card[data-card-id="' + cid + '"]');
  if (!card) return;
  var sizes = ['s', 'm', 'l', 'xl'];
  var cur = card.dataset.size || 'm';
  var next = sizes[(sizes.indexOf(cur) + 1) % sizes.length];
  card.dataset.size = next;
  // Save
  var layout = getLayout();
  if (layout) {
    if (!layout.cardSizes) layout.cardSizes = {};
    layout.cardSizes[cid] = next;
    saveLayoutObj(layout);
  }
}

function setColumns(sid, n) {
  var sc = document.querySelector('.supercard[data-supercard-id="' + sid + '"]');
  if (!sc) return;
  var grid = sc.querySelector('.drop-zone');
  if (!grid) return;
  // Remove all col classes
  for (var i = 1; i <= 6; i++) grid.classList.remove('grid-cols-' + i);
  if (n > 1) grid.classList.add('grid-cols-' + n);
  // Update button states
  sc.querySelectorAll('.col-picker button').forEach(function(b) {
    b.classList.toggle('active', parseInt(b.dataset.cols) === n);
  });
  // Save
  var layout = getLayout();
  if (layout) {
    if (!layout.columnCounts) layout.columnCounts = {};
    layout.columnCounts[sid] = n;
    saveLayoutObj(layout);
  }
}

function updateSupercardCount(sid) {
  var sc = document.querySelector('.supercard[data-supercard-id="' + sid + '"]');
  if (!sc) return;
  var count = sc.querySelectorAll('.card[data-card-id]').length;
  var el = sc.querySelector('.sc-count');
  if (el) el.textContent = count + ' card' + (count !== 1 ? 's' : '');
}

function updateSupercardCounts() {
  document.querySelectorAll('.supercard').forEach(function(sc) {
    var sid = sc.dataset.supercardId;
    if (sid) updateSupercardCount(sid);
  });
}

// ── Extend getDefaultLayout to capture nesting ──
var origGetDefaultLayout = window.getDefaultLayout || function() {};
window.getDefaultLayout = function() {
  var layout = { supercards: [], cardNames: {}, supercardNames: {}, cardContent: {}, cardSizes: {}, cardLevels: {}, columnCounts: {}, cardParents: {} };
  document.querySelectorAll('.supercard').forEach(function(sc) {
    var sid = sc.dataset.supercardId;
    if (!sid) return;
    var h2 = sc.querySelector('.supercard-header h2');
    var name = '';
    if (h2) { for (var i = 0; i < h2.childNodes.length; i++) { var n = h2.childNodes[i]; if (n.nodeType === 3 && n.textContent.trim()) name += n.textContent.trim(); } }
    layout.supercardNames[sid] = name || sid;
    // Column count
    var grid = sc.querySelector('.drop-zone');
    if (grid) {
      for (var c = 2; c <= 6; c++) { if (grid.classList.contains('grid-cols-' + c)) { layout.columnCounts[sid] = c; break; } }
    }
    // Cards - walk the DOM tree
    function collectCards(el, parentId) {
      var cards = [];
      el.querySelectorAll(':scope > .card[data-card-id]').forEach(function(card) {
        var cid = card.dataset.cardId;
        cards.push(cid);
        var ch2 = card.querySelector('h2');
        var cname = '';
        if (ch2) { for (var i = 0; i < ch2.childNodes.length; i++) { var n = ch2.childNodes[i]; if (n.nodeType === 3 && n.textContent.trim()) cname += n.textContent.trim(); } }
        layout.cardNames[cid] = cname || cid;
        layout.cardSizes[cid] = card.dataset.size || 'm';
        layout.cardLevels[cid] = card.dataset.level || 'card';
        if (parentId) layout.cardParents[cid] = parentId;
        // Content
        var editor = document.getElementById('editor-' + cid);
        if (editor) layout.cardContent[cid] = editor.value;
        // Nested
        var subZone = card.querySelector('.drop-subcard-zone');
        if (subZone) collectCards(subZone, cid);
      });
      return cards;
    }
    var topCards = collectCards(grid, null);
    layout.supercards.push({ id: sid, cards: topCards });
  });
  // Timeline
  var tl = document.querySelector('.card[data-card-id="timeline"]');
  if (tl) {
    var tlh2 = tl.querySelector('h2');
    layout.cardNames['timeline'] = tlh2 ? tlh2.textContent.replace('✎','').trim() : '📅 Snapshot Timeline';
    layout.cardSizes['timeline'] = tl.dataset.size || 'm';
  }
  return layout;
};

// ── Extend applyLayout to handle nesting, columns, sizes ──
var origApplyLayout = window.applyLayout || function(){};
window.applyLayout = function(layout) {
  if (!layout || !layout.supercards) return;
  // Apply column counts
  if (layout.columnCounts) {
    Object.keys(layout.columnCounts).forEach(function(sid) {
      var n = layout.columnCounts[sid];
      if (n > 1) setColumns(sid, n);
    });
  }
  // Apply card sizes
  if (layout.cardSizes) {
    Object.keys(layout.cardSizes).forEach(function(cid) {
      var card = document.querySelector('.card[data-card-id="' + cid + '"]');
      if (card) card.dataset.size = layout.cardSizes[cid];
    });
  }
  // Apply card levels
  if (layout.cardLevels) {
    Object.keys(layout.cardLevels).forEach(function(cid) {
      var card = document.querySelector('.card[data-card-id="' + cid + '"]');
      if (card) card.dataset.level = layout.cardLevels[cid];
    });
  }
  updateSupercardCounts();
};

// ── Extend saveLayout to include nesting ──
var origSaveLayout = window.saveLayout || function(){};
window.saveLayout = function() {
  var layout = getDefaultLayout();
  saveLayoutObj(layout);
};

// ── Extend resetLayout ──
var origResetLayout = window.resetLayout || function(){};
window.resetLayout = function() {
  if (!confirm('Reset layout to defaults? All custom cards and changes will be lost.')) return;
  localStorage.removeItem('identity_dashboard_layout');
  location.reload();
};

// ── Handle drag-drop for nesting ──
// Enhance existing drop handler to support nesting
document.addEventListener('drop', function(e) {
  e.preventDefault();
  document.querySelectorAll('.drag-over-zone').forEach(function(z) { z.classList.remove('drag-over-zone'); });
  document.querySelectorAll('.drag-over').forEach(function(c) { c.classList.remove('drag-over'); });
  if (!draggedCardId) return;

  // Check if dropped on a card (for nesting)
  var targetCard = e.target.closest('.card[data-card-id]');
  var targetZone = e.target.closest('[data-drop-zone="true"]');
  var draggedCard = document.querySelector('.card[data-card-id="' + draggedCardId + '"]');
  if (!draggedCard) return;

  if (targetCard && targetCard.dataset.cardId !== draggedCardId) {
    // Nesting: drop onto a card to make it a subcard
    var subZone = targetCard.querySelector('.drop-subcard-zone');
    var draggedLevel = draggedCard.dataset.level || 'card';
    var targetLevel = targetCard.dataset.level || 'card';

    // Determine new level based on target
    var newLevel = '';
    if (targetLevel === 'card') newLevel = 'subcard';
    else if (targetLevel === 'subcard') newLevel = 'partcard';
    else if (targetLevel === 'partcard') newLevel = 'microcard';
    else newLevel = 'microcard';

    if (subZone) {
      dragSourceZone = draggedCard.closest('.drop-zone') || draggedCard.closest('.drop-subcard-zone');
      subZone.appendChild(draggedCard);
      draggedCard.dataset.level = newLevel;

      // Re-render controls for new level
      // (leave existing controls, they'll update on next interaction)

      // Save parent relationship
      var layout = getLayout();
      if (layout) {
        if (!layout.cardParents) layout.cardParents = {};
        layout.cardParents[draggedCardId] = targetCard.dataset.cardId;
        if (!layout.cardLevels) layout.cardLevels = {};
        layout.cardLevels[draggedCardId] = newLevel;
        saveLayoutObj(layout);
        updateSupercardCounts();
      }
      updateLayoutStatus('nested as ' + newLevel);
      return;
    }
  }

  // If dropped on a zone (supercard grid), move there
  if (targetZone) {
    draggedCard.dataset.level = 'card';
    targetZone.appendChild(draggedCard);
    var layout = getLayout();
    if (layout) {
      delete layout.cardParents[draggedCardId];
      if (layout.cardLevels) layout.cardLevels[draggedCardId] = 'card';
      saveLayoutObj(layout);
      updateSupercardCounts();
    }
    updateLayoutStatus('moved');
  }
});

// ── Global Columns ──
function setGlobalColumns(n) {
  document.body.className = document.body.className.replace(/global-cols-\d+/g, '').trim();
  if (n > 1) document.body.classList.add('global-cols-' + n);
  // Update button states
  document.querySelectorAll('.global-col-picker button').forEach(function(b) {
    b.classList.toggle('active', parseInt(b.dataset.gcols) === n);
  });
  // Save
  var layout = getLayout();
  if (layout) { layout.globalColumns = n; saveLayoutObj(layout); }
}

// ── Extend getDefaultLayout to capture global columns ──
var __origGetDefault = window.getDefaultLayout || function(){};
window.getDefaultLayout = function() {
  var layout = __origGetDefault ? __origGetDefault() : { supercards: [], cardNames: {}, supercardNames: {}, cardContent: {}, cardSizes: {}, cardLevels: {}, cardParents: {} };
  // Get current global columns from body class
  for (var c = 1; c <= 4; c++) {
    if (document.body.classList.contains('global-cols-' + c)) {
      layout.globalColumns = c;
      break;
    }
  }
  return layout;
};

// ── Apply global columns on layout load ──
var __origApply = window.applyLayout || function(){};
window.applyLayout = function(layout) {
  if (__origApply) __origApply(layout);
  if (layout && layout.globalColumns) setGlobalColumns(layout.globalColumns);
};

// ── Init global columns on page load ──
(function() {
  var layout = getLayout();
  if (layout && layout.globalColumns) {
    setGlobalColumns(layout.globalColumns);
  }
})();

// ── Per-zone Column Control ──
function setZoneCols(id, n, type) {
  var zone;
  if (type === 'sc') {
    zone = document.querySelector('.supercard[data-supercard-id="' + id + '"] .drop-zone');
    // Update button states
    document.querySelectorAll('.supercard[data-supercard-id="' + id + '"] .sc-col-picker button').forEach(function(b) {
      b.classList.toggle('active', parseInt(b.dataset.col) === n);
    });
  } else {
    zone = document.querySelector('.card[data-card-id="' + id + '"] .drop-subcard-zone');
    if (!zone) zone = document.querySelector('.card[data-card-id="' + id + '"] .card-content + .drop-subcard-zone');
    document.querySelectorAll('.card[data-card-id="' + id + '"] .card-col-picker button').forEach(function(b) {
      b.classList.toggle('active', parseInt(b.dataset.col) === n);
    });
  }
  if (!zone) return;
  // Remove existing col classes
  for (var ci = 1; ci <= 4; ci++) zone.classList.remove('zone-cols-' + ci);
  if (n > 1) zone.classList.add('zone-cols-' + n);
  // Save
  var layout = getLayout();
  if (layout) {
    if (!layout.zoneCols) layout.zoneCols = {};
    layout.zoneCols[id] = n;
    saveLayoutObj(layout);
  }
}

// ── Update column picker visibility based on content ──
function addColPickerToFooter(card, cid) {
  if (!card) return;
  var footer = card.querySelector('.card-footer');
  if (!footer) return;
  // Check if picker already exists
  if (footer.querySelector('.card-col-picker')) return;
  var picker = document.createElement('span');
  picker.className = 'card-col-picker';
  picker.style.cssText = 'display:none;margin-left:6px;font-size:0.7rem;color:var(--text-dim)';
  picker.innerHTML = '| Col: ';
  for (var ci = 1; ci <= 4; ci++) {
    var btn = document.createElement('button');
    btn.textContent = ci;
    btn.onclick = function(n) { return function() { setZoneCols(cid, n, 'nested'); }; }(ci);
    btn.dataset.col = ci;
    btn.style.cssText = 'background:none;border:1px solid var(--border);border-radius:2px;color:var(--text-dim);cursor:pointer;padding:0 4px;font-size:0.65rem';
    if (ci === 2) btn.style.borderColor = 'var(--accent)';
    picker.appendChild(btn);
  }
  footer.appendChild(picker);
}

function updateColPickerVisibility() {
  // Supercards: show col picker if cards > 0
  document.querySelectorAll('.supercard').forEach(function(sc) {
    var sid = sc.dataset.supercardId;
    var cards = sc.querySelectorAll(':scope > .drop-zone > .card[data-card-id]');
    sc.classList.toggle('has-cards', cards.length > 0);
    // Restore saved column count
    var layout = getLayout();
    if (layout && layout.zoneCols && layout.zoneCols[sid]) {
      setZoneCols(sid, layout.zoneCols[sid], 'sc');
    }
  });
  // Cards: show col picker if subcards > 0
  document.querySelectorAll('.card[data-card-id]').forEach(function(card) {
    var cid = card.dataset.cardId;
    if (!cid) return;
    var subcards = card.querySelectorAll(':scope > .drop-subcard-zone > .card[data-card-id]');
    card.classList.toggle('has-subcards', subcards.length > 0);
    // Add column picker to footer if card has or could have subcards
    addColPickerToFooter(card, cid);
    // Restore saved column count
    var layout = getLayout();
    if (layout && layout.zoneCols && layout.zoneCols[cid]) {
      setZoneCols(cid, layout.zoneCols[cid], 'nested');
    }
  });
}

// Extend existing functions to call updateColPickerVisibility
var __origAddCard = window.addCard || function(){};
window.addCard = function(sid) {
  if (__origAddCard) __origAddCard(sid);
  setTimeout(updateColPickerVisibility, 50);
};

var __origAddNested = window.addNestedCard || function(){};
window.addNestedCard = function(pid, level) {
  if (__origAddNested) __origAddNested(pid, level);
  setTimeout(updateColPickerVisibility, 50);
};

var __origDeleteCard = window.deleteCard || function(){};
window.deleteCard = function(cid) {
  if (__origDeleteCard) __origDeleteCard(cid);
  setTimeout(updateColPickerVisibility, 100);
};

// Extend the existing drop handler to update visibility
// The drop handler is registered with addEventListener, so we add another listener
document.addEventListener('drop', function(e) {
  setTimeout(updateColPickerVisibility, 100);
});
</script>


<!-- Layout Controls -->
<div class="layout-bar">
  <span id="layoutStatus">📐 Drag cards to reorder • Click ✎ to rename</span>
  <button onclick="resetLayout()" title="Restore default card arrangement">↺ Reset Layout</button>
  <button onclick="saveLayoutSnapshot()" title="Save current layout as default">💾 Save as Default</button>
</div>

<!-- Modal overlay for clickable tooltips -->
<div id="detailModal" style="display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.7);z-index:1000;justify-content:center;align-items:center;backdrop-filter:blur(4px)" onclick="closeModal(event)">
  <div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;max-width:800px;width:90vw;max-height:85vh;overflow-y:auto;padding:24px;position:relative;box-shadow:0 8px 32px rgba(0,0,0,0.5)" onclick="event.stopPropagation()">
    <button style="position:absolute;top:12px;right:16px;background:none;border:none;color:var(--text-dim);font-size:22px;cursor:pointer" onclick="closeModal()">&times;</button>
    <div id="modalTitle" style="font-size:1.1rem;font-weight:600;margin-bottom:16px;padding-right:24px"></div>
    <div id="modalBody"></div>
  </div>
</div>
<script>
function closeModal(e) {
  document.getElementById('detailModal').style.display = 'none';
}

async function openSnapshotDetail(id) {
  try {
    const snap = await fetchJSON('/api/snapshots/' + id);
    if (!snap || !snap.snapshot_id) { openModal('Snapshot #' + id, '<p style="color:var(--text-dim)">Snapshot not found</p>'); return; }
    var ts = new Date(snap.timestamp * 1000).toISOString().slice(0, 19).replace('T', ' ');
    var html = '';

    // Metadata bar
    html += '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px;font-size:0.85rem">';
    html += '<span><span style="color:var(--text-dim)">Time:</span> ' + ts + '</span>';
    html += '<span><span style="color:var(--text-dim)">Version:</span> ' + (snap.version || '—') + '</span>';
    html += '<span><span style="color:var(--text-dim)">Origin:</span> ' + (snap.origin || '—') + '</span>';
    html += '<span><span style="color:var(--text-dim)">Tag:</span> ' + (snap.tag || '—') + '</span>';
    if (snap.crisis_active) html += '<span style="color:var(--red)">🚨 Crisis</span>';
    html += '</div>';

    // 1. Layer scores table
    html += '<h3 style="font-size:0.9rem;margin-bottom:8px;color:var(--accent)">Layer Scores</h3>';
    html += '<table style="width:100%;border-collapse:collapse;margin-bottom:14px;font-size:0.85rem">';
    html += '<thead><tr style="border-bottom:1px solid var(--border)">' +
      '<th style="padding:4px 8px;text-align:left;color:var(--text-dim)">Layer</th>' +
      '<th style="padding:4px 8px;text-align:right;color:var(--text-dim)">Score</th>' +
      '<th style="padding:4px 8px;text-align:left;color:var(--text-dim)">Bar</th></tr></thead><tbody>';
    var layerEntries = Object.entries(snap.layer_scores || {});
    for (var i = 0; i < layerEntries.length; i++) {
      var lid = layerEntries[i][0], ld = layerEntries[i][1];
      var sc = ld.score || 0;
      var col = sc >= 50 ? 'var(--green)' : (sc >= 20 ? 'var(--yellow)' : 'var(--red)');
      html += '<tr><td style="padding:3px 8px">' + lid + '</td>' +
        '<td style="padding:3px 8px;text-align:right">' + sc.toFixed(1) + '</td>' +
        '<td style="padding:3px 8px"><span style="display:inline-block;height:12px;width:' + Math.min(100, sc) + '%;background:' + col + ';border-radius:3px"></span></td></tr>';
    }
    html += '</tbody></table>';

    // 2. Value axioms table
    var axEntries = Object.entries(snap.value_axioms || {});
    if (axEntries.length > 0) {
      html += '<h3 style="font-size:0.9rem;margin-bottom:8px;color:var(--accent)">Value Axioms</h3>';
      html += '<table style="width:100%;border-collapse:collapse;margin-bottom:14px;font-size:0.85rem">';
      html += '<thead><tr style="border-bottom:1px solid var(--border)">' +
        '<th style="padding:4px 8px;text-align:left;color:var(--text-dim)">Axiom</th>' +
        '<th style="padding:4px 8px;text-align:right;color:var(--text-dim)">Reinforcements</th>' +
        '<th style="padding:4px 8px;text-align:right;color:var(--text-dim)">Weight</th>' +
        '<th style="padding:4px 8px;text-align:center;color:var(--text-dim)">Confidence</th></tr></thead><tbody>';
      for (var i = 0; i < axEntries.length; i++) {
        var an = axEntries[i][0], as = axEntries[i][1];
        html += '<tr><td style="padding:3px 8px">' + an + '</td>' +
          '<td style="padding:3px 8px;text-align:right">' + (as.reinforced_count || '0') + '</td>' +
          '<td style="padding:3px 8px;text-align:right">' + (as.weight || 1.0).toFixed(1) + '</td>' +
          '<td style="padding:3px 8px;text-align:center">' + ((as.confidence || 0) * 100).toFixed(0) + '%</td></tr>';
      }
      html += '</tbody></table>';
    }

    // 3. Narrative
    if (snap.narrative) {
      html += '<h3 style="font-size:0.9rem;margin-bottom:8px;color:var(--accent)">Narrative</h3>';
      html += '<div style="font-style:italic;padding:8px;background:var(--bg);border-radius:6px;font-size:0.85rem;margin-bottom:14px">' + snap.narrative + '</div>';
    }

    // 4. Stats summary + traits mini-chart
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px">';

    // Stats sub-table
    html += '<div class="subcard"><div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:6px;text-transform:uppercase">Stats</div>';
    html += '<table style="width:100%;font-size:0.8rem">';
    html += '<tr><td style="padding:2px 4px;color:var(--text-dim)">Attempts</td><td style="padding:2px 4px;text-align:right">' + (snap.total_attempts || 0) + '</td></tr>';
    html += '<tr><td style="padding:2px 4px;color:var(--text-dim)">Successes</td><td style="padding:2px 4px;text-align:right">' + (snap.successful_applications || 0) + '</td></tr>';
    html += '<tr><td style="padding:2px 4px;color:var(--text-dim)">KG Raw</td><td style="padding:2px 4px;text-align:right">' + (snap.kg_nodes_raw || 0) + '</td></tr>';
    html += '<tr><td style="padding:2px 4px;color:var(--text-dim)">KG Consol.</td><td style="padding:2px 4px;text-align:right">' + (snap.kg_nodes_consolidated || 0) + '</td></tr>';
    html += '</table></div>';

    // Traits mini-chart
    var tEntries = Object.entries(snap.traits || {});
    if (tEntries.length > 0) {
      html += '<div class="subcard"><div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:6px;text-transform:uppercase">Traits</div>';
      html += '<table style="width:100%;font-size:0.8rem">';
      for (var i = 0; i < tEntries.length; i++) {
        var tn = tEntries[i][0], td = tEntries[i][1];
        var ts = typeof td === 'object' ? (td.score || 50) : td;
        html += '<tr><td style="padding:1px 4px;color:var(--text-dim)">' + tn.replace(/_/g, ' ') + '</td>' +
          '<td style="padding:1px 4px;text-align:right">' + ts.toFixed(0) + '</td></tr>';
      }
      html += '</table></div>';
    }
    html += '</div>';

    openModal('Snapshot #' + id, html);
  } catch(e) {
    openModal('Snapshot #' + id, '<p style="color:var(--red)">Error loading snapshot</p>');
  }
}

function openModal(title, html) {
  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalBody').innerHTML = html;
  document.getElementById('detailModal').style.display = 'flex';
}
</script>
</body>
</html>
"""


# ── Dashboard App Factory ───────────────────────────────────────

def create_dashboard_app(components: Optional[dict] = None) -> FastAPI:
    """Create the dashboard FastAPI application.

    The dashboard serves a single-page HTML app and proxies API calls
    to the same server.
    """
    from identity_app.api import create_app

    # Create the underlying API app with the same components
    api_app = create_app(components)

    app = FastAPI(
        title="Identity Dashboard",
        description="Visual dashboard for the Identity App",
        version="1.0.0",
    )

    # Mount the API at /api
    app.mount("/api", api_app)

    # Serve the dashboard at /
    @app.get("/", response_class=HTMLResponse)
    @app.get("/dashboard", response_class=HTMLResponse)
    async def get_dashboard():
        return DASHBOARD_HTML

    return app


# ── Direct Run ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    app = create_dashboard_app()
    uvicorn.run(app, host="127.0.0.1", port=8500, log_level="info")
