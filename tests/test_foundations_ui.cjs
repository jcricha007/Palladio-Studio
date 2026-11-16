const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');const nodes=new Map(),find=id=>{if(!nodes.has(id))nodes.set(id,{value:'',events:{},addEventListener(n,f){this.events[n]=f;},querySelectorAll(){return [];}});return nodes.get(id);};
let commands;const group={id:'g',spec:{kind:'room'},members:{floor:'e'}},hooks={state:()=>({project:{scene:{assemblies:[group]}},selected:'e'}),preview:c=>commands=c,invalidate(){}};
for(const [key,value] of Object.entries({columns_x:3,columns_z:4,pier_width:.3,clearance:1.5}))find('foundation-'+key).value=String(value);
const ctx=vm.createContext({find,hooks});vm.runInContext(fs.readFileSync('palladio/web/foundations.js','utf8').replace('export class','class')+';const tools=new FoundationTools(find,hooks);tools.sync();',ctx);
find('foundation-raise').events.click();assert.equal(commands.length,2);assert.equal(commands[0].offset_m,1.5);assert.equal(commands[1].foundation.columns_z,4);assert.equal(find('foundation-refit').disabled,true);
group.spec.kind='foundation';vm.runInContext('tools.sync()',ctx);assert.equal(find('foundation-fit').disabled,true);assert.equal(find('foundation-refit').disabled,false);
console.log('PASS: explicit raised-host batch, foundation parameters and refit selection guards');
