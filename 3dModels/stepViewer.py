"""Interactive 3D viewer for STEP (.step/.stp) models.

Tessellates STEP files using `build123d` and opens a self-contained, offline
WebGL2 viewer in the default web browser with orbit/pan/zoom controls,
2.54 mm PCB reference grid at Z=0, origin axes, bounding-box readout, and
per-part visibility toggles.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Any

from build123d import Color, Compound, Shape, import_step

DEFAULT_MODELS_DIR = Path(__file__).resolve().parent / "stepModels"
DEFAULT_COLOR = (0.65, 0.70, 0.76, 1.0)
GENERIC_LABELS = {"", "COMPOUND", "SOLID", "SHELL", "FACE"}


def _rgba_from_color(color: Color | None) -> tuple[float, float, float, float]:
    if color is None:
        return DEFAULT_COLOR
    values = tuple(float(v) for v in color)
    if len(values) >= 4:
        return (values[0], values[1], values[2], values[3])
    if len(values) == 3:
        return (values[0], values[1], values[2], 1.0)
    return DEFAULT_COLOR


def _collect_meshes(
    shape: Shape,
    tolerance: float,
    inherited_label: str = "",
    inherited_color: Color | None = None,
) -> list[dict[str, Any]]:
    """Recursively tessellate a STEP shape tree into mesh dictionaries."""
    raw_label = getattr(shape, "label", "") or ""
    label = (
        raw_label
        if raw_label not in GENERIC_LABELS
        else (inherited_label or "Part")
    )
    color = shape.color if shape.color is not None else inherited_color

    if isinstance(shape, Compound) and shape.children:
        meshes: list[dict[str, Any]] = []
        for child in shape.children:
            meshes.extend(
                _collect_meshes(
                    child,
                    tolerance=tolerance,
                    inherited_label=label,
                    inherited_color=color,
                )
            )
        return meshes

    verts, tris = shape.tessellate(tolerance)
    if not verts or not tris:
        return []

    positions: list[float] = []
    for v in verts:
        positions.extend((round(v.X, 4), round(v.Y, 4), round(v.Z, 4)))

    indices: list[int] = []
    for tri in tris:
        indices.extend((int(tri[0]), int(tri[1]), int(tri[2])))

    rgba = _rgba_from_color(color)
    return [
        {
            "label": label,
            "color": [round(c, 4) for c in rgba],
            "positions": positions,
            "indices": indices,
        }
    ]


def load_step_model(path: Path, tolerance: float = 0.05) -> dict[str, Any]:
    """Load a STEP file and return a JSON-serializable viewer payload."""
    if not path.is_file():
        raise FileNotFoundError(f"STEP file not found: {path}")

    shape = import_step(str(path))
    bbox = shape.bounding_box()
    raw_meshes = _collect_meshes(shape, tolerance=tolerance)

    # Group meshes that share the same (label, color) so multi-pin compounds
    # appear as a single toggleable entry in the parts panel.
    grouped: dict[tuple[str, tuple[float, ...]], dict[str, Any]] = {}
    for mesh in raw_meshes:
        key = (mesh["label"], tuple(mesh["color"]))
        if key not in grouped:
            grouped[key] = {
                "label": mesh["label"],
                "color": mesh["color"],
                "positions": list(mesh["positions"]),
                "indices": list(mesh["indices"]),
            }
        else:
            target = grouped[key]
            offset = len(target["positions"]) // 3
            target["positions"].extend(mesh["positions"])
            target["indices"].extend(i + offset for i in mesh["indices"])

    return {
        "name": path.name,
        "path": str(path.resolve()),
        "bbox": {
            "min": [
                round(bbox.min.X, 3),
                round(bbox.min.Y, 3),
                round(bbox.min.Z, 3),
            ],
            "max": [
                round(bbox.max.X, 3),
                round(bbox.max.Y, 3),
                round(bbox.max.Z, 3),
            ],
            "size": [
                round(bbox.size.X, 3),
                round(bbox.size.Y, 3),
                round(bbox.size.Z, 3),
            ],
        },
        "parts": list(grouped.values()),
    }


def _resolve_step_files(paths: list[Path]) -> list[Path]:
    """Expand file/directory arguments into a sorted list of STEP files."""
    targets = paths if paths else [DEFAULT_MODELS_DIR]
    resolved: list[Path] = []
    for target in targets:
        if target.is_dir():
            found = sorted(
                p
                for p in target.iterdir()
                if p.is_file() and p.suffix.lower() in {".step", ".stp"}
            )
            resolved.extend(found)
        elif target.is_file():
            resolved.append(target)
        else:
            raise FileNotFoundError(f"Path not found: {target}")

    if not resolved:
        raise FileNotFoundError(
            "No .step/.stp files found in "
            + ", ".join(str(t) for t in targets)
        )
    return resolved


def build_viewer_html(models: list[dict[str, Any]]) -> str:
    """Build a self-contained offline WebGL2 HTML page for the loaded models."""
    models_json = json.dumps(models, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    title = models[0]["name"] if len(models) == 1 else "STEP Model Viewer"
    return _HTML_TEMPLATE.replace("__TITLE__", title).replace(
        "__MODELS_JSON__", models_json
    )


def view_step_files(
    paths: list[Path] | None = None,
    tolerance: float = 0.05,
    output_html: Path | None = None,
    open_browser: bool = True,
) -> Path:
    """Generate the HTML viewer for one or more STEP files and open it."""
    step_files = _resolve_step_files(paths or [])
    models = [load_step_model(p, tolerance=tolerance) for p in step_files]
    html = build_viewer_html(models)

    if output_html is not None:
        output_html.parent.mkdir(parents=True, exist_ok=True)
        output_html.write_text(html, encoding="utf-8")
        html_path = output_html.resolve()
    else:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".html",
            prefix="step_viewer_",
            encoding="utf-8",
            delete=False,
        ) as tmp:
            tmp.write(html)
            html_path = Path(tmp.name).resolve()

    if open_browser:
        webbrowser.open(html_path.as_uri())

    return html_path


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>__TITLE__</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #14171c;
    --panel: rgba(24, 28, 36, 0.92);
    --border: rgba(255, 255, 255, 0.12);
    --text: #e6ebf2;
    --muted: #98a2b3;
    --accent: #4c9aff;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    height: 100%;
    overflow: hidden;
    background: var(--bg);
    color: var(--text);
    font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    font-size: 13px;
  }
  #canvas {
    width: 100%;
    height: 100%;
    display: block;
    cursor: grab;
  }
  #canvas:active { cursor: grabbing; }
  .panel {
    position: fixed;
    top: 12px;
    left: 12px;
    width: 280px;
    max-height: calc(100vh - 24px);
    overflow-y: auto;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
    backdrop-filter: blur(8px);
    user-select: none;
  }
  h1 {
    margin: 0 0 10px;
    font-size: 14px;
    font-weight: 600;
    word-break: break-all;
  }
  .section {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid var(--border);
  }
  .label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    margin-bottom: 6px;
  }
  select {
    width: 100%;
    background: #1f242e;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 6px 8px;
    margin-bottom: 8px;
  }
  .btn-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }
  button {
    background: #232936;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
    cursor: pointer;
  }
  button:hover { border-color: var(--accent); }
  button.active {
    background: #264366;
    border-color: var(--accent);
  }
  .dim-table {
    width: 100%;
    border-collapse: collapse;
    font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    font-size: 12px;
  }
  .dim-table td { padding: 2px 0; }
  .dim-table td:last-child { text-align: right; color: var(--muted); }
  .part-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 0;
    cursor: pointer;
  }
  .swatch {
    width: 12px;
    height: 12px;
    border-radius: 3px;
    border: 1px solid rgba(255,255,255,0.25);
    flex-shrink: 0;
  }
  .help {
    position: fixed;
    bottom: 12px;
    left: 12px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 6px 10px;
    color: var(--muted);
    font-size: 11px;
  }
</style>
</head>
<body>
<canvas id="canvas"></canvas>

<div class="panel">
  <select id="modelSelect" style="display:none"></select>
  <h1 id="modelName"></h1>

  <div class="section">
    <div class="label">Camera</div>
    <div class="btn-grid">
      <button data-view="iso">Iso</button>
      <button data-view="top">Top</button>
      <button data-view="bottom">Bottom</button>
      <button data-view="front">Front</button>
      <button data-view="right">Right</button>
      <button data-view="fit">Fit</button>
    </div>
  </div>

  <div class="section">
    <div class="label">Display</div>
    <div class="btn-grid">
      <button id="toggleGrid" class="active">Grid 2.54</button>
      <button id="toggleAxes" class="active">Axes</button>
      <button id="toggleWire">Wireframe</button>
    </div>
  </div>

  <div class="section">
    <div class="label">Dimensions (mm)</div>
    <table class="dim-table" id="dimTable"></table>
  </div>

  <div class="section">
    <div class="label">Parts</div>
    <div id="partsList"></div>
  </div>
</div>

<div class="help">
  Left-drag: Orbit &middot; Right-drag / Shift+drag: Pan &middot; Scroll: Zoom
</div>

<script>
const MODELS = __MODELS_JSON__;

const canvas = document.getElementById("canvas");
const gl = canvas.getContext("webgl2", { antialias: true });
if (!gl) {
  document.body.innerHTML = "<p style='padding:24px'>WebGL2 is required.</p>";
  throw new Error("WebGL2 unavailable");
}

// --- Shaders ---
const MESH_VS = `#version 300 es
in vec3 aPos;
in vec3 aNorm;
uniform mat4 uMVP;
uniform mat4 uModel;
out vec3 vNorm;
out vec3 vWorldPos;
void main() {
  vNorm = mat3(uModel) * aNorm;
  vec4 wp = uModel * vec4(aPos, 1.0);
  vWorldPos = wp.xyz;
  gl_Position = uMVP * vec4(aPos, 1.0);
}`;

const MESH_FS = `#version 300 es
precision highp float;
in vec3 vNorm;
in vec3 vWorldPos;
uniform vec4 uColor;
uniform vec3 uCamPos;
uniform bool uWire;
out vec4 outColor;
void main() {
  if (uWire) {
    outColor = vec4(0.82, 0.88, 0.96, 1.0);
    return;
  }
  vec3 N = normalize(vNorm);
  if (!gl_FrontFacing) N = -N;
  vec3 V = normalize(uCamPos - vWorldPos);
  vec3 L1 = normalize(vec3(0.55, -0.75, 0.95));
  vec3 L2 = normalize(vec3(-0.7, 0.5, 0.45));
  float diff1 = max(dot(N, L1), 0.0);
  float diff2 = max(dot(N, L2), 0.0);
  float hemi = 0.5 + 0.5 * N.z;
  vec3 H1 = normalize(L1 + V);
  float spec = pow(max(dot(N, H1), 0.0), 36.0) * 0.28;
  vec3 ambient = mix(vec3(0.18, 0.20, 0.24), vec3(0.36, 0.38, 0.42), hemi);
  vec3 lit = uColor.rgb * (ambient + 0.68 * diff1 + 0.30 * diff2) + vec3(spec);
  outColor = vec4(lit, uColor.a);
}`;

const LINE_VS = `#version 300 es
in vec3 aPos;
in vec3 aColor;
uniform mat4 uMVP;
out vec3 vColor;
void main() {
  vColor = aColor;
  gl_Position = uMVP * vec4(aPos, 1.0);
}`;

const LINE_FS = `#version 300 es
precision highp float;
in vec3 vColor;
out vec4 outColor;
void main() {
  outColor = vec4(vColor, 1.0);
}`;

function compile(type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(s));
  }
  return s;
}

function link(vs, fs) {
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl.VERTEX_SHADER, vs));
  gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(p));
  }
  return p;
}

const meshProg = link(MESH_VS, MESH_FS);
const lineProg = link(LINE_VS, LINE_FS);

// --- Minimal 4x4 matrix math (column-major) ---
function mat4Identity() {
  return new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]);
}
function mat4Mul(a, b) {
  const out = new Float32Array(16);
  for (let c = 0; c < 4; c++) {
    for (let r = 0; r < 4; r++) {
      out[c*4+r] =
        a[0*4+r]*b[c*4+0] + a[1*4+r]*b[c*4+1] +
        a[2*4+r]*b[c*4+2] + a[3*4+r]*b[c*4+3];
    }
  }
  return out;
}
function mat4Perspective(fovy, aspect, near, far) {
  const f = 1 / Math.tan(fovy / 2);
  const nf = 1 / (near - far);
  return new Float32Array([
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (far + near) * nf, -1,
    0, 0, 2 * far * near * nf, 0,
  ]);
}
function norm3(v) {
  const l = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0]/l, v[1]/l, v[2]/l];
}
function cross3(a, b) {
  return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
}
function dot3(a, b) { return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }

function mat4LookAt(eye, target, up) {
  const z = norm3([eye[0]-target[0], eye[1]-target[1], eye[2]-target[2]]);
  const x = norm3(cross3(up, z));
  const y = cross3(z, x);
  return new Float32Array([
    x[0], y[0], z[0], 0,
    x[1], y[1], z[1], 0,
    x[2], y[2], z[2], 0,
    -dot3(x, eye), -dot3(y, eye), -dot3(z, eye), 1,
  ]);
}

// --- Geometry buffers ---
function buildFlatMesh(part) {
  const pos = part.positions;
  const idx = part.indices;
  const triCount = idx.length / 3;
  const flatPos = new Float32Array(triCount * 9);
  const flatNorm = new Float32Array(triCount * 9);
  const wirePos = new Float32Array(triCount * 18);

  for (let t = 0; t < triCount; t++) {
    const i0 = idx[t * 3] * 3;
    const i1 = idx[t * 3 + 1] * 3;
    const i2 = idx[t * 3 + 2] * 3;
    const ax = pos[i0], ay = pos[i0+1], az = pos[i0+2];
    const bx = pos[i1], by = pos[i1+1], bz = pos[i1+2];
    const cx = pos[i2], cy = pos[i2+1], cz = pos[i2+2];

    const ux = bx - ax, uy = by - ay, uz = bz - az;
    const vx = cx - ax, vy = cy - ay, vz = cz - az;
    const n = norm3([uy*vz - uz*vy, uz*vx - ux*vz, ux*vy - uy*vx]);

    const pOff = t * 9;
    flatPos.set([ax, ay, az, bx, by, bz, cx, cy, cz], pOff);
    flatNorm.set([n[0], n[1], n[2], n[0], n[1], n[2], n[0], n[1], n[2]], pOff);

    const wOff = t * 18;
    wirePos.set([
      ax, ay, az, bx, by, bz,
      bx, by, bz, cx, cy, cz,
      cx, cy, cz, ax, ay, az,
    ], wOff);
  }

  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);

  const pBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, pBuf);
  gl.bufferData(gl.ARRAY_BUFFER, flatPos, gl.STATIC_DRAW);
  const aPos = gl.getAttribLocation(meshProg, "aPos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0);

  const nBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, nBuf);
  gl.bufferData(gl.ARRAY_BUFFER, flatNorm, gl.STATIC_DRAW);
  const aNorm = gl.getAttribLocation(meshProg, "aNorm");
  gl.enableVertexAttribArray(aNorm);
  gl.vertexAttribPointer(aNorm, 3, gl.FLOAT, false, 0, 0);

  const wVao = gl.createVertexArray();
  gl.bindVertexArray(wVao);
  const wBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, wBuf);
  gl.bufferData(gl.ARRAY_BUFFER, wirePos, gl.STATIC_DRAW);
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0);

  gl.bindVertexArray(null);
  return {
    label: part.label,
    color: part.color,
    visible: true,
    vao,
    vertCount: triCount * 3,
    wVao,
    wireCount: triCount * 6,
  };
}

function buildLineBuffer(posArr, colArr) {
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const pBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, pBuf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(posArr), gl.STATIC_DRAW);
  const aPos = gl.getAttribLocation(lineProg, "aPos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0);

  const cBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, cBuf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(colArr), gl.STATIC_DRAW);
  const aColor = gl.getAttribLocation(lineProg, "aColor");
  gl.enableVertexAttribArray(aColor);
  gl.vertexAttribPointer(aColor, 3, gl.FLOAT, false, 0, 0);
  gl.bindVertexArray(null);
  return { vao, count: posArr.length / 3 };
}

function buildGrid(extent) {
  const pitch = 2.54;
  const steps = Math.max(10, Math.ceil(extent / pitch) + 4);
  const limit = steps * pitch;
  const pos = [];
  const col = [];
  for (let i = -steps; i <= steps; i++) {
    const d = i * pitch;
    const major = i % 5 === 0;
    const c = major ? [0.30, 0.34, 0.42] : [0.20, 0.23, 0.29];
    pos.push(d, -limit, 0, d, limit, 0);
    col.push(...c, ...c);
    pos.push(-limit, d, 0, limit, d, 0);
    col.push(...c, ...c);
  }
  return buildLineBuffer(pos, col);
}

function buildAxes(len) {
  return buildLineBuffer(
    [0,0,0, len,0,0,  0,0,0, 0,len,0,  0,0,0, 0,0,len],
    [0.95,0.28,0.28, 0.95,0.28,0.28,
     0.28,0.88,0.38, 0.28,0.88,0.38,
     0.32,0.58,0.98, 0.32,0.58,0.98]
  );
}

// --- State ---
const state = {
  modelIndex: 0,
  meshes: [],
  grid: null,
  axes: null,
  showGrid: true,
  showAxes: true,
  wireframe: false,
  target: [0, 0, 0],
  yaw: Math.PI / 4,
  pitch: Math.PI / 5,
  dist: 30,
  radius: 10,
};

function fitCamera(view = "iso") {
  const m = MODELS[state.modelIndex];
  const mn = m.bbox.min, mx = m.bbox.max, sz = m.bbox.size;
  state.target = [(mn[0]+mx[0])/2, (mn[1]+mx[1])/2, (mn[2]+mx[2])/2];
  state.radius = Math.max(Math.hypot(sz[0], sz[1], sz[2]) * 0.5, 2);
  state.dist = state.radius * 2.8;
  if (view === "iso") { state.yaw = Math.PI / 4; state.pitch = 0.55; }
  else if (view === "top") { state.yaw = 0; state.pitch = Math.PI / 2 - 0.001; }
  else if (view === "bottom") { state.yaw = 0; state.pitch = -Math.PI / 2 + 0.001; }
  else if (view === "front") { state.yaw = -Math.PI / 2; state.pitch = 0; }
  else if (view === "right") { state.yaw = 0; state.pitch = 0; }
}

function selectModel(index) {
  state.modelIndex = index;
  const m = MODELS[index];
  state.meshes = m.parts.map(buildFlatMesh);
  const maxSpan = Math.max(
    Math.abs(m.bbox.min[0]), Math.abs(m.bbox.max[0]),
    Math.abs(m.bbox.min[1]), Math.abs(m.bbox.max[1]),
    10
  );
  state.grid = buildGrid(maxSpan);
  state.axes = buildAxes(Math.max(5, Math.min(maxSpan * 0.5, 15)));
  fitCamera("iso");

  document.getElementById("modelName").textContent = m.name;
  const mn = m.bbox.min, mx = m.bbox.max, sz = m.bbox.size;
  document.getElementById("dimTable").innerHTML = `
    <tr><td>X</td><td>${sz[0].toFixed(2)} mm</td><td>[${mn[0].toFixed(2)}, ${mx[0].toFixed(2)}]</td></tr>
    <tr><td>Y</td><td>${sz[1].toFixed(2)} mm</td><td>[${mn[1].toFixed(2)}, ${mx[1].toFixed(2)}]</td></tr>
    <tr><td>Z</td><td>${sz[2].toFixed(2)} mm</td><td>[${mn[2].toFixed(2)}, ${mx[2].toFixed(2)}]</td></tr>
  `;

  const partsList = document.getElementById("partsList");
  partsList.innerHTML = "";
  state.meshes.forEach((mesh) => {
    const row = document.createElement("label");
    row.className = "part-item";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = true;
    cb.onchange = () => { mesh.visible = cb.checked; render(); };
    const sw = document.createElement("span");
    sw.className = "swatch";
    sw.style.background = `rgb(${mesh.color.slice(0,3).map(v => Math.round(v*255)).join(",")})`;
    const txt = document.createElement("span");
    txt.textContent = mesh.label;
    row.append(cb, sw, txt);
    partsList.appendChild(row);
  });
  render();
}

// --- Controls ---
let dragMode = null;
let lastX = 0, lastY = 0;

canvas.addEventListener("contextmenu", (e) => e.preventDefault());
canvas.addEventListener("pointerdown", (e) => {
  canvas.setPointerCapture(e.pointerId);
  dragMode = (e.button === 2 || e.shiftKey) ? "pan" : "orbit";
  lastX = e.clientX;
  lastY = e.clientY;
});
canvas.addEventListener("pointerup", () => { dragMode = null; });
canvas.addEventListener("pointermove", (e) => {
  if (!dragMode) return;
  const dx = e.clientX - lastX;
  const dy = e.clientY - lastY;
  lastX = e.clientX;
  lastY = e.clientY;
  if (dragMode === "orbit") {
    state.yaw -= dx * 0.008;
    state.pitch = Math.max(-Math.PI/2 + 0.001, Math.min(Math.PI/2 - 0.001, state.pitch + dy * 0.008));
  } else {
    const scale = state.dist * 0.0016;
    const right = [-Math.sin(state.yaw), Math.cos(state.yaw), 0];
    const up = [
      -Math.sin(state.pitch) * Math.cos(state.yaw),
      -Math.sin(state.pitch) * Math.sin(state.yaw),
      Math.cos(state.pitch),
    ];
    for (let i = 0; i < 3; i++) {
      state.target[i] += (-dx * right[i] + dy * up[i]) * scale;
    }
  }
  render();
});
canvas.addEventListener("wheel", (e) => {
  e.preventDefault();
  state.dist = Math.max(1.5, Math.min(state.radius * 25, state.dist * Math.exp(e.deltaY * 0.0012)));
  render();
}, { passive: false });

document.querySelectorAll("button[data-view]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const v = btn.dataset.view;
    fitCamera(v === "fit" ? undefined : v);
    render();
  });
});

document.getElementById("toggleGrid").onclick = (e) => {
  state.showGrid = !state.showGrid;
  e.target.classList.toggle("active", state.showGrid);
  render();
};
document.getElementById("toggleAxes").onclick = (e) => {
  state.showAxes = !state.showAxes;
  e.target.classList.toggle("active", state.showAxes);
  render();
};
document.getElementById("toggleWire").onclick = (e) => {
  state.wireframe = !state.wireframe;
  e.target.classList.toggle("active", state.wireframe);
  render();
};

if (MODELS.length > 1) {
  const sel = document.getElementById("modelSelect");
  sel.style.display = "block";
  MODELS.forEach((m, i) => {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = m.name;
    sel.appendChild(opt);
  });
  sel.onchange = () => selectModel(Number(sel.value));
}

function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.floor(canvas.clientWidth * dpr);
  const h = Math.floor(canvas.clientHeight * dpr);
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
}

function render() {
  resize();
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.clearColor(0.08, 0.09, 0.11, 1.0);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST);

  const eye = [
    state.target[0] + state.dist * Math.cos(state.pitch) * Math.cos(state.yaw),
    state.target[1] + state.dist * Math.cos(state.pitch) * Math.sin(state.yaw),
    state.target[2] + state.dist * Math.sin(state.pitch),
  ];
  const proj = mat4Perspective(
    Math.PI / 4,
    canvas.width / Math.max(1, canvas.height),
    Math.max(0.05, state.dist * 0.005),
    state.dist * 20
  );
  const view = mat4LookAt(eye, state.target, [0, 0, 1]);
  const mvp = mat4Mul(proj, view);
  const model = mat4Identity();

  // Grid & Axes
  gl.useProgram(lineProg);
  gl.uniformMatrix4fv(gl.getUniformLocation(lineProg, "uMVP"), false, mvp);
  if (state.showGrid && state.grid) {
    gl.bindVertexArray(state.grid.vao);
    gl.drawArrays(gl.LINES, 0, state.grid.count);
  }
  if (state.showAxes && state.axes) {
    gl.bindVertexArray(state.axes.vao);
    gl.drawArrays(gl.LINES, 0, state.axes.count);
  }

  // Meshes
  gl.useProgram(meshProg);
  gl.uniformMatrix4fv(gl.getUniformLocation(meshProg, "uMVP"), false, mvp);
  gl.uniformMatrix4fv(gl.getUniformLocation(meshProg, "uModel"), false, model);
  gl.uniform3fv(gl.getUniformLocation(meshProg, "uCamPos"), new Float32Array(eye));
  const uColor = gl.getUniformLocation(meshProg, "uColor");
  const uWire = gl.getUniformLocation(meshProg, "uWire");

  for (const mesh of state.meshes) {
    if (!mesh.visible) continue;
    gl.uniform4fv(uColor, new Float32Array(mesh.color));
    gl.uniform1i(uWire, 0);
    gl.bindVertexArray(mesh.vao);
    gl.drawArrays(gl.TRIANGLES, 0, mesh.vertCount);
    if (state.wireframe) {
      gl.uniform1i(uWire, 1);
      gl.bindVertexArray(mesh.wVao);
      gl.drawArrays(gl.LINES, 0, mesh.wireCount);
    }
  }
  gl.bindVertexArray(null);
}

window.addEventListener("resize", render);
selectModel(0);
</script>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Open one or more .step/.stp files in an interactive 3D viewer."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="STEP file(s) or directory to view (default: ./stepModels).",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.05,
        help="Tessellation tolerance in mm (default: 0.05).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Save the generated standalone HTML viewer to this path.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Generate the HTML viewer without opening a web browser.",
    )
    args = parser.parse_args(argv)

    try:
        html_path = view_step_files(
            paths=args.paths,
            tolerance=args.tolerance,
            output_html=args.output,
            open_browser=not args.no_browser,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Viewer generated: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
