"""Build a standalone static HTML snapshot for GitHub Pages."""

import json, time, sys
from urllib.request import urlopen

API = "http://127.0.0.1:8080"

# Fetch live data
data = {
    "status": json.loads(urlopen(API + "/api/status").read()),
    "health": json.loads(urlopen(API + "/api/health").read()),
    "layers": json.loads(urlopen(API + "/api/layers").read()),
    "concept": json.loads(urlopen(API + "/api/self-model/concept").read()),
    "axioms": json.loads(urlopen(API + "/api/value-axioms").read()),
    "snapshots": json.loads(urlopen(API + "/api/snapshots").read()),
    "timeline": json.loads(urlopen(API + "/api/metrics/timeline").read()),
    "pulses": json.loads(urlopen(API + "/api/pulses?limit=10").read()),
    "pulse_latest": json.loads(urlopen(API + "/api/pulses/latest").read()),
    "kg": json.loads(urlopen(API + "/api/knowledge-graph").read()),
}

S = data["status"]
H = data["health"]
C = data["concept"]
A = data["axioms"]
snaps = data["snapshots"]["snapshots"]
pulses = data["pulses"]["pulses"]
latest = data["pulse_latest"]
kg = data["kg"]
timeline = data["timeline"]["timeline"]

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

layer_names = {"L1":"Execution","L2":"Planning","L3":"Self-Direction","L4":"Optimizer","L5":"Evolution","L6":"Identity"}
now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

# Build layer cards
layer_cards = ""
for lid in ["L1","L2","L3","L4","L5","L6"]:
    sc = S["layer_scores"][lid]["score"]
    color = "var(--green)" if sc >= 60 else "var(--yellow)" if sc >= 30 else "var(--red)"
    layer_cards += f"""
    <div class="layer-card">
      <div class="layer-score" style="color:{color}">{round(sc)}</div>
      <div class="layer-name">{lid}: {layer_names[lid]}</div>
      <div class="layer-bar"><div class="layer-fill" style="width:{sc}%;background:{color}"></div></div>
    </div>"""

# Build layer detail
layer_detail = ""
for lid in ["L1","L2","L3","L4","L5","L6"]:
    info = S["layer_scores"][lid]
    metrics = "".join(f'<div class="stat-row"><span class="stat-label">{k}</span><span class="stat-value">{v}</span></div>' for k,v in info["metrics"].items())
    layer_detail += f"""
    <div class="card">
      <h3>{lid}: {layer_names[lid]} <span style="float:right">{round(info['score'])}/100</span></h3>
      {metrics}
    </div>"""

# Build axiom display
axiom_html = "".join(
    f'<div class="stat-row"><span class="stat-label">{n}</span><span class="stat-value">'
    f'x{s.get("reinforced_count",0)} (w:{A["weights"].get(n,1.0):.1f})</span></div>'
    for n, s in A["axioms"].items()
)

# Build snapshots
snap_html = "".join(
    f'<div style="font-size:13px;padding:4px 0;border-bottom:1px solid var(--border)">'
    f'#{s["snapshot_id"]} -- {time.strftime("%Y-%m-%d %H:%M", time.gmtime(s["timestamp"]))}</div>'
    for s in snaps[-5:]
) if snaps else '<p style="color:var(--text2)">No snapshots</p>'

# Build pulse list
pulse_html = "".join(
    f'<div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:14px">'
    f'<strong>Pulse {p["pulse_id"]}</strong> '
    f'<span style="color:var(--text2);margin-left:12px">{p.get("phase","")}</span>'
    f'<span style="float:right">{p.get("decision","")} (conf={p.get("confidence","")})</span></div>'
    for p in pulses
)

# Build timeline data for JS
timeline_json = json.dumps(timeline)
latest_json = json.dumps(latest, indent=2)[:2000]

health_class = "stat-good" if H["healthy"] else "stat-bad"
health_text = "OK" if H["healthy"] else "CRISIS"

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RSIS Portal -- Static Snapshot</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
:root {{ --bg:#0d1117; --surface:#161b22; --surface2:#21262d; --border:#30363d; --text:#e6edf3; --text2:#8b949e; --accent:#58a6ff; --green:#3fb950; --yellow:#d29922; --red:#f85149; --purple:#bc8cff; --font:'Segoe UI',system-ui,sans-serif; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:var(--font); }}
.layout {{ display:flex; min-height:100vh; }}
.sidebar {{ width:240px; background:var(--surface); border-right:1px solid var(--border); padding:20px 0; flex-shrink:0; }}
.sidebar h1 {{ font-size:14px; font-weight:600; padding:0 20px 20px; color:var(--accent); }}
.sidebar .version {{ font-size:11px; color:var(--text2); padding:0 20px 20px; margin-top:-12px; }}
.nav-item {{ padding:10px 20px; cursor:pointer; font-size:14px; color:var(--text2); transition:.15s; }}
.nav-item:hover,.nav-item.active {{ background:var(--surface2); color:var(--accent); }}
.nav-item.active {{ border-left:3px solid var(--accent); }}
.main {{ flex:1; padding:24px 32px; overflow-y:auto; max-height:100vh; }}
.tab {{ display:none; }} .tab.active {{ display:block; }}
h2 {{ font-size:20px; font-weight:600; margin-bottom:20px; }}
h3 {{ font-size:15px; font-weight:500; color:var(--text2); margin-bottom:12px; }}
.card {{ background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:20px; margin-bottom:16px; }}
.card-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:16px; }}
.stat-row {{ display:flex; justify-content:space-between; padding:6px 0; font-size:14px; }}
.stat-label {{ color:var(--text2); }} .stat-value {{ font-weight:500; }}
.stat-good {{ color:var(--green); }} .stat-warn {{ color:var(--yellow); }} .stat-bad {{ color:var(--red); }}
.layer-card {{ background:var(--surface); border:1px solid var(--border); border-radius:8px; padding:16px; text-align:center; }}
.layer-score {{ font-size:32px; font-weight:700; }}
.layer-name {{ font-size:12px; color:var(--text2); margin-top:4px; }}
.layer-bar {{ height:6px; background:var(--surface2); border-radius:3px; margin-top:10px; overflow:hidden; }}
.layer-fill {{ height:100%; border-radius:3px; }}
.chart-container {{ height:250px; margin-top:10px; }}
.axiom-tag {{ display:inline-block; padding:3px 10px; border-radius:12px; font-size:12px; margin:2px; background:var(--surface2); border:1px solid var(--border); }}
.footer {{ text-align:center; padding:20px; font-size:12px; color:var(--text2); }}
a {{ color:var(--accent); }}
@media (max-width:768px) {{ .layout {{ flex-direction:column; }} .sidebar {{ width:100%; }} .main {{ padding:16px; }} }}
</style>
</head>
<body>
<div class="layout">
<nav class="sidebar">
  <h1>RSIS Portal</h1>
  <div class="version">v{S['version']} -- Static Snapshot</div>
  <div class="nav-item active" data-tab="dashboard">Dashboard</div>
  <div class="nav-item" data-tab="layers">Layers</div>
  <div class="nav-item" data-tab="identity">Identity</div>
  <div class="nav-item" data-tab="pulses">Pulses</div>
  <div class="nav-item" data-tab="about">About</div>
</nav>
<main class="main">

<div class="tab active" id="tab-dashboard">
  <h2>System Dashboard</h2>
  <div class="card-grid">
    <div class="card"><h3>System Status</h3>
      <div class="stat-row"><span class="stat-label">Version</span><span class="stat-value">{S['version']}</span></div>
      <div class="stat-row"><span class="stat-label">Narrative</span><span class="stat-value" style="font-size:12px">{esc(C['current_narrative'][:100])}</span></div>
      <div class="stat-row"><span class="stat-label">KG Nodes</span><span class="stat-value">{kg['total_nodes_raw']} raw / {kg['total_nodes_consolidated']} con.</span></div>
      <div class="stat-row"><span class="stat-label">Snapshots</span><span class="stat-value">{S['snapshot_count']}</span></div>
    </div>
    <div class="card"><h3>Success Metrics</h3>
      <div class="stat-row"><span class="stat-label">Attempts</span><span class="stat-value">{S['total_attempts']}</span></div>
      <div class="stat-row"><span class="stat-label">Successful</span><span class="stat-value stat-good">{S['successful_applications']}</span></div>
      <div class="stat-row"><span class="stat-label">Success Rate</span><span class="stat-value">{S['success_rate']}%</span></div>
      <div class="stat-row"><span class="stat-label">Health</span><span class="stat-value {health_class}">{health_text}</span></div>
    </div>
  </div>
  <div class="card-grid" id="layerGrid">{layer_cards}</div>
  <div class="chart-container"><canvas id="timelineChart"></canvas></div>
</div>

<div class="tab" id="tab-layers">
  <h2>Layer Detail</h2>
  <div class="card-grid" id="layerDetail">{layer_detail}</div>
  <div class="card-grid">
    <div class="card"><h3>Latest Pulse</h3>
      <div class="stat-row"><span class="stat-label">Pulse</span><span class="stat-value">{latest['pulse_id']}</span></div>
      <div class="stat-row"><span class="stat-label">Phase</span><span class="stat-value">{latest['phase']}</span></div>
      <div class="stat-row"><span class="stat-label">Decision</span><span class="stat-value">{latest['decision']}</span></div>
      <div class="stat-row"><span class="stat-label">Confidence</span><span class="stat-value">{latest['confidence']}</span></div>
    </div>
    <div class="card"><h3>Knowledge Graph</h3>
      <div class="stat-row"><span class="stat-label">Raw Nodes</span><span class="stat-value">{kg['total_nodes_raw']}</span></div>
      <div class="stat-row"><span class="stat-label">Consolidated</span><span class="stat-value">{kg['total_nodes_consolidated']}</span></div>
      <div class="stat-row"><span class="stat-label">Utility</span><span class="stat-value">{kg.get('utility_density',0)}%</span></div>
    </div>
  </div>
</div>

<div class="tab" id="tab-identity">
  <h2>Identity Viewer</h2>
  <div class="card-grid">
    <div class="card"><h3>Self-Concept</h3>
      <p style="font-size:13px;margin-bottom:8px"><strong>Purpose:</strong> {esc(C['purpose'])}</p>
      <p style="font-size:13px;margin-bottom:8px"><strong>Narrative:</strong> {esc(C['current_narrative'])}</p>
      <p style="font-size:13px;color:var(--text2)">{esc(C['self_description'])}</p>
    </div>
    <div class="card"><h3>Core Beliefs</h3>
      {"".join(f'<div class="axiom-tag">{esc(b)}</div>' for b in C['core_beliefs'])}
      <h3 style="margin-top:12px">Aspirations</h3>
      {"".join(f'<div style="font-size:13px;padding:2px 0;color:var(--text2)">rarr; {esc(a)}</div>' for a in C['aspirations'])}
    </div>
  </div>
  <div class="card-grid">
    <div class="card"><h3>Value Axioms</h3>{axiom_html}</div>
    <div class="card"><h3>Snapshots</h3>{snap_html}</div>
  </div>
</div>

<div class="tab" id="tab-pulses">
  <h2>Pulse Logs</h2>
  <div class="card">{pulse_html}</div>
  <div class="card"><h3>Latest Pulse Detail</h3>
    <pre style="font-size:12px;color:var(--text2);overflow-x:auto;max-height:500px">{latest_json}</pre>
  </div>
</div>

<div class="tab" id="tab-about">
  <h2>About RSIS</h2>
  <div class="card">
    <p style="font-size:14px;line-height:1.7;margin-bottom:12px"><strong>RSIS</strong> -- Recursive Self-Improving System. An autonomous architecture operating across 9 functional layers.</p>
    <p style="font-size:14px;line-height:1.7;margin-bottom:12px">Static snapshot generated from live system telemetry.</p>
    <p style="font-size:13px;color:var(--text2)">Source: <a href="https://github.com/gemquota/rsisb">github.com/gemquota/rsisb</a></p>
  </div>
  <div class="card-grid">
    <div class="card"><h3>Modules</h3>
      <div style="font-size:13px;line-height:1.8;color:var(--text2)">
        - Identity Core (self-model, snapshots, values, crisis)<br>
        - Codegen Engine (AST parser, Jinja2 templates)<br>
        - Evaluator (4-phase reasoning)<br>
        - State Machine (5-state lifecycle)<br>
        - Recovery Manager (git rollback)<br>
        - L3 Self-Direction (signals, goals, queue)<br>
        - RRP Protocol (ambiguity, constraints, decisions)<br>
        - FastAPI Server (36 routes)<br>
        - Frontend Portal
      </div>
    </div>
    <div class="card"><h3>Stats</h3>
      <div class="stat-row"><span class="stat-label">Tests</span><span class="stat-value">70</span></div>
      <div class="stat-row"><span class="stat-label">API Routes</span><span class="stat-value">36</span></div>
      <div class="stat-row"><span class="stat-label">Pulses</span><span class="stat-value">{len(pulses)}</span></div>
      <div class="stat-row"><span class="stat-label">Snapshots</span><span class="stat-value">{len(snaps)}</span></div>
    </div>
  </div>
</div>

</main>
</div>
<div class="footer">RSIS &middot; {now} &middot; Static snapshot</div>

<script>
document.querySelectorAll('.nav-item').forEach(function(item) {{
  item.addEventListener('click', function() {{
    document.querySelectorAll('.nav-item').forEach(function(n) {{ n.classList.remove('active'); }});
    document.querySelectorAll('.tab').forEach(function(t) {{ t.classList.remove('active'); }});
    item.classList.add('active');
    document.getElementById('tab-' + item.dataset.tab).classList.add('active');
  }});
}});

var timelineData = {timeline_json};
if (timelineData.length > 0) {{
  var ctx = document.getElementById('timelineChart').getContext('2d');
  var labels = timelineData.map(function(t) {{ return 'S#' + t.snapshot_id; }});
  var datasets = [];
  var layerIds = ['L1','L2','L3','L4','L5','L6'];
  var colors = ['#3fb950','#58a6ff','#d29922','#bc8cff','#f85149','#79c0ff'];
  layerIds.forEach(function(lid, i) {{
    datasets.push({{
      label: lid,
      data: timelineData.map(function(t) {{ return t[lid] || 0; }}),
      borderColor: colors[i],
      backgroundColor: colors[i] + '22',
      fill: true,
      tension: 0.3,
      pointRadius: 3
    }});
  }});
  new Chart(ctx, {{
    type: 'line',
    data: {{ labels: labels, datasets: datasets }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ labels: {{ color: '#8b949e' }} }} }},
      scales: {{
        x: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }},
        y: {{ min: 0, max: 100, ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }}
      }}
    }}
  }});
}}
</script>
</body>
</html>"""

import os
os.makedirs("docs", exist_ok=True)
with open("docs/index.html", "w") as f:
    f.write(html)
print(f"Static snapshot: {len(html):,} bytes written to docs/index.html")
