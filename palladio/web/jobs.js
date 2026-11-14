export class JobTools {
  constructor(find,hooks) {
    this.find=find;this.hooks=hooks;this.items=[];this.property='';this.generation=0;
    find('job-refresh').addEventListener('click',()=>hooks.run(()=>this.refresh()));
    find('job-list').addEventListener('change',()=>{hooks.invalidate();this.details();});
    find('job-outline').addEventListener('click',()=>hooks.run(async()=>{
      const model=hooks.state().model;if(!model)throw new Error('Choose an installed local model in the agent panel first.');
      const result=await hooks.api('/api/agent/job-outline',{brief:find('job-brief').value,model});
      if(!find('job-title').value)find('job-title').value=result.title;find('job-steps').value=result.steps.join('\n');
      find('job-agent-status').textContent='Suggested outline only. Edit the steps, then Save design job.';
    }));
    for(const action of ['propose','review'])find('job-'+action).addEventListener('click',()=>hooks.run(async()=>{
      const job=this.chosen(),{project,provider,model,selected,query,references}=hooks.state();if(!job)return;hooks.showPlan();
      const result=await hooks.api('/api/properties/'+project.id+'/jobs/'+job.id,{action,version:job.version,revision:project.revision,provider,model,selection:selected,query,references});
      if(hooks.state().project?.id!==project.id||hooks.state().project.revision!==result.plan.revision)throw new Error('Property changed. Reload and preview again.');
      await this.refresh(job.id);hooks.showPlan(result.plan);
      find('job-agent-status').textContent=result.plan.commands.length?'Review the scene proposal, then Apply to save the scene and complete this step.':'The agent needs clarification; this step remains pending.';
    }));
    find('job-form').addEventListener('submit',event=>{event.preventDefault();hooks.run(async()=>{
      const {project}=hooks.state();const job=await hooks.api('/api/properties/'+project.id+'/jobs',{title:find('job-title').value,brief:find('job-brief').value,steps:find('job-steps').value.split('\n').map(s=>s.trim()).filter(Boolean)});
      await this.refresh(job.id);
    });});
    for(const action of ['start','pause','resume','cancel','checkpoint'])find('job-'+action).addEventListener('click',()=>hooks.run(async()=>{
      const job=this.chosen(),{project}=hooks.state();if(!job)return;
      hooks.showPlan();const result=await hooks.api('/api/properties/'+project.id+'/jobs/'+job.id,{action,version:job.version,revision:project.revision,note:find('job-note').value});
      await this.refresh(result.id);
    }));
  }
  apply(plan){return this.hooks.run(async()=>{
    const {project}=this.hooks.state();this.hooks.showPlan();
    const result=await this.hooks.api('/api/properties/'+project.id+'/jobs/'+plan.job.id,{action:'apply',version:plan.job.version,revision:plan.revision});
    this.hooks.open(result.project);await this.refresh(result.job.id);await this.hooks.reloadLibrary();
  });}
  discard(plan){return this.hooks.run(async()=>{
    const {project}=this.hooks.state();this.hooks.showPlan();
    await this.hooks.api('/api/properties/'+project.id+'/jobs/'+plan.job.id,{action:'discard',version:plan.job.version});await this.refresh(plan.job.id);
  });}
  chosen(){return this.items.find(j=>j.id===this.find('job-list').value);}
  async refresh(preferred){
    const {project}=this.hooks.state();if(!project)return;const generation=++this.generation;
    const items=await this.hooks.api('/api/properties/'+project.id+'/jobs');
    if(generation!==this.generation||this.hooks.state().project?.id!==project.id)return;
    this.items=items;const list=this.find('job-list'),previous=preferred||list.value;
    list.replaceChildren(...items.map(j=>new Option(j.title+' · '+j.status,j.id)));if(items.some(j=>j.id===previous))list.value=previous;
    this.details();
  }
  details(){
    const job=this.chosen();this.find('job-details').textContent=job?job.brief+'\n\n'+job.steps.map((s,i)=>(i+1)+'. ['+s.status+'] '+s.instruction+(s.revision?' · revision '+s.revision+' · '+s.note:'')).join('\n\n'):'Create an ordered brief, or choose a saved job.';
    this.sync();
  }
  render(){
    const id=this.hooks.state().project?.id||'';if(id===this.property)return;
    this.property=id;this.generation++;this.items=[];this.find('job-list').replaceChildren();this.details();
    if(id)this.refresh().catch(error=>{if(this.property===id)this.find('job-details').textContent=error.message;});
  }
  sync(){
    const {busy,project,baselineView}=this.hooks.state(),disabled=busy||!project||baselineView,job=this.chosen();
    for(const node of this.find('jobs-panel').querySelectorAll('input,textarea,select,button'))node.disabled=disabled;
    for(const [action,state] of Object.entries({start:'ready',pause:'active',resume:'paused',checkpoint:'active'}))this.find('job-'+action).disabled=disabled||job?.status!==state;
    this.find('job-outline').disabled=disabled||!this.hooks.state().model;
    this.find('job-propose').disabled=disabled||job?.status!=='active';
    this.find('job-review').disabled=disabled||job?.status!=='active'||!job?.proposal;
    this.find('job-cancel').disabled=disabled||!job||['completed','cancelled'].includes(job.status);
  }
}
