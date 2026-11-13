// Decode locally, bound dimensions and strip file metadata before saving a copy.
export async function prepareReference(file) {
  if(!file || !['image/png','image/jpeg'].includes(file.type) || file.size>10000000)
    throw new Error('Choose a PNG or JPEG photo/sketch up to 10 MB.');
  const url=URL.createObjectURL(file);
  try {
    const img=new Image();img.src=url;await img.decode();
    const ratio=Math.min(1,1024/Math.max(img.naturalWidth,img.naturalHeight));
    const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(img.naturalWidth*ratio));canvas.height=Math.max(1,Math.round(img.naturalHeight*ratio));
    const drawing=canvas.getContext('2d');drawing.fillStyle='#ffffff';drawing.fillRect(0,0,canvas.width,canvas.height);drawing.drawImage(img,0,0,canvas.width,canvas.height);
    for(const quality of [.85,.65,.45]) {
      const data=canvas.toDataURL('image/jpeg',quality).split(',')[1];
      if(data.length<=666664)return data;
    }
    throw new Error('This image is too detailed. Choose a smaller crop.');
  } finally {URL.revokeObjectURL(url);}
}

export class ReferenceTools {
  constructor(find,hooks,prepare=prepareReference) {
    this.find=find;this.hooks=hooks;this.prepare=prepare;this.items=[];this.projectId=null;this.revision=null;
    find('reference-list').addEventListener('change',()=>{hooks.invalidate();this.show();});
    find('reference-use').addEventListener('change',hooks.invalidate);
    find('reference-form').addEventListener('input',hooks.invalidate);
    find('reference-form').addEventListener('change',hooks.invalidate);
    find('reference-form').addEventListener('submit',event=>{
      event.preventDefault();hooks.run(async()=>{
        const snapshot=hooks.state().project;
        const reference={name:find('reference-name').value,cues:find('reference-cues').value};
        const data=await this.prepare(find('reference-file').files[0]);
        if(hooks.state().project?.id!==snapshot.id || hooks.state().project.revision!==snapshot.revision)throw new Error('Property changed. Add the image again.');
        // run() already owns the busy state; release it before shared Preview.
        return {action:'reference_add',reference:{...reference,image:data}};
      }).then(command=>{if(command)hooks.preview([command]);});
    });
    find('reference-save').addEventListener('click',()=>{
      const id=find('reference-list').value;if(id)hooks.preview([{action:'reference_update',id,reference:{name:find('reference-name').value,cues:find('reference-cues').value}}]);
    });
    find('reference-remove').addEventListener('click',()=>{
      const id=find('reference-list').value;if(id)hooks.preview([{action:'reference_remove',id}]);
    });
  }
  selected() {return this.find('reference-use').checked && this.items.some(r=>r.id===this.find('reference-list').value)?[this.find('reference-list').value]:[];}
  show() {
    const item=this.items.find(r=>r.id===this.find('reference-list').value),pic=this.find('reference-image');
    pic.hidden=!item;
    if(item) {pic.src='data:'+item.mime+';base64,'+item.data;pic.alt=item.name;this.find('reference-name').value=item.name;this.find('reference-cues').value=item.cues;}
    else {pic.removeAttribute('src');this.find('reference-name').value='Reference';this.find('reference-cues').value='';this.find('reference-use').checked=false;}
  }
  render(project) {
    if(this.projectId===project?.id && this.revision===project?.revision)return;
    if(this.projectId!==project?.id)this.find('reference-use').checked=false;
    this.projectId=project?.id;this.revision=project?.revision;this.items=project?.scene.references||[];
    const select=this.find('reference-list'),previous=select.value;
    select.replaceChildren(...this.items.map(r=>new Option(r.name,r.id)));
    if(this.items.some(r=>r.id===previous))select.value=previous;
    this.find('reference-file').value='';this.show();
  }
  sync(disabled) {
    for(const control of this.find('reference-board').querySelectorAll('input,textarea,select,button'))control.disabled=disabled;
    for(const id of ['reference-save','reference-remove','reference-use'])this.find(id).disabled=disabled||!this.items.length;
  }
}
