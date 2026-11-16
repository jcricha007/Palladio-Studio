// Local visual lighting model, not geolocated solar analysis.
export const QUALITY = Object.freeze({
  draft: {pixelRatio:1, shadowSize:0, samples:0},
  studio: {pixelRatio:1.5, shadowSize:1024, samples:1},
  presentation: {pixelRatio:2, shadowSize:2048, samples:2},
});

export function lighting(environment) {
  const hour = Number.isFinite(environment.hour) ? environment.hour : 16;
  const angle = (hour - 6) * Math.PI / 12;
  const daylight = Math.max(0, Math.sin(angle));
  const clear = environment.weather === 'clear';
  const warm = Math.pow(1 - daylight, 3);
  const direction = [Math.cos(angle), Math.sin(angle), .32];
  const length = Math.hypot(...direction);
  return {
    direction:direction.map(v=>v/length),
    color:[1, .98 - .28 * warm, .93 - .43 * warm],
    direct:daylight * (clear ? 3.1 : .65),
    ambient:.035 + daylight * (clear ? .52 : .72),
    sky:[.32,.48,.65].map(v=>v*(.06+.94*daylight)),
    haze:({clear:.002,overcast:.008,fog:.035,rain:.018})[environment.weather] ?? .002,
  };
}

export function materialResponse(material) {
  return ({steel:[.3,.8],glass:[.12,0],water:[.16,0],oak:[.65,0],
    timber:[.7,0],concrete:[.94,0],stone:[.87,0],plaster:[.92,0]})[material] || [.78,0];
}

export const surfaceVertex = `
attribute vec3 point, color, normal;
attribute vec2 material;
uniform vec3 eye, right, up, forward;
uniform vec2 spread;
varying vec3 surface, worldPoint, surfaceNormal;
varying vec2 response;
varying float viewDepth;
void main() {
  vec3 relative = point - eye;
  float depth = dot(relative, forward);
  viewDepth = depth;
  surface = color; worldPoint = point; surfaceNormal = normal; response = material;
  gl_Position = vec4(dot(relative, right) / spread.x, dot(relative, up) / spread.y,
                     1.000016 * depth - 0.160001, depth);
}`;

export const surfaceFragment = `
precision highp float;
uniform vec3 eye, sky, sunDirection, sunColor;
uniform float directLight, ambientLight, haze, shadowEnabled, shadowStep, shadowSamples;
uniform sampler2D shadowMap;
uniform vec3 shadowCenter, shadowRight, shadowUp, shadowForward;
uniform float shadowExtent, shadowDepth;
varying vec3 surface, worldPoint, surfaceNormal;
varying vec2 response;
varying float viewDepth;
float visibility(vec3 n) {
  if (shadowEnabled < .5) return 1.0;
  vec3 p = worldPoint - shadowCenter;
  vec2 uv = vec2(dot(p,shadowRight),dot(p,shadowUp)) / (2.0*shadowExtent) + .5;
  float depth = dot(p,shadowForward) / (2.0*shadowDepth) + .5;
  if (uv.x<.002 || uv.y<.002 || uv.x>.998 || uv.y>.998 || depth<0.0 || depth>1.0) return 1.0;
  float bias = max(.00018, .00075*(1.0-max(dot(n,sunDirection),0.0)));
  float sum = 0.0; float count = 0.0;
  for (int y=-2; y<=2; y++) for (int x=-2; x<=2; x++) {
    if (abs(float(x)) <= shadowSamples && abs(float(y)) <= shadowSamples) {
      vec2 depthChannels = texture2D(shadowMap,uv+vec2(float(x),float(y))*shadowStep).rg;
      float stored = depthChannels.x + depthChannels.y/255.0;
      sum += depth-bias <= stored ? 1.0 : 0.0; count += 1.0;
    }
  }
  return sum/max(count,1.0);
}
vec3 tonemap(vec3 x) {
  return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.0,1.0);
}
void main() {
  vec3 n = normalize(surfaceNormal);
  vec3 v = normalize(eye-worldPoint);
  if (!gl_FrontFacing) n = -n;
  vec3 h = normalize(v+sunDirection);
  float nl = max(dot(n,sunDirection),0.0), nv = max(dot(n,v),.001);
  float rough = max(response.x,.08), metal = response.y;
  vec3 base = pow(max(surface,vec3(0.0)),vec3(2.2));
  vec3 f0 = mix(vec3(.04),base,metal);
  vec3 fresnel = f0+(1.0-f0)*pow(1.0-max(dot(h,v),0.0),5.0);
  float a2 = pow(rough,4.0), nh=max(dot(n,h),0.0);
  float denom=nh*nh*(a2-1.0)+1.0;
  float distribution=a2/(3.14159*denom*denom+.00001);
  float k=pow(rough+1.0,2.0)/8.0;
  float geometry=(nv/(nv*(1.0-k)+k))*(nl/(nl*(1.0-k)+k));
  vec3 specular=distribution*geometry*fresnel/(4.0*nv*nl+.001);
  vec3 diffuse=(1.0-fresnel)*(1.0-metal)*base/3.14159;
  float hemi=.38+.62*(n.y*.5+.5);
  vec3 ambient=base*ambientLight*hemi + f0*ambientLight*.15;
  vec3 lit=ambient+(diffuse+specular)*sunColor*directLight*nl*visibility(n);
  float fog=1.0-exp(-max(viewDepth-9.0,0.0)*haze);
  vec3 display=pow(tonemap(lit),vec3(1.0/2.2));
  gl_FragColor=vec4(mix(display,sky,min(fog,.97)),1.0);
}`;

export const shadowVertex = `
attribute vec3 point;
uniform vec3 shadowCenter, shadowRight, shadowUp, shadowForward;
uniform float shadowExtent, shadowDepth;
void main() {
  vec3 p=point-shadowCenter;
  gl_Position=vec4(dot(p,shadowRight)/shadowExtent,dot(p,shadowUp)/shadowExtent,
    dot(p,shadowForward)/shadowDepth,1.0);
}`;
export const shadowFragment = `
precision highp float;
void main() {
  float depth=min(gl_FragCoord.z,.99999);
  vec2 depthChannels=fract(depth*vec2(1.0,255.0));
  depthChannels.x-=depthChannels.y/255.0;
  gl_FragColor=vec4(depthChannels,0.0,1.0);
}`;
export const skyVertex = `
attribute vec2 point;
varying vec2 coord;
void main() { coord=point; gl_Position=vec4(point,1.0,1.0); }
`;
export const skyFragment = `
precision highp float;
varying vec2 coord;
uniform vec3 right, up, forward, sky, sunDirection, sunColor;
uniform vec2 spread;
uniform float directLight;
void main() {
  vec3 ray=normalize(forward+right*coord.x*spread.x+up*coord.y*spread.y);
  float horizon=pow(1.0-max(ray.y,0.0),4.0);
  vec3 color=mix(sky,sky*.72+vec3(.12,.10,.075),horizon*.6);
  float disk=smoothstep(.9997,.99996,dot(ray,sunDirection));
  color+=sunColor*disk*min(directLight,.8);
  gl_FragColor=vec4(color,1.0);
}`;
