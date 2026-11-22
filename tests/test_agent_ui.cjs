const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {readStudio}=require('./helpers/studio-source.cjs');
// DOM/fetch doubles exercise async UI state, not WebGL or model quality.
const root=process.argv[2] || process.cwd();
const nodes = new Map();
class Node {
  constructor(id='') { Object.assign(this, {id, value:'', hidden:false, disabled:false, dataset:{}, children:[], events:{}, classList:{toggle(){}}}); }
  addEventListener(event, fn) { (this.events[event] ??= []).push(fn); }
  setAttribute() {} querySelectorAll() { return this.children; }
  append(node) { this.children.push(node); }
  replaceChildren(...children) { this.children=children; if(children[0]?.value!==undefined) this.value=children[0].value; }
  reset() {} showModal() {} close() {} focus() {}
  get valueAsNumber() { return Number(this.value); }
}
const node = id => nodes.get(id) || (nodes.set(id,new Node(id)), nodes.get(id));
for(const m of fs.readFileSync(root+'/palladio/web/index.html','utf8').matchAll(/id="([^"]+)"/g)) node(m[1]);
const storage = new Map();
const updates = [];
let requests = [], responder;
const context = vm.createContext({
  console,Extensions:class{sync(){}render(){}},DesignTools:class{sync(){}render(){}},AssetTools:class{sync(){}render(){}},ReferenceTools:class{sync(){}render(){}selected(){return [];}}, AbortController,
  Option:function(label,value) { this.label=label; this.value=value; },
  localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
  document:{getElementById:node,querySelectorAll:()=>[...nodes.values()],createElement:()=>new Node()},
  history:{replaceState(){}},location:{hash:''},
  Viewport:class {reset(){} update(...args){updates.push(args)}},
  fetch:async(path,options)=>{requests.push({path,options});return responder(path,options)},
});
const source=readStudio(root);
vm.runInContext(fs.readFileSync(root+'/palladio/web/site-picker.js','utf8')
  .replace(/^import .+;$/gm,'').replace('export class SitePicker','class SitePicker'),context);
vm.runInContext(source,context);
assert.equal(requests.length,0,'Loading the UI test harness must not run application startup requests.');
const evaluate=s=>vm.runInContext(s,context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const emit=(id,event='click')=>node(id).events[event].forEach(fn=>fn({preventDefault(){}}));
const ok=value=>({ok:true,json:async()=>value});
const fixture={id:'property-one',name:'Property',revision:3,history:[{number:3,label:'current'}],
  scene:{elements:[{id:'wall-id',name:'Wall',material:'oak',position:[0,0,0],size:[1,1,1],yaw:0}],environment:{weather:'clear',hour:12}},
  baseline:{source:{profile:'meadow'},environment:{weather:'clear',hour:12}}};
context.fixture=fixture;
context.plan={revision:3,provider:'ollama',model:'model-a',summary:'Widen and add fog',commands:[
  {action:'update',id:'wall-id',element:{size:[2,1,1]}},{action:'environment',environment:{weather:'fog'}}],
  changes:['Resize Wall','Set weather to fog'],scene:{...fixture.scene,environment:{weather:'fog',hour:12},elements:[{...fixture.scene.elements[0],size:[2,1,1]}]}};
function reset() {
  evaluate('cancelAgentRequest(); cancelModelRequest(); busy=false; baselineView=false; catalog={materials:{oak:"#123456"},assemblies:{}}; showProject(fixture,true);');
  node('agent-provider').value='ollama'; node('agent-model').value='model-a'; node('request').value='Widen and add fog';
  evaluate('installedModels=["model-a","model-b"]; syncControls()');
  requests=[];
}
(async()=>{
  reset();
  // Installed model discovery requires explicit choice; no hardcoded auto-selection.
  node('agent-model').value='';
  responder=async()=>ok({models:[{name:'model-a'},{name:'model-b'}]});
  await evaluate('refreshModels()');
  assert.equal(node('agent-model').value,''); assert.equal(node('preview-request').disabled,true);
  node('agent-model').value='model-b'; emit('agent-model','change');
  assert.equal(storage.get('palladio.agent.model'),'model-b');
  await evaluate('refreshModels()'); assert.equal(node('agent-model').value,'model-b');
  responder=async()=>ok({models:[{name:'model-a'}]});
  await evaluate('refreshModels()'); assert.equal(node('agent-model').value,'');
  responder=async()=>ok({models:[]}); await evaluate('refreshModels()');
  assert.match(node('agent-status').textContent,/no models/); assert.equal(node('preview-request').disabled,true);
  responder=async()=>({ok:false,json:async()=>({error:'Cannot connect to Ollama'})});
  await evaluate('refreshModels()');assert.match(node('agent-status').textContent,/Cannot connect/);
  assert.equal(node('agent-status').dataset.error,'true'); assert.equal(node('agent-provider').disabled,false);
  node('agent-provider').value='rules'; emit('agent-provider','change');
  assert.equal(node('agent-model-label').hidden,true); assert.equal(node('preview-request').disabled,false);

  // A cancelled/replaced model discovery must not overwrite the current provider.
  reset(); let release;
  responder=async()=>{await new Promise(r=>release=r);return ok({models:[{name:'late-model'}]})};
  const refresh=evaluate('refreshModels()');
  node('agent-provider').value='rules';emit('agent-provider','change');
  assert.equal(requests[0].options.signal.aborted,true);release();await refresh;
  assert.equal(node('agent-provider').value,'rules');assert.match(node('agent-status').textContent,/no language model/);

  // Repeated submits issue exactly one request and never auto-apply.
  reset();
  responder=async()=>{await new Promise(r=>release=r);return ok(context.plan)};
  const first=evaluate('previewRequest()');await evaluate('previewRequest()');
  assert.equal(requests.length,1);assert.equal(node('preview-request').disabled,true);
  assert.equal(node('cancel-request').hidden,false);assert.equal(node('agent-model').disabled,false);
  const body=JSON.parse(requests[0].options.body);
  assert.equal(body.provider,'ollama');assert.equal(body.model,'model-a');assert.equal(body.revision,3);
  release();await first;
  assert.equal(requests.length,1);assert.equal(node('proposal').hidden,false);assert.equal(node('apply-plan').disabled,false);
  assert.equal(updates.at(-1)[0].scene.environment.weather,'fog');
  assert.equal(fixture.scene.environment.weather,'clear');assert.equal(fixture.scene.elements[0].size[0],1);
  assert.equal(node('proposal-changes').children.length,2);assert.match(node('proposal-source').textContent,/model-a/);
  assert.equal(node('proposal-commands').textContent,JSON.stringify(context.plan.commands,null,2));
  assert.equal(node('proposal-commands-detail').open,false);
  node('proposal-commands-detail').open=true;
  emit('discard-plan');assert.equal(node('proposal').hidden,true);assert.equal(updates.at(-1)[0],fixture);
  assert.equal(node('proposal-commands').textContent,'');assert.equal(node('proposal-commands-detail').open,false);

  // Validated scene data, not model prose or a raw command, drives review facts.
  const beforeAssemblies=[{id:'garage',members:{},spec:{kind:'garage',name:'Workshop',window_width:2,height:3.2}},
    {id:'existing-tree',members:{},spec:{kind:'pine',name:'Existing pine',height:7}}];
  const afterAssemblies=[{id:'garage',members:{},spec:{kind:'garage',name:'Workshop',window_width:2.4,height:3.2}},
    {id:'new-garage',spec:{kind:'garage',name:'New garage',height:3.2}},beforeAssemblies[1],
    ...[1,2,3,4].map(n=>({id:'new-tree-'+n,spec:{kind:'pine',name:'Courtyard pine '+n,height:7}}))];
  context.factBase={...fixture,scene:{...fixture.scene,assemblies:beforeAssemblies}};
  context.factPlan={...context.plan,summary:'Four 5 m trees and a 3 m garage.',
    scene:{...context.plan.scene,assemblies:afterAssemblies}};
  evaluate('showProject(factBase,true); showPlan(factPlan)');
  assert.equal(node('proposal-facts').hidden,false);
  assert.deepEqual(node('proposal-facts-list').children.map(n=>n.textContent),[
    'Workshop · Configured window width: 2 m → 2.4 m',
    'New garage · New shell height: 3.2 m',
    'Pine added (4): Courtyard pine 1 (7 m), Courtyard pine 2 (7 m), Courtyard pine 3 (7 m), Courtyard pine 4 (7 m)']);
  assert.equal(node('proposal-text').textContent,'Four 5 m trees and a 3 m garage.');
  assert.equal(beforeAssemblies[0].spec.window_width,2);
  emit('discard-plan');
  assert.equal(node('proposal-facts').hidden,true);
  assert.equal(node('proposal-facts-list').children.length,0);
  evaluate('showPlan({...factPlan,revision:2})');
  assert.equal(node('proposal-facts').hidden,true,'Do not compare a proposal to a different saved revision.');

  // Late replies after cancel, model/prompt/property/selection/view changes are ignored.
  for(const cancel of [
    ()=>emit('cancel-request'),
    ()=>{node('agent-model').value='model-b';emit('agent-model','change')},
    ()=>{node('request').value='different';emit('request','input')},
    ()=>evaluate('showProject({...fixture,id:"property-two"},true)'),
    ()=>evaluate('select("wall-id")'),
    ()=>emit('baseline-view'),
    ()=>emit('new-property'),
  ]) {
    reset();responder=async()=>{await new Promise(r=>release=r);return ok(context.plan)};
    const inFlight=evaluate('previewRequest()'); cancel();
    assert.equal(requests[0].options.signal.aborted,true);release();await inFlight;
    assert.equal(node('proposal').hidden,true);assert.equal(node('cancel-request').hidden,true);
  }

  // Obsolete errors cannot overwrite a newer model's result.
  reset();let rejectOld;
  responder=async()=>{await new Promise((_,reject)=>rejectOld=reject);return ok(context.plan)};
  const old=evaluate('previewRequest()');node('agent-model').value='model-b';emit('agent-model','change');
  responder=async()=>ok({...context.plan,model:'model-b'});
  await evaluate('previewRequest()');rejectOld(new Error('old error'));await old;
  assert.match(node('proposal-source').textContent,/model-b/);assert.doesNotMatch(node('agent-status').textContent,/old error/);

  // Stale response, connection error and invalid response show no actionable plan.
  for(const response of [ok({...context.plan,revision:4}),{ok:false,json:async()=>({error:'Inference already busy'})}]) {
    reset();responder=async()=>response;await evaluate('previewRequest()');
    assert.equal(node('proposal').hidden,true);assert.equal(node('apply-plan').disabled,true);
    assert.equal(node('agent-status').dataset.error,'true');
  }
  // A no-command reply is informative, not a scene edit or success claim.
  reset();responder=async()=>ok({...context.plan,commands:[],changes:[],summary:'Which wall?',scene:fixture.scene});
  await evaluate('previewRequest()');assert.equal(node('apply-plan').disabled,true);
  assert.equal(node('assembly-preview-badge').hidden,true);assert.equal(node('proposal-text').textContent,'Which wall?');
  assert.match(node('agent-status').textContent,/No scene changes/);

  // Applying a reviewed multi-command preview happens only once, at its revision.
  reset();responder=async()=>ok(context.plan);await evaluate('previewRequest()');requests=[];
  responder=async(path)=>{if(path.endsWith('/edit')){await new Promise(r=>release=r);return ok({...fixture,revision:4,scene:context.plan.scene})}return ok([])};
  emit('apply-plan');emit('apply-plan');assert.equal(requests.length,1);
  assert.equal(JSON.parse(requests[0].options.body).commands.length,2);
  assert.equal(JSON.parse(requests[0].options.body).revision,3);
  release();await tick();await tick();assert.equal(evaluate('project.revision'),4);
  assert.equal(node('proposal').hidden,true);assert.equal(node('agent-provider').disabled,false);
  console.log('PASS: model discovery/selection, empty/offline/error states, remembered model, repeated preview/apply, cancellation and late replies, model/prompt/property/selection/view invalidation, stale response, no-command reply, multi-edit preview immutability and atomic Apply');
})().catch(error=>{console.error(error);process.exitCode=1});
