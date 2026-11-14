"""Persistent, ordered design briefs with optimistic versions and explicit checkpoints."""
import json
from uuid import uuid4
from .scene import ValidationError,required_text
from .store import MissingProject,RevisionConflict,timestamp


def outline(data):
    title=required_text(data.get('title'),'Job title',100);brief=required_text(data.get('brief'),'Design brief',64000)
    steps=data.get('steps')
    if not isinstance(steps,list) or not 1<=len(steps)<=32:raise ValidationError('Provide 1–32 ordered steps.')
    return {'title':title,'brief':brief,'status':'ready','steps':[{'id':str(uuid4()),'instruction':required_text(s,'Step instruction',8000),'status':'pending'} for s in steps]}


def current_step(job):
    return next((step for step in job['steps'] if step['status']=='pending'),None)


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
            return self.save(connection,job)
