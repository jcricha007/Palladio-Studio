const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),find=id=>{if(!nodes.has(id))nodes.set(id,{value:'',checked:false,files:[],events:{},addEventListener(n,f){this.events[n]=f;},querySelectorAll(){return [];},removeAttribute(n){delete this[n];},replaceChildren(...items){this.value=items[0]?.value||'';}});return nodes.get(id);};
let task,commands,lastError,invalidations=0,project={id:'p',revision:2,scene:{references:[{id:'r',name:'Sketch',cues:'Warm timber',mime:'image/png',data:'AA=='}]}},prepare=async()=> 'image bytes';
const hooks={run:f=>(task=f().catch(e=>{lastError=e;})),state:()=>({project}),preview:c=>commands=c,invalidate:()=>invalidations++};
let revoked=0;
const canvas={width:0,height:0,getContext:()=>({fillRect(){},drawImage(){}}),toDataURL:()=> 'data:image/jpeg;base64,cGljdHVyZQ=='};
const context=vm.createContext({find,hooks,prepare:f=>prepare(f),Option:function(label,value){this.value=value;},
  URL:{createObjectURL:()=> 'blob:local',revokeObjectURL:()=> revoked++},Image:class{naturalWidth=2048;naturalHeight=1024;async decode(){}},document:{createElement:()=> canvas}});
vm.runInContext(fs.readFileSync('palladio/web/references.js','utf8').replace('export async function','async function').replace('export class','class')+'\nconst refs=new ReferenceTools(find,hooks,prepare);',context);
(async()=>{
  assert.equal(await vm.runInContext('prepareReference({type:"image/png",size:100})',context),'cGljdHVyZQ==');
  assert.equal(canvas.width,1024);assert.equal(canvas.height,512);assert.equal(revoked,1);
  await assert.rejects(vm.runInContext('prepareReference({type:"image/svg+xml",size:100})',context),/PNG or JPEG/);
  context.project=project;vm.runInContext('refs.render(project)',context);
  assert.equal(find('reference-image').src,'data:image/png;base64,AA==');assert.equal(find('reference-use').checked,false);
  find('reference-use').checked=true;find('reference-use').events.change();assert.equal(invalidations,1);
  assert.deepEqual(Array.from(vm.runInContext('refs.selected()',context)),['r']);
  find('reference-cues').value='Vertical grain';find('reference-save').events.click();assert.equal(commands[0].reference.cues,'Vertical grain');
  find('reference-remove').events.click();assert.equal(commands[0].id,'r');
  find('reference-form').events.submit({preventDefault(){}});await task;await new Promise(setImmediate);
  assert.equal(commands[0].action,'reference_add');assert.equal(commands[0].reference.image,'image bytes');
  context.project={...project,id:'other'};vm.runInContext('refs.render(project)',context);assert.equal(find('reference-use').checked,false);
  let release;prepare=()=>new Promise(r=>release=r);find('reference-form').events.submit({preventDefault(){}});
  project={...project,revision:3};release('late');await task;assert.match(lastError.message,/Property changed/);
  console.log('PASS: reference selection, cues, add/remove previews and property invalidation');
})().catch(error=>{console.error(error);process.exitCode=1;});
