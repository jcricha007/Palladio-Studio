// Mirrors geometry.py so the browser and native projection share finish geometry.
export function surfaceTriangles(item, materialColor) {
  const [w,h,d]=item.size, appearance=item.finish || {}, result=[];
  const emit=(points,source)=>{
    let base=source && (appearance.source_colors ?? !item.finish) ? source : appearance.color || materialColor;
    let shade=1;
    const pattern=appearance.pattern||'solid';
    if(pattern!=='solid') {
      const centre=[0,1,2].map(i=>points.reduce((sum,p)=>sum+p[i],0)/3);
      const [a,b,c]=points,u0=b.map((x,i)=>x-a[i]),v0=c.map((x,i)=>x-a[i]);
      const normal=[u0[1]*v0[2]-u0[2]*v0[1],u0[2]*v0[0]-u0[0]*v0[2],u0[0]*v0[1]-u0[1]*v0[0]];
      let axis=0;for(let i=1;i<3;i++)if(Math.abs(normal[i])>Math.abs(normal[axis]))axis=i;
      let [u,v]=axis===0?[centre[2],centre[1]]:axis===1?[centre[0],centre[2]]:[centre[0],centre[1]];
      const angle=(appearance.rotation||0)*Math.PI/180;
      [u,v]=[u*Math.cos(angle)-v*Math.sin(angle),u*Math.sin(angle)+v*Math.cos(angle)];const scale=appearance.scale_m||.25;
      if(pattern==='wood'){const phase=(u+.02*Math.sin(v*7))/scale;shade=.72+.28*Math.round((Math.sin(phase*2*Math.PI)*.5+.5)*7)/7;}
      else if(pattern==='stone')shade=.65+.35*((Math.floor(u/scale)*73856093 ^ Math.floor(v/scale)*19349663)&7)/7;
      else {
        const row=Math.floor(v/scale*(pattern==='brick'?2:1)),x=u/scale+(pattern==='brick'?((row%2+2)%2)*.5:0),y=v/scale*(pattern==='brick'?2:1);
        const grout=Math.min(x-Math.floor(x),1-(x-Math.floor(x)),y-Math.floor(y),1-(y-Math.floor(y)))<.07;
        if(grout)base=appearance.accent_color||'#c8c1b7';else if(pattern==='brick')shade=.88+.12*((Math.floor(x)^row)&3)/3;
      }
    }
    const color=[1,3,5].map(i=>Math.round(parseInt(base.slice(i,i+2),16)*shade)/255);
    result.push({points,color});
  };
  if(item.mesh) {
    const points=item.mesh.vertices.map(p=>[p[0]*w,p[1]*h,p[2]*d]);
    for(let i=0;i<item.mesh.triangles.length;i+=3) emit(item.mesh.triangles.slice(i,i+3).map(j=>points[j]),item.mesh.colors?.[i/3]);
  } else {
    const corners=[[-w/2,0,-d/2],[w/2,0,-d/2],[w/2,0,d/2],[-w/2,0,d/2],[-w/2,h,-d/2],[w/2,h,-d/2],[w/2,h,d/2],[-w/2,h,d/2]];
    const n=appearance.pattern==='wood'?8:(appearance.pattern||'solid')!=='solid'?16:1;
    for(const [ia,ib,ic,id] of [[0,1,2,3],[4,7,6,5],[0,4,5,1],[1,5,6,2],[2,6,7,3],[3,7,4,0]]) {
      const a=corners[ia],b=corners[ib],d=corners[id];
      const at=(u,v)=>a.map((x,i)=>x+(b[i]-x)*u+(d[i]-x)*v);
      for(let row=0;row<n;row++)for(let col=0;col<n;col++) {
        const p=at(col/n,row/n),q=at((col+1)/n,row/n),r=at((col+1)/n,(row+1)/n),s=at(col/n,(row+1)/n);
        emit([p,q,r]);emit([p,r,s]);
      }
    }
  }
  return result;
}
