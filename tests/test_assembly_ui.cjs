const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
// State tests with a minimal DOM/viewport double; not browser/WebGL acceptance.
// Run from the repository root: node tests/test_assembly_ui.cjs
const root=process.argv[2] || process.cwd();
const nodes=new Map();
class Node {
 constructor(id=''){this.id=id;this.value='';this.hidden=false;this.disabled=false;this.dataset={};this.children=[];this.events={};this.classList={toggle(){}};}
 addEventListener(name,fn){(this.events[name]??=[]).push(fn)}
 setAttribute(){} querySelectorAll(){return this.children} append(n){this.children.push(n)}
 replaceChildren(...ns){this.children=ns;if(ns[0]?.value!==undefined)this.value=ns[0].value}
 reset(){} showModal(){} close(){} focus(){}
 get valueAsNumber(){return Number(this.value)}
}
const node=id=>nodes.get(id)|| (nodes.set(id,new Node(id)),nodes.get(id));
for(const m of fs.readFileSync(root+'/palladio/web/index.html','utf8').matchAll(/id="([^"]+)"/g))node(m[1]);
const updates=[];let requests=[];let response;
const context=vm.createContext({console,Option:function(label,value){this.label=label;this.value=value},document:{getElementById:node,querySelectorAll(){return [...nodes.values()]},createElement(){return new Node()}},history:{replaceState(){}},location:{hash:''},Viewport:class{reset(){} update(...x){updates.push(x)}},fetch:async(path,options)=>{requests.push({path,options});return response(path,options)}});
let source=fs.readFileSync(root+'/palladio/web/studio.js','utf8').replace('import {Viewport} from "./viewport.js";','');
source=source.slice(0,source.lastIndexOf('\nrender();\nrun(async'));
vm.runInContext(source,context);
const evaluate=s=>vm.runInContext(s,context);
const scene={elements:[{id:'saved',name:'Wall',material:'oak',position:[0,0,0],size:[1,1,1],yaw:0}],environment:{weather:'clear',hour:16}};
const project={id:'one',name:'Property',revision:1,history:[{number:1,label:'created'}],scene,baseline:{environment:scene.environment,source:{profile:'meadow'}}};
context.fixture=project;
evaluate('catalog={materials:{oak:"#123456"},assemblies:{room:{label:"Room shell",width:6,height:3,depth:5,material:"oak",limits:{width:[3,30],height:[2.5,8],depth:[3,30]}}}}; showProject(fixture)');
node('assembly-kind').value='room';evaluate('assemblyDefaults()');
assert.equal(node('assembly-width').value,6);assert.equal(node('assembly-width').min,3);assert.equal(node('assembly-height').max,8);
const plan={revision:1,summary:'Preview room',command:{action:'assembly',assembly:{kind:'room'}},elements:[{...scene.elements[0],id:'preview'}]};
context.plan=plan;
evaluate('showPlan(plan)');
assert.equal(updates.at(-1)[0].scene.elements.length,2);
assert.equal(project.scene.elements.length,1);
assert.equal(node('assembly-preview-badge').hidden,false);
evaluate('discardOnEdit()');
assert.equal(updates.at(-1)[0],project);assert.equal(node('proposal').hidden,true);
for(const event of ['input','change']){evaluate('showPlan(plan)');for(const fn of node('assembly-form').events[event])fn({});assert.equal(node('proposal').hidden,true)}
evaluate('showPlan(plan); select("saved")');assert.equal(node('proposal').hidden,true);
evaluate('showPlan(plan)');node('baseline-view').events.click[0]();assert.equal(node('proposal').hidden,true);assert.equal(updates.at(-1)[1],true);
node('design-view').events.click[0]();evaluate('showPlan(plan); showProject({...fixture,id:"two"},true)');assert.equal(node('proposal').hidden,true);
(async()=>{
 evaluate('showProject(fixture); showPlan(plan)');
 let release;const gate=new Promise(r=>release=r);
 response=async(path)=>{if(path.endsWith('/edit')){await gate;return {ok:true,json:async()=>({...project,revision:2,scene:{...scene,elements:[...scene.elements,{...scene.elements[0],id:'new'}]},history:[{number:2,label:'assembly'},{number:1,label:'created'}]})}}return {ok:true,json:async()=>[]}};
 node('apply-plan').events.click[0]();node('apply-plan').events.click[0]();
 assert.equal(requests.length,1);assert.equal(node('assembly-kind').disabled,true);assert.equal(node('discard-plan').disabled,true);
 assert.equal(JSON.parse(requests[0].options.body).revision,1);assert.equal(JSON.parse(requests[0].options.body).commands.length,1);
 release(); await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));
 assert.equal(evaluate('project.revision'),2);assert.equal(node('proposal').hidden,true);assert.equal(node('assembly-kind').disabled,false);
 // Stale application clears unsaved geometry and retains saved property.
 evaluate('showPlan({...plan,revision:2})');requests=[];
 response=async()=>({ok:false,json:async()=>({error:'Reload stale property'})});
 node('apply-plan').events.click[0]();await new Promise(r=>setImmediate(r));
 assert.equal(evaluate('project.revision'),2);assert.equal(node('proposal').hidden,true);assert.match(node('status').textContent,/Reload stale/);
 console.log('PASS: preview immutability, discard, input/change invalidation, selection, baseline/property switching, repeated apply, busy controls, revision binding, stale apply');
})().catch(e=>{console.error(e);process.exitCode=1});
