import {surfaceTriangles} from "./mesh.js";
import {QUALITY, lighting, materialResponse, surfaceVertex, surfaceFragment, shadowVertex, shadowFragment, skyVertex, skyFragment} from "./lighting.js";
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
function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader));
  }
  return shader;
}

function triangle(vertices, a, b, c, color, response = [.9,0]) {
  const normal = normalize(cross(sub(b, a), sub(c, a)));
  for (const point of [a, b, c]) vertices.push(...point, ...color, ...normal, ...response);
}

function quad(vertices, a, b, c, d, color, response) {
  triangle(vertices, a, b, c, color, response);
  triangle(vertices, a, c, d, color, response);
}

function box(vertices, {size: [width, height, depth], position, yaw}, color, response) {
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
  ]) quad(vertices, corners[a], corners[b], corners[c], corners[d], color, response);
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
    const program = (vs, fs) => {
      const result=gl.createProgram();
      for (const [type,source] of [[gl.VERTEX_SHADER,vs],[gl.FRAGMENT_SHADER,fs]]) {
        const shader=compile(gl,type,source);gl.attachShader(result,shader);gl.deleteShader(shader);
      }
      gl.linkProgram(result);
      if (!gl.getProgramParameter(result,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(result));
      return result;
    };
    this.program=program(surfaceVertex,surfaceFragment);
    this.shadowProgram=program(shadowVertex,shadowFragment);
    this.skyProgram=program(skyVertex,skyFragment);
    this.buffer=gl.createBuffer();
    this.skyBuffer=gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER,this.skyBuffer);
    gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,3,-1,-1,3]),gl.STATIC_DRAW);
    this.quality='studio';
    this.uniforms=new Map();
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

  captureCamera() {return {...this.camera,target:[...this.camera.target]};}

  projectionScale() {return Math.tan((this.camera.fov_degrees ?? 45)*Math.PI/360);}

  setFieldOfView(value) {
    if(!Number.isFinite(value)||value<15||value>100)throw new Error('Choose a vertical field of view from 15 to 100 degrees.');
    this.camera.fov_degrees=value;this.draw();
  }

  applyCamera(camera) {
    this.camera={...camera,target:[...camera.target]};
    this.maxDistance=Math.max(this.maxDistance||170,camera.distance);this.draw();
  }

  capturePng() {
    this.draw();
    return new Promise((resolve,reject)=>this.canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('The viewport image could not be captured.')),'image/png'));
  }

  reset() {
    this.applyCamera(this.defaultCamera || {target: [0, 1, 0], azimuth: .68, pitch: .43, distance: 33});
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
    const fieldOfView = this.projectionScale();
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
      if (item.mesh || item.finish && item.finish.pattern !== 'solid') {
        for (const surface of surfaceTriangles(item, materials[item.material])) {
          const points=surface.points.map(p=>add(item.position,rotate(p,item.yaw*Math.PI/180)));
          triangle(vertices,...points,chosen?add(scale(surface.color,.72),[.28,.25,.15]):surface.color,materialResponse(item.material));
        }
      } else box(vertices, item, chosen ? add(scale(color, .72), [.28, .25, .15]) : color,materialResponse(item.material));
    }
    this.gl.bindBuffer(this.gl.ARRAY_BUFFER,this.buffer);
    this.gl.bufferData(this.gl.ARRAY_BUFFER, new Float32Array(vertices), this.gl.STATIC_DRAW);
    this.count = vertices.length / 11;
    this.bounds = [[Infinity,Infinity,Infinity],[-Infinity,-Infinity,-Infinity]];
    for(let i=0;i<vertices.length;i+=11) for(let axis=0;axis<3;axis++) {
      this.bounds[0][axis]=Math.min(this.bounds[0][axis],vertices[i+axis]);
      this.bounds[1][axis]=Math.max(this.bounds[1][axis],vertices[i+axis]);
    }
    this.shadowKey='';
    this.draw();
  }

  setQuality(value) {
    if (!Object.hasOwn(QUALITY,value)) throw new Error('Choose Draft, Studio or Presentation.');
    this.quality=value; this.shadowKey=''; this.draw();
  }

  qualityDescription() {
    if (this.shadowFailed) return 'Material lighting · shadows unavailable on this device';
    return {draft:'Fast material preview · shadows off',studio:'Sunlight · soft shadows · material lighting',
      presentation:'High resolution · fine shadows · material lighting'}[this.quality];
  }

  uniform(program,name,value) {
    const gl=this.gl;
    if(!this.uniforms.has(program))this.uniforms.set(program,new Map());
    const cache=this.uniforms.get(program);
    if(!cache.has(name))cache.set(name,gl.getUniformLocation(program,name));
    const location=cache.get(name);
    if(Array.isArray(value)) {
      if(value.length===2)gl.uniform2fv(location,value);else gl.uniform3fv(location,value);
    } else gl.uniform1f(location,value);
  }

  use(program,sky=false) {
    const gl=this.gl;gl.useProgram(program);
    // Attribute locations differ between linked programs; disable old bindings.
    for(let i=0;i<4;i++)gl.disableVertexAttribArray(i);
    gl.bindBuffer(gl.ARRAY_BUFFER,sky?this.skyBuffer:this.buffer);
    for(const [name,size,offset] of sky?[['point',2,0]]:[['point',3,0],['color',3,12],['normal',3,24],['material',2,36]]) {
      const location=gl.getAttribLocation(program,name);
      if(location<0)continue;
      gl.enableVertexAttribArray(location);
      gl.vertexAttribPointer(location,size,gl.FLOAT,false,sky?8:44,offset);
    }
  }

  ensureShadow(size) {
    const gl=this.gl;
    size=Math.min(size,gl.getParameter(gl.MAX_TEXTURE_SIZE),gl.getParameter(gl.MAX_RENDERBUFFER_SIZE));
    if(size && this.failedShadowSize===size)return false;
    if(this.shadow?.size===size)return true;
    if(this.shadow) {
      gl.deleteTexture(this.shadow.texture);gl.deleteRenderbuffer(this.shadow.depth);gl.deleteFramebuffer(this.shadow.framebuffer);
      this.shadow=null;
    }
    if(!size)return false;
    const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,size,size,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
    for(const param of [gl.TEXTURE_MIN_FILTER,gl.TEXTURE_MAG_FILTER])gl.texParameteri(gl.TEXTURE_2D,param,gl.NEAREST);
    for(const param of [gl.TEXTURE_WRAP_S,gl.TEXTURE_WRAP_T])gl.texParameteri(gl.TEXTURE_2D,param,gl.CLAMP_TO_EDGE);
    const depth=gl.createRenderbuffer();gl.bindRenderbuffer(gl.RENDERBUFFER,depth);
    gl.renderbufferStorage(gl.RENDERBUFFER,gl.DEPTH_COMPONENT16,size,size);
    const framebuffer=gl.createFramebuffer();gl.bindFramebuffer(gl.FRAMEBUFFER,framebuffer);
    gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,texture,0);
    gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,depth);
    const complete=gl.checkFramebufferStatus(gl.FRAMEBUFFER)===gl.FRAMEBUFFER_COMPLETE;
    gl.bindFramebuffer(gl.FRAMEBUFFER,null);
    if(!complete) {
      gl.deleteTexture(texture);gl.deleteRenderbuffer(depth);gl.deleteFramebuffer(framebuffer);
      this.shadowFailed=true;this.failedShadowSize=size;return false;
    }
    this.shadow={size,texture,depth,framebuffer};this.shadowKey='';this.shadowFailed=false;this.failedShadowSize=0;return true;
  }

  draw() {
    if (!this.count || this.gl.isContextLost()) return;
    const {canvas,gl}=this;
    const quality=QUALITY[this.quality];
    const ratio=Math.min(quality.pixelRatio,window.devicePixelRatio||1);
    const width=Math.max(1,Math.round(canvas.clientWidth*ratio));
    const height=Math.max(1,Math.round(canvas.clientHeight*ratio));
    if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}
    const light=lighting(this.environment),basis=this.basis();
    const spread=[this.projectionScale()*width/height,this.projectionScale()];
    const shadowForward=scale(light.direction,-1);
    const shadowRight=normalize(cross(shadowForward,[0,1,0]));
    const shadowUp=cross(shadowRight,shadowForward);
    const shadowCenter=this.camera.target;
    const shadowExtent=Math.max(20,Math.min(220,this.camera.distance*1.2));
    const shadowDepth=Math.max(100,...this.bounds.map(p=>Math.hypot(...sub(p,shadowCenter))))+20;
    const shadowUniforms={shadowForward,shadowRight,shadowUp,shadowCenter,shadowExtent,shadowDepth};
    const hasShadow=this.ensureShadow(quality.shadowSize)&&light.direct>.001;
    if(hasShadow) {
      const key=JSON.stringify([shadowCenter,shadowExtent,this.environment,this.quality]);
      if(key!==this.shadowKey) {
        gl.bindFramebuffer(gl.FRAMEBUFFER,this.shadow.framebuffer);
        gl.viewport(0,0,this.shadow.size,this.shadow.size);
        gl.enable(gl.DEPTH_TEST);gl.disable(gl.BLEND);gl.disable(gl.DITHER);
        gl.clearColor(1,1,1,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
        this.use(this.shadowProgram);
        for(const [name,value] of Object.entries(shadowUniforms))this.uniform(this.shadowProgram,name,value);
        gl.drawArrays(gl.TRIANGLES,0,this.count);
        this.shadowKey=key;
      }
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.viewport(0,0,width,height);
    gl.clearColor(...light.sky,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    gl.disable(gl.DEPTH_TEST);gl.enable(gl.DITHER);
    this.use(this.skyProgram,true);
    for(const [name,value] of Object.entries({...basis,spread,sky:light.sky,sunDirection:light.direction,sunColor:light.color,directLight:light.direct}))this.uniform(this.skyProgram,name,value);
    gl.drawArrays(gl.TRIANGLES,0,3);
    gl.enable(gl.DEPTH_TEST);this.use(this.program);
    const uniforms={...basis,spread,...shadowUniforms,sky:light.sky,sunDirection:light.direction,sunColor:light.color,
      directLight:light.direct,ambientLight:light.ambient,haze:this.imported?light.haze*.35:light.haze,
      shadowEnabled:hasShadow?1:0,shadowStep:hasShadow?1/this.shadow.size:1,shadowSamples:quality.samples};
    for(const [name,value] of Object.entries(uniforms))this.uniform(this.program,name,value);
    // WebGL requires a complete sampler even when the no-shadow branch is used.
    if(!this.fallbackTexture) {
      this.fallbackTexture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,this.fallbackTexture);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,1,1,0,gl.RGBA,gl.UNSIGNED_BYTE,new Uint8Array([255,255,255,255]));
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);
    }
    gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,hasShadow?this.shadow.texture:this.fallbackTexture);
    gl.uniform1i(gl.getUniformLocation(this.program,'shadowMap'),0);
    gl.drawArrays(gl.TRIANGLES,0,this.count);
  }
}
