import {surfaceTriangles} from "./mesh.js";
// WebGL adapter for the local-metre scene. Persistence and commands live in Python.
const add = (a, b) => a.map((value, i) => value + b[i]);
const sub = (a, b) => a.map((value, i) => value - b[i]);
const scale = (v, n) => v.map(value => value * n);
const dot = (a, b) => a.reduce((sum, value, i) => sum + value * b[i], 0);
const cross = ([x, y, z], [u, v, w]) => [y * w - z * v, z * u - x * w, x * v - y * u];
const normalize = v => scale(v, 1 / (Math.hypot(...v) || 1));
const tint = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255);
const rotate = ([x, y, z], angle) => [
  x * Math.cos(angle) + z * Math.sin(angle), y, -x * Math.sin(angle) + z * Math.cos(angle),
];
const sun = normalize([-.4, .9, .6]);
const fieldOfView = Math.tan(Math.PI / 8);

const vertex = `
  attribute vec3 point;
  attribute vec3 color;
  uniform vec3 eye, right, up, forward;
  uniform vec2 spread;
  varying mediump vec3 surface;
  varying mediump float viewDepth;
  void main() {
    vec3 relative = point - eye;
    float depth = dot(relative, forward);
    viewDepth = depth;
    surface = color;
    gl_Position = vec4(dot(relative, right) / spread.x, dot(relative, up) / spread.y,
                       1.000016 * depth - 0.160001, depth);
  }
`;
const fragment = `
  precision mediump float;
  uniform vec3 sky;
  uniform float light, haze;
  varying mediump vec3 surface;
  varying mediump float viewDepth;
  void main() {
    float fog = 1.0 - exp(-max(viewDepth - 9.0, 0.0) * haze);
    gl_FragColor = vec4(mix(surface * light, sky, min(fog, 0.97)), 1.0);
  }
`;

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader));
  }
  return shader;
}

function triangle(vertices, a, b, c, color) {
  const normal = normalize(cross(sub(b, a), sub(c, a)));
  const shade = .65 + .35 * Math.max(0, dot(normal, sun));
  for (const point of [a, b, c]) vertices.push(...point, ...scale(color, shade));
}

function quad(vertices, a, b, c, d, color) {
  triangle(vertices, a, b, c, color);
  triangle(vertices, a, c, d, color);
}

function box(vertices, {size: [width, height, depth], position, yaw}, color) {
  const angle = yaw * Math.PI / 180;
  const w = width / 2;
  const d = depth / 2;
  const corners = [
    [-w, 0, -d], [w, 0, -d], [w, 0, d], [-w, 0, d],
    [-w, height, -d], [w, height, -d], [w, height, d], [-w, height, d],
  ].map(point => add(position, rotate(point, angle)));
  for (const [a, b, c, d] of [
    [0, 1, 2, 3], [4, 7, 6, 5], [0, 4, 5, 1],
    [1, 5, 6, 2], [2, 6, 7, 3], [3, 7, 4, 0],
  ]) quad(vertices, corners[a], corners[b], corners[c], corners[d], color);
}

function groundHeight(terrain, x, z) {
  const {size,spacing,heights:h}=terrain, edge=(size-1)*spacing/2;
  let u=(x+edge)/spacing, v=(z+edge)/spacing;
  const col=Math.max(0,Math.min(size-2,Math.floor(u))),row=Math.max(0,Math.min(size-2,Math.floor(v)));
  u=Math.max(0,Math.min(1,u-col));v=Math.max(0,Math.min(1,v-row));
  const a=h[row*size+col],b=h[(row+1)*size+col],c=h[(row+1)*size+col+1],d=h[row*size+col+1];
  return v>=u?a+(c-b)*u+(b-a)*v:a+(d-a)*u+(c-d)*v;
}

function scenery(baseline) {
  const vertices = [];
  const {size, spacing, heights} = baseline.terrain;
  const edge = (size - 1) * spacing / 2;
  const at = (x, z) => [x * spacing - edge, heights[z * size + x], z * spacing - edge];
  const coastal = baseline.source.profile === "coastal bluff";
  for (let z = 0; z < size - 1; z++) {
    for (let x = 0; x < size - 1; x++) {
      const variation = 1 + .055 * Math.sin(x * 8.7 + z * 5.1);
      const color = coastal && z > size * .72 ? [.54, .49, .38] : [.42, .49, .30];
      quad(vertices, at(x, z), at(x, z + 1), at(x + 1, z + 1), at(x + 1, z), scale(color, variation));
    }
  }
  if (coastal) {
    quad(vertices, [-170, -8, 19], [-170, -8, 180], [170, -8, 180], [170, -8, 19], [.24, .43, .48]);
  }
  for (const {position, height} of baseline.vegetation) {
    box(vertices, {position, size: [.22, height * .55, .22], yaw: 0}, [.36, .26, .17]);
    for (const layer of [.27, .45, .62]) {
      const radius = height * (.26 - layer * .2);
      const ring = Array.from({length: 7}, (_, i) => {
        const angle = i * 2 * Math.PI / 7;
        return add(position, [Math.cos(angle) * radius, height * layer, Math.sin(angle) * radius]);
      });
      const tip = add(position, [0, height * Math.min(1, layer + .43), 0]);
      for (let i = 0; i < ring.length; i++) {
        triangle(vertices, ring[i], tip, ring[(i + 1) % ring.length], [.24, .37 + layer * .07, .23]);
      }
    }
  }
  return vertices;
}

function intersection(eye, direction, item) {
  const angle = -item.yaw * Math.PI / 180;
  const origin = rotate(sub(eye, item.position), angle);
  const ray = rotate(direction, angle);
  const [width, height, depth] = item.size;
  const low = [-width / 2, 0, -depth / 2];
  const high = [width / 2, height, depth / 2];
  let near = 0;
  let far = Infinity;
  for (let i = 0; i < 3; i++) {
    if (Math.abs(ray[i]) < 1e-7) {
      if (origin[i] < low[i] || origin[i] > high[i]) return Infinity;
      continue;
    }
    const a = (low[i] - origin[i]) / ray[i];
    const b = (high[i] - origin[i]) / ray[i];
    near = Math.max(near, Math.min(a, b));
    far = Math.min(far, Math.max(a, b));
    if (far < near) return Infinity;
  }
  return near;
}

export class Viewport {
  constructor(canvas, onSelect) {
    this.canvas = canvas;
    const gl = canvas.getContext("webgl", {antialias: true, alpha: false});
    if (!gl) throw new Error("WebGL is unavailable. Property controls remain usable.");
    this.gl = gl;
    this.program = gl.createProgram();
    gl.attachShader(this.program, compile(gl, gl.VERTEX_SHADER, vertex));
    gl.attachShader(this.program, compile(gl, gl.FRAGMENT_SHADER, fragment));
    gl.linkProgram(this.program);
    if (!gl.getProgramParameter(this.program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(this.program));
    }
    gl.useProgram(this.program);
    this.uniforms = Object.fromEntries(
      ["eye", "right", "up", "forward", "spread", "sky", "light", "haze"].map(
        name => [name, gl.getUniformLocation(this.program, name)],
      ),
    );
    this.buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    for (const [name, offset] of [["point", 0], ["color", 12]]) {
      const location = gl.getAttribLocation(this.program, name);
      gl.enableVertexAttribArray(location);
      gl.vertexAttribPointer(location, 3, gl.FLOAT, false, 24, offset);
    }
    gl.enable(gl.DEPTH_TEST);
    this.camera = {target: [0, 1, 0], azimuth: .68, pitch: .43, distance: 33};
    this.reset();
    this.items = [];
    this.environment = {weather: "clear", hour: 16};
    new ResizeObserver(() => this.draw()).observe(canvas);

    let pointer;
    canvas.addEventListener("pointerdown", event => {
      if (event.button !== 0 || pointer) return;
      canvas.setPointerCapture(event.pointerId);
      pointer = {id: event.pointerId, x: event.clientX, y: event.clientY, travelled: 0};
    });
    canvas.addEventListener("pointermove", event => {
      if (event.pointerId !== pointer?.id) return;
      const dx = event.clientX - pointer.x;
      const dy = event.clientY - pointer.y;
      pointer.travelled += Math.hypot(dx, dy);
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      if (event.shiftKey) {
        const {right, up} = this.basis();
        const factor = this.camera.distance * .0015;
        this.camera.target = add(this.camera.target, add(scale(right, -dx * factor), scale(up, dy * factor)));
      } else {
        this.camera.azimuth -= dx * .007;
        this.camera.pitch = Math.max(.06, Math.min(1.51, this.camera.pitch + dy * .007));
      }
      this.draw();
    });
    canvas.addEventListener("pointerup", event => {
      if (event.pointerId !== pointer?.id) return;
      if (pointer.travelled < 4) onSelect(this.pick(event.clientX, event.clientY));
      pointer = null;
    });
    canvas.addEventListener("lostpointercapture", () => { pointer = null; });
    canvas.addEventListener("wheel", event => {
      event.preventDefault();
      const factor = event.deltaMode === 0 ? .001 : .025;
      this.camera.distance = Math.max(2, Math.min(this.maxDistance || 170, this.camera.distance * Math.exp(event.deltaY * factor)));
      this.draw();
    }, {passive: false});
  }

  reset() {
    Object.assign(this.camera, this.defaultCamera || {target: [0, 1, 0], azimuth: .68, pitch: .43, distance: 33});
    this.draw();
  }

  basis() {
    const {target, azimuth, pitch, distance} = this.camera;
    const eye = add(target, scale([
      Math.sin(azimuth) * Math.cos(pitch), Math.sin(pitch), Math.cos(azimuth) * Math.cos(pitch),
    ], distance));
    const forward = normalize(sub(target, eye));
    const right = normalize(cross(forward, [0, 1, 0]));
    return {eye, right, up: cross(right, forward), forward};
  }

  pick(x, y) {
    const rect = this.canvas.getBoundingClientRect();
    const {eye, right, up, forward} = this.basis();
    const u = (2 * (x - rect.left) / rect.width - 1) * fieldOfView * rect.width / rect.height;
    const v = (1 - 2 * (y - rect.top) / rect.height) * fieldOfView;
    const ray = add(forward, add(scale(right, u), scale(up, v)));
    let closest = Infinity;
    let selection = null;
    for (const item of this.items) {
      const distance = intersection(eye, ray, item);
      if (distance < closest) {
        closest = distance;
        selection = item.id;
      }
    }
    return selection;
  }

  update(project, baselineView, materials, selected) {
    const landscape = !baselineView && project.scene.terrain ? {...project.baseline, terrain:project.scene.terrain,
      vegetation:project.baseline.vegetation.map(tree=>({...tree,position:[tree.position[0],groundHeight(project.scene.terrain,tree.position[0],tree.position[2]),tree.position[2]]}))} : project.baseline;
    const terrainKey=JSON.stringify([project.id,landscape.terrain]);
    if (terrainKey !== this.terrainKey) {
      this.terrain = scenery(landscape);
      this.terrainKey = terrainKey;
    }
    if (project.id !== this.projectId) {
      this.projectId = project.id;
      const {size, spacing, heights} = project.baseline.terrain;
      this.imported = project.baseline.source.kind === "elevation grid";
      this.defaultCamera = {target: [0, 1, 0], azimuth: .68, pitch: .43, distance: 33};
      if (this.imported) {
        const low = Math.min(...heights), high = Math.max(...heights);
        const span = (size - 1) * spacing;
        this.defaultCamera = {target: [0, (low + high) / 2, 0], azimuth: .68, pitch: .7,
          distance: Math.max(33, Math.hypot(span, span, high - low) * 1.5)};
      }
      this.maxDistance = Math.max(170, this.defaultCamera.distance * 3);
      this.reset();
    }
    this.items = baselineView ? [] : project.scene.elements;
    this.environment = (baselineView ? project.baseline : project.scene).environment;
    const vertices = this.terrain.slice();
    for (const item of this.items) {
      const chosen = item.id === selected;
      const color = tint(item.finish?.color || materials[item.material]);
      if (item.mesh || item.finish?.pattern === 'wood') {
        for (const surface of surfaceTriangles(item, materials[item.material])) {
          const points=surface.points.map(p=>add(item.position,rotate(p,item.yaw*Math.PI/180)));
          triangle(vertices,...points,chosen?add(scale(surface.color,.72),[.28,.25,.15]):surface.color);
        }
      } else box(vertices, item, chosen ? add(scale(color, .72), [.28, .25, .15]) : color);
    }
    this.gl.bufferData(this.gl.ARRAY_BUFFER, new Float32Array(vertices), this.gl.STATIC_DRAW);
    this.count = vertices.length / 6;
    this.draw();
  }

  draw() {
    if (!this.count) return;
    const {canvas, gl, uniforms} = this;
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const width = Math.max(1, Math.round(canvas.clientWidth * ratio));
    const height = Math.max(1, Math.round(canvas.clientHeight * ratio));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    gl.viewport(0, 0, width, height);
    const {weather, hour} = this.environment;
    const daylight = Math.max(.22, Math.sin((hour - 5) * Math.PI / 14));
    const sky = scale(weather === "clear" ? [.69, .77, .77] : [.63, .68, .66], .4 + .6 * daylight);
    gl.clearColor(...sky, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    for (const [name, value] of Object.entries(this.basis())) gl.uniform3fv(uniforms[name], value);
    gl.uniform2f(uniforms.spread, fieldOfView * width / height, fieldOfView);
    gl.uniform3fv(uniforms.sky, sky);
    gl.uniform1f(uniforms.haze, {clear: this.imported ? .0006 : .004, overcast: .012, fog: .05, rain: .027}[weather]);
    gl.uniform1f(uniforms.light, daylight * (weather === "clear" ? 1 : .85));
    gl.drawArrays(gl.TRIANGLES, 0, this.count);
  }
}
