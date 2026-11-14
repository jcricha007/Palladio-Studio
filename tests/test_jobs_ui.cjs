const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),find=id=>{if(!nodes.has(id))nodes.set(id,{value:'',events:{},addEventListener(n,f){this.events[n]=f;},querySelectorAll(){return [];},replaceChildren(...items){this.value=items[0]?.value||'';}});return nodes.get(id);};
let project={id:'p',revision:4},calls=[],reply;
const job={id:'j',version:3,title:'Cabin',brief:'Intent',status:'active',steps:[{instruction:'Build room',status:'pending'}]};
const hooks={state:()=>({project}),api:async(url,data)=>{calls.push({url,data});return data?job:reply||[job];},run:f=>f(),invalidate(){},showPlan(){}};
const ctx=vm.createContext({find,hooks,Option:function(text,value){this.value=value;}});vm.runInContext(fs.readFileSync('palladio/web/jobs.js','utf8').replace('export class','class')+';const jobs=new JobTools(find,hooks);',ctx);
(async()=>{
await vm.runInContext('jobs.refresh()',ctx);assert.equal(find('job-pause').disabled,false);assert.equal(find('job-start').disabled,true);
find('job-note').value='Reviewed';await find('job-checkpoint').events.click();const sent=calls.find(c=>c.data?.action==='checkpoint');assert.equal(sent.data.version,3);assert.equal(sent.data.revision,4);assert.equal(sent.data.note,'Reviewed');
let release;reply=new Promise(r=>release=r);const pending=vm.runInContext('jobs.refresh()',ctx);project={id:'other',revision:1};vm.runInContext('jobs.items=[];jobs.generation++;',ctx);release([job]);await pending;assert.equal(vm.runInContext('jobs.items.length',ctx),0);
console.log('PASS: job lifecycle controls, versioned checkpoints and late property responses');
})().catch(e=>{console.error(e);process.exitCode=1;});
