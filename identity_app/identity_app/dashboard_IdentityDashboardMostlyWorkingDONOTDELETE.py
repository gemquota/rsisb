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
  <span id="lastUpdated">—</span>
</div>

<div class="grid">
  <!-- Narrative -->
  <div class="card">
    <h2>📖 Current Narrative</h2>
    <div class="narrative-box" id="narrative">Loading...</div>
  </div>

  <!-- Self-Concept (expanded) -->
  <div class="card">
    <h2>🎯 Self-Concept</h2>
    <div id="selfConceptContent" style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div class="subcard" style="grid-column:1/-1">
        <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px">Purpose</div>
        <div id="scPurpose" style="font-size:0.85rem;font-style:italic">Loading...</div>
      </div>
      <div class="subcard">
        <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px">Self-Description</div>
        <div id="scDescription" style="font-size:0.8rem">Loading...</div>
      </div>
      <div class="subcard">
        <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px">Narrative</div>
        <div id="scNarrative" style="font-size:0.8rem;font-style:italic">Loading...</div>
      </div>
      <div class="subcard" style="grid-column:1/-1">
        <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px">Aspirations</div>
        <div id="scAspirations" style="font-size:0.85rem">Loading...</div>
      </div>
    </div>
  </div>

  <!-- Core Beliefs -->
  <div class="card">
    <h2>📜 Core Beliefs</h2>
    <div id="beliefsContent">
      <div id="beliefsTags" style="margin-bottom:8px">Loading...</div>
      <div style="margin-top:8px"><strong style="font-size:0.85rem">Active Beliefs</strong></div>
      <div id="beliefsList" style="font-size:0.85rem;color:var(--text-dim);margin-top:4px">Loading...</div>
    </div>
  </div>

  <!-- Crisis Status -->
  <div class="card">
    <h2>🚨 Crisis Status</h2>
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
</div>

<div class="grid">
  <!-- Layer Scores -->
  <div class="card">
    <h2>📊 Layer Scores</h2>
    <div id="layerScores"></div>
  </div>

  <!-- Identity Traits -->
  <div class="card">
    <h2>🧬 Identity Traits</h2>
    <div id="traits"></div>
  </div>
</div>

<div class="grid">
  <!-- Value Axioms -->
  <div class="card">
    <h2>⚖️ Value Axioms</h2>
    <div id="axioms"></div>
  </div>

  <!-- Stats -->
  <div class="card">
    <h2>📈 System Stats</h2>
    <div class="stat-grid">
      <div class="stat"><div class="num" id="statSnapshots">—</div><div class="lbl">Snapshots</div></div>
      <div class="stat"><div class="num" id="statAttempts">—</div><div class="lbl">Attempts</div></div>
      <div class="stat"><div class="num" id="statSuccessRate">—</div><div class="lbl">Success Rate</div></div>
      <div class="stat"><div class="num" id="statBalance">—</div><div class="lbl">Axiom Balance</div></div>
    </div>
  </div>
</div>

<!-- Timeline -->
<div class="card">
  <h2>📅 Snapshot Timeline</h2>
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
    document.getElementById('scPurpose').textContent = sc.purpose || '(not set)';
    document.getElementById('scDescription').textContent = sc.self_description || '(not set)';
    document.getElementById('scNarrative').textContent = sc.current_narrative || '(no narrative)';
    const aspirationsDiv = document.getElementById('scAspirations');
    if (sc.aspirations && sc.aspirations.length > 0) {
      aspirationsDiv.innerHTML = sc.aspirations.map(a => '<div style="padding:2px 0">✦ ' + a + '</div>').join('');
    } else {
      aspirationsDiv.innerHTML = '(none)';
    }
  } catch (e) { console.error('Self-concept load error:', e); }
}

async function loadBeliefs() {
  try {
    const data = await fetchJSON('/api/self/beliefs');
    const entries = Object.entries(data);
    const tagsDiv = document.getElementById('beliefsTags');
    const listDiv = document.getElementById('beliefsList');

    // Core beliefs as clickable tags
    const scData = await fetchJSON('/api/self');
    const coreBeliefs = (scData.self_concept && scData.self_concept.core_beliefs) || [];
    if (coreBeliefs.length > 0) {
      tagsDiv.innerHTML = coreBeliefs.map((b, i) =>
        '<span class="axiom-tag" style="cursor:pointer" onclick="openBeliefDetail(' + i + ')">' + b + '</span>'
      ).join(' ');
    } else {
      tagsDiv.innerHTML = '(none)';
    }
    // Store for the detail popup
    window._coreBeliefsData = coreBeliefs;
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
</script>

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
