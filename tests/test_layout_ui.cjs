const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),find=id=>{if(!nodes.has(id))nodes.set(id,{value:'',events:{},addEventListener(n,f){this.events[n]=f;},querySelectorAll(){return [];}});return nodes.get(id);};
let project={id:'p',revision:1,scene:{elements:[{id:'a',name:'Room slab'},{id:'b',name:'Bench'}]}},selected='a',commands,invalidations=0,task;
const hooks={state:()=>({project,selected,busy:false,baselineView:false}),preview:c=>commands=c,invalidate:()=>invalidations++,run:f=>(task=f()),api:async()=>({objects:2,parts:12,size:[8,3,5],origin_distance_m:4})};
const ctx=vm.createContext({find,hooks});vm.runInContext(fs.readFileSync('palladio/web/layout.js','utf8').replace('export class','class')+'\nconst panel=new LayoutTools(find,hooks);panel.render();',ctx);
(async()=>{
 find('layout-include').events.click();find('layout-include').events.click();selected='b';find('layout-include').events.click();
 find('layout-operation').value='move';find('layout-x').value='3';find('layout-y').value='0';find('layout-z').value='0';find('layout-spacing').value='1';find('layout-angle').value='0';find('layout-axis').value='x';
 find('layout-form').events.submit({preventDefault(){}});assert.deepEqual(Array.from(commands[0].layout.ids),['a','b']);assert.equal(commands[0].layout.offset[0],3);
 find('layout-measure').events.click();await task;assert.match(find('layout-measurement').textContent,/origin distance 4.000/);
 project={...project,id:'other'};vm.runInContext('panel.render()',ctx);assert.equal(find('layout-preview').disabled,true);assert.ok(invalidations>=3);
 console.log('PASS: layout set deduplication, preview, measurements and property switching');
})().catch(e=>{console.error(e);process.exitCode=1;});
