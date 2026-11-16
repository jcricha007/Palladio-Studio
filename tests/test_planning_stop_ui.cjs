const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),find=id=>{if(!nodes.has(id))nodes.set(id,{value:'',events:{},addEventListener(n,f){this.events[n]=f;},querySelectorAll(){return [];},replaceChildren(...items){this.value=items[0]?.value||'';}});return nodes.get(id);};
let project={id:'p',revision:1},busy=false,shown,calls=[],release,stopFailure=false;
let job={id:'j',version:2,title:'Job',brief:'Brief',status:'active',steps:[{id:'step',status:'pending',instruction:'Set weather'}]};
const hooks={state:()=>({project,busy,provider:'ollama',model:'local:latest'}),showPlan:p=>shown=p,invalidate(){},
  run:async f=>{busy=true;try{return await f();}finally{busy=false;}},api:async(url,data,signal)=>{
    calls.push({url,data,signal});if(!data)return [job];
    if(data.action==='stop_planning'){if(stopFailure)throw Error('Connection lost');job={...job,status:'paused',version:job.version+1};return job;}
    // Intentionally ignores AbortSignal, exercising late-result protection.
    return new Promise(r=>release=r);
  }};
const ctx=vm.createContext({find,hooks,AbortController,crypto:require('node:crypto').webcrypto,Option:function(text,value){this.value=value;}});
vm.runInContext(fs.readFileSync('palladio/web/jobs.js','utf8').replace('export class','class')+';const jobs=new JobTools(find,hooks);jobs.property="p";',ctx);
(async()=>{
  await vm.runInContext('jobs.refresh()',ctx);
  const pending=find('job-propose').events.click();assert.equal(find('job-stop').disabled,false);assert.equal(busy,true);
  const late=release;await find('job-stop').events.click();await pending;
  assert.equal(busy,false);assert.equal(job.status,'paused');assert.equal(shown,undefined);
  const proposal=calls.find(c=>c.data?.action==='propose'),stop=calls.find(c=>c.data?.action==='stop_planning');
  assert.equal(stop.data.request_id,proposal.data.request_id);assert.equal(stop.data.step_id,'step');assert.equal(stop.data.version,2);assert.equal(proposal.signal.aborted,true);
  late({job,plan:{revision:1,commands:[{action:'remove',id:'x'}]}});await new Promise(r=>setImmediate(r));assert.equal(shown,undefined);
  assert.match(find('job-agent-status').textContent,/Job paused/);
  find('job-steps').value='Keep draft';const outline=find('job-outline').events.click(),lateOutline=release;
  await find('job-stop').events.click();await outline;lateOutline({title:'Late',steps:['Overwrite draft']});await new Promise(r=>setImmediate(r));
  assert.equal(find('job-steps').value,'Keep draft');assert.equal(calls.filter(c=>c.data?.action==='stop_planning').length,1);
  job={...job,status:'active',version:4};await vm.runInContext('jobs.refresh()',ctx);stopFailure=true;
  const fail=find('job-propose').events.click();await find('job-stop').events.click();await fail;
  assert.match(find('job-agent-status').textContent,/could not confirm/);assert.equal(shown,undefined);assert.equal(busy,false);
  stopFailure=false;const other=find('job-propose').events.click();project={id:'other',revision:1};vm.runInContext('jobs.render()',ctx);await other;
  assert.equal(calls.filter(c=>c.data?.action==='stop_planning').at(-1).url,'/api/properties/p/jobs/j');assert.equal(shown,undefined);
  console.log('PASS: request-scoped stop, durable pause, ignored late replies, untouched outline drafts, stop failures and property switching');
})().catch(error=>{console.error(error);process.exitCode=1;});
