const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const ctx=vm.createContext({});
vm.runInContext(fs.readFileSync('palladio/web/lighting.js','utf8').replace(/export /g,''),ctx);
const light=(hour,weather='clear')=>vm.runInContext(`lighting({hour:${hour},weather:${JSON.stringify(weather)}})`,ctx);
const morning=light(8),noon=light(12),evening=light(16),night=light(0);
assert(morning.direction[0]>0&&evening.direction[0]<0,'Sun must cross the site rather than remain fixed');
assert(noon.direct>morning.direct&&night.direct===0,'No direct solar light at night');
assert(noon.direct>light(12,'overcast').direct,'Cloud cover softens direct illumination');
assert(light(12,'fog').haze>noon.haze);
for(let hour=0;hour<24;hour+=.25) {
 const result=light(hour);
 assert(Math.abs(Math.hypot(...result.direction)-1)<1e-12);
 for(const key of ['direct','ambient','haze'])assert(Number.isFinite(result[key])&&result[key]>=0);
}
assert(light(7).color[2]<noon.color[2],'Low sun warms the light');
assert(vm.runInContext("materialResponse('glass')[0] < materialResponse('concrete')[0]",ctx));
assert(vm.runInContext("QUALITY.draft.shadowSize===0 && QUALITY.presentation.shadowSize > QUALITY.studio.shadowSize",ctx));
// Geometry keeps true normals and unlit material colour for moving light/shadow passes.
vm.runInContext(fs.readFileSync('palladio/web/viewport.js','utf8').replace(/^import .*$/gm,'').replace('export class','class'),ctx);
vm.runInContext(`
 const vertices=[];
 triangle(vertices,[0,0,0],[0,0,1],[1,0,0],[.6,.4,.2],[.8,0]);
 if(vertices.length!==33)throw Error('Interleaved geometry layout changed');
 if(vertices[6]!==0||vertices[7]!==1||vertices[8]!==0)throw Error('Ground normal is not upward');
 if(vertices[3]!==.6)throw Error('Material color was prelit');
 const test=Object.create(Viewport.prototype);let draws=0;test.draw=()=>draws++;
 test.setQuality('presentation');
 if(test.quality!=='presentation'||draws!==1)throw Error('Quality switch did not redraw');
 let rejected=false;try{test.setQuality('unknown');}catch{rejected=true;}if(!rejected)throw Error('Unknown quality accepted');
`,ctx);
console.log('PASS: moving sun, night/cloud response, material roughness, normals and render-quality switching');
