/* Scale only the sandboxed HTML preview. Source data and exported files stay untouched. */
const PreviewZoomUI=(()=>{
  let frame,control,output,label,fitOption,documentRef,scheduled=false;
  let mode='fit';
  function update(){
    if(!control)return;
    label.textContent=uiText('Zoom HTML','HTML zoom','Zoom HTML');
    fitOption.textContent=uiText('Ajustar al ancho','Fit width','Ajustar à largura');
    control.disabled=S.previewMode!=='live';
    control.title=uiText('El PDF tiene sus propios controles de visualización.','PDF has its own viewer controls.','O PDF tem seus próprios controles de visualização.');
    if(control.disabled)output.textContent='';
  }
  function apply(){
    scheduled=false;
    const doc=documentRef;
    if(!doc||doc!==frame?.contentDocument||S.previewMode!=='live'||!frame.getClientRects().length)return;
    const body=doc.body,cover=doc.querySelector('.cover');
    if(!body||!cover)return;
    // Measure the authored paper width without deriving it from the narrow
    // iframe. Width and zoom are preview-local inline properties only.
    const oldZoom=parseFloat(body.style.zoom)||1;
    const paperWidth=cover.getBoundingClientRect().width/oldZoom;
    if(!Number.isFinite(paperWidth)||paperWidth<=0)return;
    const style=doc.defaultView.getComputedStyle(body);
    const margins=(parseFloat(style.marginLeft)||0)+(parseFloat(style.marginRight)||0);
    body.style.width=paperWidth+'px';
    const width=doc.documentElement.clientWidth;
    if(width<=1)return;
    const zoom=mode==='fit'?Math.min(1,(width-1)/(paperWidth+margins)):Number(mode)/100;
    body.style.zoom=String(zoom);
    output.textContent=Math.round(zoom*100)+'%';
    frame.dataset.previewZoomMode=mode;
    frame.dataset.previewZoom=String(zoom);
  }
  function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame(apply);}}
  function ready(doc){
    documentRef=doc;update();apply();
    doc.fonts?.ready.then(()=>{if(documentRef===doc)schedule();});
    for(const image of doc.images)if(!image.complete)image.addEventListener('load',schedule,{once:true});
  }
  function bind(){
    frame=$('#pdfPreview');
    label=h('span',{});fitOption=h('option',{value:'fit'});
    control=h('select',{id:'previewZoom'},fitOption,...[50,75,100,125,150,200].map(value=>h('option',{value:String(value)},value+'%')));
    output=h('output',{'aria-hidden':'true'});
    control.addEventListener('change',()=>{mode=control.value;apply();});
    $('.preview-head').append(h('label',{class:'preview-zoom'},label,control,output));
    new ResizeObserver(schedule).observe(frame);
    window.addEventListener('resize',schedule);update();
  }
  return {bind,ready,update};
})();
