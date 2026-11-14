const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),find=id=>{if(!nodes.has(id))nodes.set(id,{value:'',events:{},addEventListener(n,f){this.events[n]=f;},querySelectorAll(){return [];},replaceChildren(...items){this.value=items[0]?.value||'';}});return nodes.get(id);};
let project={id:'p',revision:1},job={id:'j',version:3,title:'Job',brief:'Brief',status:'active',steps:[],proposal:{}},shown,opened,calls=[];
const plan={revision:1,job:{id:'j',version:3},commands:[{action:'environment',environment:{hour:12}}]};
const hooks={state:()=>({project,provider:'ollama',model:'local:latest',selected:'part',query:'house',references:['ref']}),showPlan:p=>shown=p,open:p=>opened=p,reloadLibrary:async()=>{},invalidate(){},run:f=>f(),api:async(url,data)=>{
 calls.push({url,data});if(!data)return [job];if(data.action==='propose'||data.action==='review')return {job,plan};if(data.action==='apply')return {job:{...job,version:4},project:{...project,revision:2}};return job;
}};
const ctx=vm.createContext({find,hooks,plan,Option:function(text,value){this.value=value;}});vm.runInContext(fs.readFileSync('palladio/web/jobs.js','utf8').replace('export class','class')+';const jobs=new JobTools(find,hooks);',ctx);
(async()=>{await vm.runInContext('jobs.refresh()',ctx);await find('job-propose').events.click();assert.equal(shown,plan);assert.equal(calls.find(c=>c.data?.action==='propose').data.references[0],'ref');
await vm.runInContext('jobs.apply(plan)',ctx);const applied=calls.find(c=>c.data?.action==='apply');assert.equal(applied.data.version,3);assert.equal(applied.data.revision,1);assert.equal(opened.revision,2);
await vm.runInContext('jobs.discard(plan)',ctx);assert.ok(calls.some(c=>c.data?.action==='discard'));console.log('PASS: agent job preview context, version-bound Apply and persistent discard');
})().catch(e=>{console.error(e);process.exitCode=1;});
