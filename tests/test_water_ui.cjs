const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');const nodes=new Map(),find=id=>{if(!nodes.has(id))nodes.set(id,{value:'',events:{},addEventListener(n,f){this.events[n]=f;},querySelectorAll(){return [];}});return nodes.get(id);};
let commands;const group={id:'g',members:{water:'e'},spec:{kind:'pool',name:'Pool',material:'stone',width:6,depth:10,height:1.5,yaw:0,water_level:1.2,position:[10,0,0]}};
const hooks={state:()=>({project:{id:'p',revision:2,scene:{assemblies:[group]}},selected:'e'}),preview:c=>commands=c,invalidate(){},run:f=>f(),api:async()=>({features:[{name:'Pool',litres:1000,surface_area_m2:5,water_depth_m:1}]})};
const ctx=vm.createContext({find,hooks});vm.runInContext(fs.readFileSync('palladio/web/water.js','utf8').replace('export class','class')+';const tools=new WaterTools(find,hooks);tools.render();tools.sync();',ctx);
find('water-water_level').value='.8';find('water-update').events.click();assert.equal(commands[0].assembly.water_level,.8);assert.equal(commands[0].id,'g');assert.equal(commands[0].assembly.kind,undefined);
find('water-kind').value='pond';vm.runInContext('tools.sync()',ctx);assert.equal(find('water-update').disabled,true);find('water-form').events.submit({preventDefault(){}});assert.equal(commands[0].assembly.kind,'pond');
console.log('PASS: water-feature creation, level edits and explicit type changes');
