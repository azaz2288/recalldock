// Current-document pages: never render a response from a closed/changed view.
(() => {
  const dialog=$('#document-dialog');
  const controls=document.createElement('div');controls.className='row document-pagination';
  controls.innerHTML='<button class="btn secondary" id="document-prev">上一页原文</button><span id="document-page" role="status"></span><button class="btn secondary" id="document-next">下一页原文</button><button class="btn secondary" id="document-restart">重新读取当前版本</button>';
  $('#document-content').after(controls);
  let generation=0,current=null;
  const previous=$('#document-prev'),next=$('#document-next'),status=$('#document-page');
  function invalidate(){generation++;current=null;$('#document-content').replaceChildren();status.textContent='';previous.disabled=true;next.disabled=true;}
  function close(){invalidate();if(dialog.open)dialog.close();}
  async function load(offset){
    if(!current)return;
    const view=current,requestGeneration=++generation;
    previous.disabled=true;next.disabled=true;status.textContent='正在读取原文…';
    $('#document-content').replaceChildren();
    let route=`/documents/${encodeURIComponent(view.id)}/chunks/page?kb_id=${encodeURIComponent(view.kb)}&offset=${offset}&limit=20`;
    if(view.version!==null)route+=`&expected_version=${view.version}`;
    const active=()=>current===view&&requestGeneration===generation&&selectedBase===view.kb&&dialog.open;
    try{
      const data=await api(route);
      if(!active())return;
      if(data.document.id!==view.id||data.document.kb_id!==view.kb||
         (view.version!==null&&data.document.version!==view.version))throw new Error('原文来源已变化，请重新读取');
      view.version=data.document.version;view.offset=data.offset;view.next=data.next_offset;
      $('#document-title').textContent=data.document.name;
      $('#document-content').innerHTML=data.items.map(c=>`<article><span class="badge">第 ${c.page} 页 · 片段 ${c.idx+1}</span><pre>${esc(c.text)}</pre></article>`).join('')||empty('没有更多片段','可以重新读取当前版本。');
      $('#document-content').scrollTop=0;
      status.textContent=`版本 ${view.version} · 共 ${data.total} 个片段 · ${data.items.length?data.offset+1:0}–${data.offset+data.items.length}`;
      previous.disabled=view.offset===0;next.disabled=view.next===null;
    }catch(error){
      if(!active())return;
      status.textContent='读取未完成，请重新读取当前版本或关闭';
      toast(error.message,true);
    }
  }
  async function open(id){
    invalidate();current={id,kb:selectedBase,version:null,offset:0,next:null};
    $('#document-title').textContent='当前原文';if(!dialog.open)dialog.showModal();await load(0);
  }
  previous.onclick=()=>current&&load(Math.max(0,current.offset-20));
  next.onclick=()=>current&&current.next!==null&&load(current.next);
  $('#document-restart').onclick=()=>current&&open(current.id);
  $('#document-close').onclick=close;
  dialog.addEventListener('cancel',invalidate);
  // Native close events are queued: an earlier close must not invalidate a reopened view.
  dialog.addEventListener('close',()=>{if(!dialog.open)invalidate();});
  $('#kb-select').addEventListener('change',close);
  const beforePagesRefresh=refresh;
  refresh=async()=>{
    close();await beforePagesRefresh();
    $$('.view-document').forEach(button=>button.onclick=()=>open(button.dataset.id));
  };
})();
