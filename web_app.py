"""
Web-based interactive power flow solver.
Run: python web_app.py
Then open http://localhost:5050
"""

from flask import Flask, render_template_string, request, jsonify
import pandapower as pp
import pandapower.networks as pn
import networkx as nx

app = Flask(__name__)

# Global network state
net = None
pos = None


def init_network(load_scale=1.0):
    """Create IEEE 14-bus network with optional load scaling."""
    global net, pos
    net = pn.case14()
    net.load["p_mw"] *= load_scale
    net.load["q_mvar"] *= load_scale
    pp.runpp(net)

    G = nx.Graph()
    for _, row in net.line.iterrows():
        G.add_edge(int(row["from_bus"]), int(row["to_bus"]))
    for _, row in net.trafo.iterrows():
        G.add_edge(int(row["hv_bus"]), int(row["lv_bus"]))
    pos = nx.kamada_kawai_layout(G)


def get_network_data():
    """Return network state as JSON-friendly dict for the frontend."""
    buses = []
    for idx in net.bus.index:
        vm = float(net.res_bus.loc[idx, "vm_pu"])
        is_gen = (
            int(idx) in net.gen["bus"].values or int(idx) in net.ext_grid["bus"].values
        )
        # Get load at this bus
        bus_loads = net.load[net.load["bus"] == idx]
        p_load = float(bus_loads["p_mw"].sum()) if len(bus_loads) > 0 else 0.0
        q_load = float(bus_loads["q_mvar"].sum()) if len(bus_loads) > 0 else 0.0
        # Get generation at this bus
        p_gen = 0.0
        q_gen = 0.0
        if int(idx) in net.ext_grid["bus"].values:
            eg = net.ext_grid[net.ext_grid["bus"] == idx]
            for ei in eg.index:
                p_gen += float(net.res_ext_grid.loc[ei, "p_mw"])
                q_gen += float(net.res_ext_grid.loc[ei, "q_mvar"])
        if int(idx) in net.gen["bus"].values:
            g = net.gen[net.gen["bus"] == idx]
            for gi in g.index:
                p_gen += float(net.res_gen.loc[gi, "p_mw"])
                q_gen += float(net.res_gen.loc[gi, "q_mvar"])
        # Get base kV
        vn_kv = float(net.bus.loc[idx, "vn_kv"])
        buses.append(
            {
                "id": int(idx),
                "x": float(pos[idx][0]),
                "y": float(pos[idx][1]),
                "vm_pu": vm,
                "vn_kv": vn_kv,
                "is_gen": is_gen,
                "p_load": p_load,
                "q_load": q_load,
                "p_gen": p_gen,
                "q_gen": q_gen,
            }
        )

    lines = []
    for idx in net.line.index:
        loading = float(net.res_line.loc[idx, "loading_percent"])
        p_from = float(net.res_line.loc[idx, "p_from_mw"])
        p_to = float(net.res_line.loc[idx, "p_to_mw"])
        lines.append(
            {
                "id": int(idx),
                "from_bus": int(net.line.loc[idx, "from_bus"]),
                "to_bus": int(net.line.loc[idx, "to_bus"]),
                "loading": loading,
                "p_from_mw": p_from,
                "p_to_mw": p_to,
            }
        )

    trafos = []
    for idx in net.trafo.index:
        loading = float(net.res_trafo.loc[idx, "loading_percent"])
        trafos.append(
            {
                "id": int(idx),
                "hv_bus": int(net.trafo.loc[idx, "hv_bus"]),
                "lv_bus": int(net.trafo.loc[idx, "lv_bus"]),
                "loading": loading,
                "tap_pos": int(net.trafo.loc[idx, "tap_pos"])
                if "tap_pos" in net.trafo.columns
                and str(net.trafo.loc[idx, "tap_pos"]) != "nan"
                else 0,
            }
        )

    gens = []
    for idx in net.ext_grid.index:
        gens.append(
            {
                "type": "ext_grid",
                "id": int(idx),
                "bus": int(net.ext_grid.loc[idx, "bus"]),
                "vm_pu": float(net.ext_grid.loc[idx, "vm_pu"]),
            }
        )
    for idx in net.gen.index:
        gens.append(
            {
                "type": "gen",
                "id": int(idx),
                "bus": int(net.gen.loc[idx, "bus"]),
                "vm_pu": float(net.gen.loc[idx, "vm_pu"]),
                "p_mw": float(net.gen.loc[idx, "p_mw"]),
            }
        )

    shunts = []
    for idx in net.shunt.index:
        shunts.append(
            {
                "id": int(idx),
                "bus": int(net.shunt.loc[idx, "bus"]),
                "q_mvar": float(net.shunt.loc[idx, "q_mvar"]),
            }
        )

    violations = int(
        (net.res_bus["vm_pu"] < 0.95).sum() + (net.res_bus["vm_pu"] > 1.05).sum()
    )
    overloads = int((net.res_line["loading_percent"] > 100).sum())

    return {
        "buses": buses,
        "lines": lines,
        "trafos": trafos,
        "gens": gens,
        "shunts": shunts,
        "violations": violations,
        "overloads": overloads,
        "converged": bool(net.converged),
    }


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/network")
def api_network():
    return jsonify(get_network_data())


@app.route("/api/set_gen", methods=["POST"])
def api_set_gen():
    data = request.json
    gen_type = data["type"]
    idx = int(data["id"])
    vm = float(data["vm_pu"])
    if gen_type == "ext_grid":
        net.ext_grid.at[idx, "vm_pu"] = vm
    else:
        net.gen.at[idx, "vm_pu"] = vm
    pp.runpp(net)
    return jsonify(get_network_data())


@app.route("/api/add_shunt", methods=["POST"])
def api_add_shunt():
    data = request.json
    bus = int(data["bus"])
    q = float(data["q_mvar"])
    existing = net.shunt[net.shunt["bus"] == bus]
    if len(existing) > 0:
        net.shunt.at[existing.index[0], "q_mvar"] = q
    else:
        pp.create_shunt(net, bus=bus, q_mvar=q, p_mw=0)
    pp.runpp(net)
    return jsonify(get_network_data())


@app.route("/api/remove_shunt", methods=["POST"])
def api_remove_shunt():
    data = request.json
    idx = int(data["id"])
    net.shunt.drop(idx, inplace=True)
    pp.runpp(net)
    return jsonify(get_network_data())


@app.route("/api/set_tap", methods=["POST"])
def api_set_tap():
    data = request.json
    idx = int(data["id"])
    tap = int(data["tap_pos"])
    net.trafo.at[idx, "tap_pos"] = tap
    pp.runpp(net)
    return jsonify(get_network_data())


@app.route("/api/reset", methods=["POST"])
def api_reset():
    data = request.json or {}
    scale = float(data.get("load_scale", 1.0))
    init_network(load_scale=scale)
    return jsonify(get_network_data())


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Power Flow Solver</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; display: flex; height: 100vh; }
#sidebar { width: 320px; background: #16213e; padding: 20px; overflow-y: auto; border-right: 1px solid #0f3460; }
#main { flex: 1; display: flex; flex-direction: column; }
#canvas-container { flex: 1; position: relative; }
canvas { width: 100%; height: 100%; }
h1 { font-size: 1.3em; margin-bottom: 10px; color: #4fc3f7; }
h2 { font-size: 1em; margin: 15px 0 8px; color: #81d4fa; border-bottom: 1px solid #0f3460; padding-bottom: 4px; }
.status-bar { background: #0f3460; padding: 10px 20px; display: flex; gap: 20px; font-size: 0.9em; }
.status-ok { color: #4caf50; }
.status-warn { color: #ff9800; }
.status-bad { color: #f44336; }
.control-group { margin-bottom: 8px; display: flex; align-items: center; gap: 6px; font-size: 0.85em; }
.control-group label { min-width: 90px; }
.control-group input, .control-group select { background: #1a1a2e; border: 1px solid #0f3460; color: #eee; padding: 4px 8px; border-radius: 4px; width: 70px; }
button { background: #0f3460; color: #4fc3f7; border: 1px solid #4fc3f7; padding: 5px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em; }
button:hover { background: #4fc3f7; color: #1a1a2e; }
.btn-danger { border-color: #f44336; color: #f44336; }
.btn-danger:hover { background: #f44336; color: #fff; }
#instructions { background: #0d1b3e; padding: 12px; border-radius: 6px; font-size: 0.8em; line-height: 1.5; margin-bottom: 15px; }
#instructions strong { color: #4fc3f7; }
.shunt-row { display: flex; align-items: center; gap: 4px; margin: 4px 0; font-size: 0.8em; }
</style>
</head>
<body>

<div id="sidebar">
  <h1>⚡ Power Flow Solver</h1>
  <div id="instructions">
    <strong>Goal:</strong> Keep all bus voltages between 0.95–1.05 pu and line loading under 100%.<br><br>
    <strong>Controls:</strong><br>
    • Adjust generator voltage setpoints<br>
    • Add shunt compensation (negative Q = capacitive)<br>
    • Change transformer tap positions<br>
    • Increase load scale for a challenge
  </div>

  <h2>Load Scale</h2>
  <div class="control-group">
    <input type="range" id="load-scale" min="0.5" max="3.0" step="0.1" value="1.0" style="width:140px">
    <span id="load-scale-val">1.0x</span>
    <button onclick="resetNetwork()">Apply</button>
  </div>

  <h2>Generators</h2>
  <div id="gen-controls"></div>

  <h2>Transformers</h2>
  <div id="trafo-controls"></div>

  <h2>Shunt Compensation</h2>
  <div id="shunt-controls"></div>
  <div class="control-group" style="margin-top:8px">
    <label>Bus:</label>
    <input type="number" id="new-shunt-bus" min="0" max="13" value="9" style="width:50px">
    <label>Q:</label>
    <input type="number" id="new-shunt-q" step="1" value="-10" style="width:60px">
    <button onclick="addShunt()">Add</button>
  </div>

  <h2 style="margin-top:20px">
    <button onclick="resetNetwork()" style="width:100%">🔄 Reset Network</button>
  </h2>
</div>

<div id="main">
  <div id="status-bar" class="status-bar">
    <span>Loading...</span>
  </div>
  <div id="canvas-container">
    <canvas id="network-canvas"></canvas>
  </div>
</div>

<script>
let networkData = null;
const canvas = document.getElementById('network-canvas');
const ctx = canvas.getContext('2d');

function resizeCanvas() {
  const container = document.getElementById('canvas-container');
  canvas.width = container.clientWidth * window.devicePixelRatio;
  canvas.height = container.clientHeight * window.devicePixelRatio;
  canvas.style.width = container.clientWidth + 'px';
  canvas.style.height = container.clientHeight + 'px';
  ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
  if (networkData) drawNetwork();
}
window.addEventListener('resize', resizeCanvas);

async function fetchNetwork() {
  const res = await fetch('/api/network');
  networkData = await res.json();
  updateUI();
  drawNetwork();
}

function updateUI() {
  // Status bar
  const sb = document.getElementById('status-bar');
  const v = networkData.violations;
  const o = networkData.overloads;
  const conv = networkData.converged;
  sb.innerHTML = `
    <span class="${conv ? 'status-ok' : 'status-bad'}">PF: ${conv ? 'Converged' : 'FAILED'}</span>
    <span class="${v === 0 ? 'status-ok' : 'status-warn'}">Voltage violations: ${v}</span>
    <span class="${o === 0 ? 'status-ok' : 'status-bad'}">Line overloads: ${o}</span>
  `;

  // Generator controls
  const gc = document.getElementById('gen-controls');
  gc.innerHTML = networkData.gens.map(g => `
    <div class="control-group">
      <label>${g.type === 'ext_grid' ? 'Slack' : 'Gen'} (Bus ${g.bus}):</label>
      <input type="number" step="0.01" min="0.9" max="1.1" value="${g.vm_pu.toFixed(3)}"
        onchange="setGen('${g.type}', ${g.id}, this.value)">
      <span>pu</span>
    </div>
  `).join('');

  // Trafo controls
  const tc = document.getElementById('trafo-controls');
  tc.innerHTML = networkData.trafos.map(t => `
    <div class="control-group">
      <label>T${t.id} (${t.hv_bus}→${t.lv_bus}):</label>
      <input type="number" step="1" min="-10" max="10" value="${t.tap_pos}"
        onchange="setTap(${t.id}, this.value)">
      <span>tap</span>
    </div>
  `).join('');

  // Shunt controls
  const sc = document.getElementById('shunt-controls');
  sc.innerHTML = networkData.shunts.map(s => `
    <div class="shunt-row">
      Bus ${s.bus}: ${s.q_mvar.toFixed(1)} Mvar
      <button class="btn-danger" onclick="removeShunt(${s.id})">✕</button>
    </div>
  `).join('') || '<div style="font-size:0.8em;color:#888">None</div>';
}

function drawNetwork() {
  const w = canvas.width / window.devicePixelRatio;
  const h = canvas.height / window.devicePixelRatio;
  ctx.clearRect(0, 0, w, h);

  // Transform network coords to canvas
  const padding = 60;
  const xs = networkData.buses.map(b => b.x);
  const ys = networkData.buses.map(b => b.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const scaleX = (w - padding * 2) / (maxX - minX || 1);
  const scaleY = (h - padding * 2) / (maxY - minY || 1);
  const scale = Math.min(scaleX, scaleY);

  function tx(x) { return padding + (x - minX) * scale + ((w - padding*2) - (maxX-minX)*scale)/2; }
  function ty(y) { return padding + (y - minY) * scale + ((h - padding*2) - (maxY-minY)*scale)/2; }

  const busPos = {};
  networkData.buses.forEach(b => { busPos[b.id] = { x: tx(b.x), y: ty(b.y) }; });

  // Draw lines
  networkData.lines.forEach(l => {
    const from = busPos[l.from_bus], to = busPos[l.to_bus];
    if (!from || !to) return;
    const color = l.loading < 50 ? '#4caf50' : l.loading < 80 ? '#ff9800' : '#f44336';
    const lw = 2 + l.loading / 40;
    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.strokeStyle = color;
    ctx.lineWidth = lw;
    ctx.stroke();

    // Flow arrow and MW label at midpoint
    const mx = (from.x + to.x) / 2, my = (from.y + to.y) / 2;
    const flow = Math.abs(l.p_from_mw);
    ctx.fillStyle = '#aaa';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${flow.toFixed(1)} MW`, mx, my - 6);
    ctx.fillText(`${l.loading.toFixed(0)}%`, mx, my + 10);

    // Draw flow direction arrow
    const dir = l.p_from_mw >= 0 ? 1 : -1;
    const dx = to.x - from.x, dy = to.y - from.y;
    const len = Math.sqrt(dx*dx + dy*dy);
    if (len > 0) {
      const ux = dx/len * dir, uy = dy/len * dir;
      const ax = mx + ux*12, ay = my + uy*12;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(ax - ux*8 - uy*4, ay - uy*8 + ux*4);
      ctx.lineTo(ax - ux*8 + uy*4, ay - uy*8 - ux*4);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
    }
  });

  // Draw trafos (dashed)
  networkData.trafos.forEach(t => {
    const from = busPos[t.hv_bus], to = busPos[t.lv_bus];
    if (!from || !to) return;
    const color = t.loading < 50 ? '#4caf50' : t.loading < 80 ? '#ff9800' : '#f44336';
    ctx.beginPath();
    ctx.setLineDash([6, 4]);
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.setLineDash([]);
  });

  // Draw buses
  networkData.buses.forEach(b => {
    const p = busPos[b.id];
    const color = b.vm_pu < 0.95 ? '#42a5f5' : b.vm_pu > 1.05 ? '#ef5350' : '#66bb6a';
    const r = b.is_gen ? 16 : 10;

    ctx.beginPath();
    if (b.is_gen) {
      ctx.rect(p.x - r, p.y - r, r*2, r*2);
    } else {
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
    }
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Label
    ctx.fillStyle = '#ccc';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`Bus ${b.id} (${b.vn_kv} kV)`, p.x, p.y - r - 18);
    ctx.fillText(`${b.vm_pu.toFixed(3)} pu | ${(b.vm_pu * b.vn_kv).toFixed(1)} kV`, p.x, p.y - r - 6);

    // Show gen or load info below
    ctx.font = '9px sans-serif';
    if (b.is_gen && (b.p_gen !== 0 || b.q_gen !== 0)) {
      ctx.fillStyle = '#4fc3f7';
      ctx.fillText(`G: ${Math.abs(b.p_gen).toFixed(1)}MW ${Math.abs(b.q_gen).toFixed(1)}Mvar`, p.x, p.y + r + 12);
    }
    if (b.p_load > 0 || b.q_load > 0) {
      ctx.fillStyle = '#ffab91';
      ctx.fillText(`L: ${b.p_load.toFixed(1)}MW ${b.q_load.toFixed(1)}Mvar`, p.x, p.y + r + (b.is_gen ? 24 : 12));
    }
  });

  // Legend
  ctx.font = '11px sans-serif';
  ctx.textAlign = 'left';
  const lx = 15, ly = h - 80;
  [['#66bb6a', '0.95 ≤ V ≤ 1.05'], ['#42a5f5', 'V < 0.95'], ['#ef5350', 'V > 1.05']].forEach(([c, t], i) => {
    ctx.fillStyle = c;
    ctx.fillRect(lx, ly + i*18, 12, 12);
    ctx.fillStyle = '#ccc';
    ctx.fillText(t, lx + 18, ly + i*18 + 10);
  });
}

async function setGen(type, id, value) {
  const res = await fetch('/api/set_gen', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ type, id, vm_pu: parseFloat(value) })
  });
  networkData = await res.json();
  updateUI(); drawNetwork();
}

async function setTap(id, value) {
  const res = await fetch('/api/set_tap', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ id, tap_pos: parseInt(value) })
  });
  networkData = await res.json();
  updateUI(); drawNetwork();
}

async function addShunt() {
  const bus = parseInt(document.getElementById('new-shunt-bus').value);
  const q = parseFloat(document.getElementById('new-shunt-q').value);
  const res = await fetch('/api/add_shunt', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ bus, q_mvar: q })
  });
  networkData = await res.json();
  updateUI(); drawNetwork();
}

async function removeShunt(id) {
  const res = await fetch('/api/remove_shunt', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ id })
  });
  networkData = await res.json();
  updateUI(); drawNetwork();
}

async function resetNetwork() {
  const scale = parseFloat(document.getElementById('load-scale').value);
  const res = await fetch('/api/reset', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ load_scale: scale })
  });
  networkData = await res.json();
  updateUI(); drawNetwork();
}

document.getElementById('load-scale').addEventListener('input', function() {
  document.getElementById('load-scale-val').textContent = this.value + 'x';
});

// Init
resizeCanvas();
fetchNetwork();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    init_network()
    print("Starting server at http://localhost:5050")
    app.run(port=5050, debug=False)
