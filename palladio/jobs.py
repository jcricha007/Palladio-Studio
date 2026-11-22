"""Persistent, ordered design briefs with optimistic versions and explicit checkpoints."""
import json
from uuid import UUID,uuid4
from .scene import ValidationError,required_text
from .store import MissingProject,RevisionConflict,timestamp


def outline(data):
    title=required_text(data.get('title'),'Job title',100);brief=required_text(data.get('brief'),'Design brief',64000)
    steps=data.get('steps')
    if not isinstance(steps,list) or not 1<=len(steps)<=32:raise ValidationError('Provide 1–32 ordered steps.')
    return {'title':title,'brief':brief,'status':'ready','steps':[{'id':str(uuid4()),'instruction':required_text(s,'Step instruction',8000),'status':'pending'} for s in steps]}


def current_step(job):
    return next((step for step in job['steps'] if step['status']=='pending'),None)


def request_identity(data,step):
    key=data.get('request_id')
    if key is None:return None
    try:
        if not isinstance(key,str) or str(UUID(key))!=key:raise ValueError()
    except (ValueError,TypeError,AttributeError):raise ValidationError('Use a unique planning request ID.')
    return {'id':key,'version':data.get('version'),'step_id':step['id']}


class DesignJobs:
    def __init__(self,library):self.library=library
    @staticmethod
    def unpack(row):
        return {**json.loads(row['data']),'id':row['id'],'project_id':row['project_id'],'version':row['version'],'updated':row['updated']}
    def read(self,connection,project_id,job_id):
        row=connection.execute('SELECT * FROM design_jobs WHERE project_id=? AND id=?',(project_id,job_id)).fetchone()
        if row is None:raise MissingProject('Design job not found for this property.')
        return self.unpack(row)
    def get(self,project_id,job_id):
        with self.library.connect() as connection:return self.read(connection,project_id,job_id)
    def list(self,project_id):
        with self.library.connect() as connection:
            self.library._read(connection,project_id)
            return [self.unpack(r) for r in connection.execute('SELECT * FROM design_jobs WHERE project_id=? ORDER BY updated DESC,id',(project_id,))]
    def create(self,project_id,data):
        job=outline(data);key=str(uuid4())
        with self.library.connect(write=True) as connection:
            self.library._read(connection,project_id)
            if connection.execute('SELECT COUNT(*) FROM design_jobs WHERE project_id=?',(project_id,)).fetchone()[0]>=40:raise ValidationError('Keep at most 40 design jobs per property.')
            connection.execute('INSERT INTO design_jobs VALUES(?,?,1,?,?)',(key,project_id,timestamp(),json.dumps(job)))
            return self.read(connection,project_id,key)
    @staticmethod
    def check_version(job,version):
        if type(version) is not int or version<1:raise ValidationError('A current job version is required.')
        if job['version']!=version:raise RevisionConflict('This job changed in another session. Refresh jobs before continuing.')
    def save(self,connection,job):
        data={k:v for k,v in job.items() if k not in ('id','project_id','version','updated')}
        connection.execute('UPDATE design_jobs SET version=version+1,updated=?,data=? WHERE id=?',(timestamp(),json.dumps(data),job['id']))
        return self.read(connection,job['project_id'],job['id'])
    def change(self,project_id,job_id,data):
        with self.library.connect(write=True) as connection:
            job=self.read(connection,project_id,job_id);self.check_version(job,data.get('version'));action=data.get('action')
            if not isinstance(action,str):raise ValidationError('Choose a supported job operation.')
            transitions={'start':('ready','active'),'pause':('active','paused'),'resume':('paused','active')}
            if action in transitions:
                before,after=transitions[action]
                if job['status']!=before:raise ValidationError(f'Only a {before} job can {action}.')
                job['status']=after;job.pop('proposal',None)
            elif action=='cancel':
                if job['status'] in ('completed','cancelled'):raise ValidationError('This job has already ended.')
                job['status']='cancelled';job.pop('proposal',None)
            elif action=='revise':
                if job['status']!='ready':raise ValidationError('Revise the outline before starting the job.')
                job.update(outline(data))
            elif action=='checkpoint':
                if job['status']!='active':raise ValidationError('Start or resume this job before recording a checkpoint.')
                project=self.library._read(connection,project_id)
                if type(data.get('revision')) is not int or data['revision']!=project['revision']:raise RevisionConflict('The property changed. Review its latest revision before recording a checkpoint.')
                note=required_text(data.get('note'),'Checkpoint note',1000)
                step=current_step(job);step.update(status='complete',revision=project['revision'],note=note,completed=timestamp(),method='manual')
                job.pop('proposal',None)
                if current_step(job) is None:job['status']='completed'
            else:raise ValidationError('Choose a supported job operation.')
            job.pop('last_plan_request',None)
            return self.save(connection,job)

    def stop_planning(self,project_id,job_id,data):
        # A stop may arrive before inference starts or immediately after its proposal
        # saves. Match that exact request; never pause a later step/session.
        with self.library.connect(write=True) as connection:
            job=self.read(connection,project_id,job_id);step=current_step(job)
            if job['status']!='active' or step is None or data.get('step_id')!=step['id']:
                raise RevisionConflict('This job moved on. Refresh jobs before pausing it.')
            request=request_identity(data,step);version=data.get('version')
            if request is None or type(version) is not int or version<1:raise ValidationError('Provide the planning request ID and starting job version.')
            if job['version']!=version and not (job['version']==version+1 and job.get('last_plan_request')==request):
                raise RevisionConflict('This job changed outside that planning request. Refresh jobs before pausing it.')
            job['status']='paused';job.pop('proposal',None);job.pop('last_plan_request',None)
            return self.save(connection,job)

    def propose(self,project_id,job_id,data,agent):
        job=self.get(project_id,job_id);self.check_version(job,data.get('version'))
        if job['status']!='active':raise ValidationError('Start or resume this job before previewing a step.')
        project=self.library.get(project_id)
        if type(data.get('revision')) is not int or data['revision']!=project['revision']:raise RevisionConflict('Reload the property before planning this step.')
        step=current_step(job);request=request_identity(data,step);provider=data.get('provider','rules');context=None
        if provider=='ollama':
            required_text(job['brief'],'Brief for local planning',16000)
            index=job['steps'].index(step)
            context={'title':job['title'],'brief':job['brief'],'current_step':index+1,'total_steps':len(job['steps']),
                     'nearby_steps':[{'number':i+1,'instruction':s['instruction'][:500],'status':s['status']} for i,s in enumerate(job['steps']) if index-4<=i<=index+2],
                     'nearby_instructions_may_be_truncated':True}
        plan=agent.preview(project,step['instruction'],data.get('selection'),provider=provider,model=data.get('model'),
                           revision=project['revision'],references=data.get('references'),query=data.get('query',''),job_context=context)
        # Inference runs outside the write lock. A paused/cancelled/changed job invalidates a late response.
        with self.library.connect(write=True) as connection:
            latest=self.read(connection,project_id,job_id);self.check_version(latest,job['version'])
            if self.library._read(connection,project_id)['revision']!=project['revision']:raise RevisionConflict('The property changed while this step was planned. Preview again.')
            changed=False
            if plan['commands']:
                latest['proposal']={k:v for k,v in plan.items() if k not in ('scene','command','elements')}
                changed=True
            elif latest.pop('proposal',None) is not None:changed=True
            if request is not None:latest['last_plan_request']=request;changed=True
            elif latest.pop('last_plan_request',None) is not None:changed=True
            if changed:latest=self.save(connection,latest)
            return {'job':latest,'plan':{**plan,'job':{'id':latest['id'],'version':latest['version']}}}

    def review(self,project_id,job_id,data):
        from .commands import preview_commands
        with self.library.connect() as connection:
            # A review needs the versioned job and property from one SQLite snapshot.
            connection.execute("BEGIN")
            job=self.read(connection,project_id,job_id);self.check_version(job,data.get('version'))
            proposal=job.get('proposal')
            if job['status']!='active' or not proposal:raise ValidationError('Preview the current step first.')
            project=self.library._read(connection,project_id)
            if type(data.get('revision')) is not int or data['revision']!=project['revision']:raise RevisionConflict('Reload before reviewing a saved proposal.')
        # Preview generation can be expensive. Keep the database available to other
        # sessions; suppress the result if another request changed either input.
        plan=preview_commands(project,proposal['revision'],proposal['commands'])
        with self.library.connect() as connection:
            connection.execute("BEGIN")
            latest=self.read(connection,project_id,job_id)
            self.check_version(latest,job['version'])
            latest_revision=connection.execute(
                "SELECT revision FROM properties WHERE id=?", (project_id,)
            ).fetchone()
            if latest_revision is None or latest_revision['revision']!=project['revision']:
                raise RevisionConflict('The property changed while reviewing this proposal. Reload before continuing.')
        return {'job':job,'plan':{**proposal,'scene':plan['scene'],'changes':plan['changes'],'warnings':plan['warnings'],'job':{'id':job_id,'version':job['version']}}}

    def apply(self,project_id,job_id,data):
        with self.library.connect(write=True) as connection:
            job=self.read(connection,project_id,job_id);self.check_version(job,data.get('version'));proposal=job.get('proposal')
            if job['status']!='active' or not proposal:raise ValidationError('Review a current job proposal before applying it.')
            if type(data.get('revision')) is not int or data['revision']!=proposal['revision']:raise RevisionConflict('This preview belongs to an earlier property revision.')
            project=self.library._commit(connection,project_id,proposal['revision'],proposal['commands'])
            current_step(job).update(status='complete',revision=project['revision'],note=proposal['summary'],method='agent',completed=timestamp())
            job.pop('proposal');job['status']='active' if current_step(job) else 'completed'
            job.pop('last_plan_request',None)
            return {'project':project,'job':self.save(connection,job)}

    def discard(self,project_id,job_id,data):
        with self.library.connect(write=True) as connection:
            job=self.read(connection,project_id,job_id);self.check_version(job,data.get('version'))
            job.pop('proposal',None);job.pop('last_plan_request',None);return self.save(connection,job)
