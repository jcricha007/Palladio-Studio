export class RoofTools {
  constructor(find,hooks) {
    this.find=find;this.hooks=hooks;
    find('roof-fit').addEventListener('click',()=>{
      const {project,selected}=hooks.state();const group=project.scene.assemblies?.find(g=>Object.values(g.members).includes(selected));
      if(group)hooks.preview([{action:'roof_fit',id:group.id,roof:{kind:find('assembly-kind').value,name:find('assembly-name').value,
        height:Number(find('assembly-height').value),material:find('assembly-material').value,overhang:Number(find('assembly-overhang').value)}}]);
    });
    find('assembly-kind').addEventListener('change',()=>this.render());
  }
  render() {this.find('assembly-overhang-label').hidden=!this.find('assembly-kind').value.endsWith('_roof');this.sync();}
  sync() {
    const {project,selected,busy,baselineView}=this.hooks.state();
    const group=project?.scene.assemblies?.find(g=>Object.values(g.members).includes(selected));
    this.find('roof-fit').disabled=busy||baselineView||!this.find('assembly-kind').value.endsWith('_roof')||!['room','garage','dwelling'].includes(group?.spec.kind);
  }
}
