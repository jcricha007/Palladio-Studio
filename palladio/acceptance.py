"""Create an isolated architecture walkthrough. Never reuse an existing database."""
import argparse
import json
from pathlib import Path
from .jobs import DesignJobs
from .scene import ValidationError
from .store import Library


def create_fixture(path):
    path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('xb'):pass
    except FileExistsError as error:
        raise ValidationError('Acceptance requires a new database path. Existing libraries are never overwritten.') from error
    library=Library(path);project=library.create('Architecture review · five PRs','An open meadow for the architecture review')
    def edit(*commands):
        nonlocal project
        project=library.commit(project['id'],project['revision'],list(commands))
    edit({'action':'terrain_layer','layer':{'name':'Review clearing','mode':'flatten','center':[0,0],'radius_m':55,'height_m':0}},
         {'action':'assembly','assembly':{'kind':'dwelling','name':'Raised meadow house','width':12,'depth':8,'height':3,
             'position':[-8,1.2,-6],'rooms_x':2,'rooms_z':2}},
         {'action':'assembly','assembly':{'kind':'wall_run','name':'Opening review wall','width':10,'height':3,'position':[4,0,7],
             'openings':[{'key':'entry','kind':'door','center':-2,'width':1.4,'height':2.2},
                         {'key':'view','kind':'window','center':2,'width':2,'height':1.2,'sill':.9}]}},
         {'action':'assembly','assembly':{'kind':'pool','name':'Pool collision review','width':6,'depth':9,'height':2.5,
             'position':[13,0,-7],'water_level':2.2}},
         {'action':'assembly','assembly':{'kind':'pond','name':'Garden pond','width':7,'depth':6,'height':1.2,
             'position':[14,0,10],'water_level':1}},
         {'action':'assembly','assembly':{'kind':'stairs','name':'House entry stairs','width':1.5,'depth':4,'height':1.35,
             'steps':9,'position':[-11,0,0],'yaw':180}})
    house=project['scene']['assemblies'][0]
    edit({'action':'foundation_fit','id':house['id'],'foundation':{'columns_x':3,'columns_z':3}},
         {'action':'roof_fit','id':house['id'],'roof':{'kind':'gable_roof','name':'Meadow house roof','height':2,'overhang':.5}},
         {'action':'planting','planting':{'kind':'broadleaf','center':[-21,14],'radius_m':5,'count':3,'seed':13}},
         {'action':'finish_apply','scope':'part','ids':[next(iter(house['members'].values()))],'finish_id':'builtin:light-tile'})
    for name,target,azimuth,pitch,distance,fov in [
        ('Site overview',[2,1,1],.7,.6,55,55),
        ('Wall doorway',[2,1.2,7],3.141592653589793,.15,10,50),
        ('Raised foundations',[-8,.6,-6],2.1,.3,18,50),
        ('Pool collision',[13,.3,-7],0,1.3,3,55),
        ('Pond layout',[14,.8,10],.8,.65,14,50),
    ]:
        edit({'action':'view_save','name':name,'camera':{'target':target,'azimuth':azimuth,'pitch':pitch,'distance':distance,'fov_degrees':fov}})
    job=DesignJobs(library).create(project['id'],{'title':'Architecture review job',
        'brief':'Keep the meadow house and its separate foundations. Review every proposal before applying it. '
                'Test weather first, then use a local model for the existing keyed opening and water level. No terrain excavation.',
        'steps':['set weather to fog',
                 'Set the view window in Opening review wall to 2.4 m wide, keeping its key, centre, sill, frame and height. Lower Pool collision review water_level to 2.0 m. Leave everything else unchanged.',
                 'Refit the existing Raised meadow house foundations to the saved terrain. Keep the house and foundation top fixed.']})
    return {'library_path':str(path),'property_id':project['id'],'name':project['name'],'revision':project['revision'],
            'job_id':job['id'],'views':[v['name'] for v in project['scene']['views']],
            'assemblies':[g['spec']['name'] for g in project['scene']['assemblies']],
            'acceptance':'fixture prepared; interactive checks have not run'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--library',required=True,type=Path)
    args=parser.parse_args()
    try:result=create_fixture(args.library)
    except ValidationError as error:parser.exit(2,str(error)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=True))


if __name__=='__main__':main()
