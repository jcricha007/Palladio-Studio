const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),find=id=>{if(!nodes.has(id))nodes.set(id,{value:'',events:{},addEventListener(n,f){this.events[n]=f;},querySelectorAll(){return [];},replaceChildren(...items){this.value=items[0]?.value||'';}});return nodes.get(id);};
let commands,selected='wall';const group={id:'g',members:{wall:'wall'},spec:{kind:'wall_run',openings:[]}},project={id:'p',revision:1,scene:{assemblies:[group],elements:[{id:'wall',kind:'wall'},{id:'independent',kind:'wall'}]}};
const hooks={state:()=>({project,selected}),preview:c=>commands=c,invalidate(){}};const ctx=vm.createContext({find,hooks,Option:function(text,value){this.value=value;}});
vm.runInContext(fs.readFileSync('palladio/web/walls.js','utf8').replace('export class','class')+';const tools=new WallTools(find,hooks);tools.render();tools.sync();',ctx);
assert.equal(find('wall-convert').disabled,true);find('opening-form').events.submit({preventDefault(){}});assert.equal(commands[0].id,'g');assert.equal(commands[0].opening.width,1.2);
find('opening-kind').value='door';find('opening-kind').events.change();assert.equal(find('opening-sill').value,0);
selected='independent';vm.runInContext('tools.render();tools.sync()',ctx);assert.equal(find('wall-convert').disabled,false);find('wall-convert').events.click();assert.equal(commands[0].id,'independent');
console.log('PASS: opening drafts, wall-group targeting and explicit independent-wall conversion');
