// Mirrors geometry.py so the browser and native projection share finish geometry.
export function surfaceTriangles(item, materialColor) {
  const [w,h,d]=item.size, appearance=item.finish || {}, result=[];
  const emit=(points,source)=>{
    const base=source && (appearance.source_colors ?? !item.finish) ? source : appearance.color || materialColor;
    let shade=1;
    if(appearance.pattern==='wood') {
      const centre=[0,1,2].map(i=>points.reduce((sum,p)=>sum+p[i],0)/3);
      const angle=(appearance.rotation||0)*Math.PI/180;
      const phase=(centre[0]*Math.cos(angle)+centre[2]*Math.sin(angle)+.02*Math.sin(centre[1]*7))/(appearance.scale_m||.25);
      shade=.72+.28*Math.round((Math.sin(phase*2*Math.PI)*.5+.5)*7)/7;
    }
    const color=[1,3,5].map(i=>Math.round(parseInt(base.slice(i,i+2),16)*shade)/255);
    result.push({points,color});
  };
  if(item.mesh) {
    const points=item.mesh.vertices.map(p=>[p[0]*w,p[1]*h,p[2]*d]);
    for(let i=0;i<item.mesh.triangles.length;i+=3) emit(item.mesh.triangles.slice(i,i+3).map(j=>points[j]),item.mesh.colors?.[i/3]);
  } else {
    const corners=[[-w/2,0,-d/2],[w/2,0,-d/2],[w/2,0,d/2],[-w/2,0,d/2],[-w/2,h,-d/2],[w/2,h,-d/2],[w/2,h,d/2],[-w/2,h,d/2]];
    const n=appearance.pattern==='wood'?8:1;
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
