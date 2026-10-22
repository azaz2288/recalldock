// Historical snapshots are immutable; every response is still scoped to the open view.
(() => {
  const dialog=document.createElement('dialog');dialog.id='version-dialog';
  dialog.setAttribute?.('aria-labelledby','version-title');
  dialog.innerHTML='<h2 id="version-title">文档版本历史</h2><div id="version-list"></div><div id="version-content"></div><div class="row document-pagination"><button class="btn secondary" id="version-prev">上一页旧版原文</button><span id="version-page" role="status"></span><button class="btn secondary" id="version-next">下一页旧版原文</button></div><button class="btn secondary" id="version-close">关闭</button>';
  document.body.append(dialog);
  const list=$('#version-list'),content=$('#version-content'),status=$('#version-page');
  const previous=$('#version-prev'),next=$('#version-next');
  let generation=0,current=null;
  function clearPage(){content.replaceChildren();status.textContent='';previous.disabled=true;next.disabled=true;}
  function invalidate(){generation++;current=null;list.replaceChildren();clearPage();$('#version-title').textContent='文档版本历史';}
  function close(){invalidate();if(dialog.open)dialog.close();}
  function active(view,token){return current===view&&token===generation&&selectedBase===view.kb&&dialog.open;}
  async function load(version,offset){
    if(!current)return;
    const view=current,token=++generation;view.version=version;clearPage();status.textContent='正在读取旧版原文…';
    try{
      const data=await api(`/ingest/documents/${encodeURIComponent(view.id)}/versions/${version}/page?kb_id=${encodeURIComponent(view.kb)}&offset=${offset}&limit=20`);
      if(!active(view,token))return;
      if(data.document.id!==view.id||data.document.kb_id!==view.kb||data.document.version!==version)
        throw new Error('旧版原文来源不匹配，请关闭并重新打开');
      view.offset=data.offset;view.next=data.next_offset;
      $('#version-title').textContent=`${data.document.name} · 历史版本 ${version}`;
      content.innerHTML=data.items.map(c=>`<article><span class="badge">第 ${c.page} 页 · 片段 ${c.idx+1}</span><pre class="answer">${esc(c.text)}</pre></article>`).join('')||empty('此版本没有片段','');
      content.scrollTop=0;
      status.textContent=`版本 ${version} · 共 ${data.total} 个片段 · ${data.items.length?data.offset+1:0}–${data.offset+data.items.length}`;
      previous.disabled=view.offset===0;next.disabled=view.next===null;
    }catch(error){if(active(view,token)){status.textContent='读取未完成，请重新选择版本或关闭';toast(error.message,true);}}
  }
  async function open(id){
    invalidate();const view={id,kb:selectedBase,version:null,offset:0,next:null};current=view;
    if(!dialog.open)dialog.showModal();const token=++generation;status.textContent='正在读取版本列表…';
    try{
      const data=await api(`/ingest/documents/${encodeURIComponent(id)}/versions`);
      if(!active(view,token))return;
      list.innerHTML=data.map(v=>`<button class="btn secondary inspect-version-page" data-version="${Number(v.version)}">查看历史版本 ${Number(v.version)}</button>`).join('')||empty('还没有旧版本','更新文档后保留旧版原文');
      status.textContent=`共 ${data.length} 个历史版本；请选择版本`;
    }catch(error){if(active(view,token)){status.textContent='版本列表读取未完成，请关闭重试';toast(error.message,true);}}
  }
  list.addEventListener('click',event=>{
    const button=event.target.closest('.inspect-version-page');if(!button||!current)return;
    const version=Number(button.dataset.version);if(Number.isSafeInteger(version)&&version>=1)return load(version,0);
  });
  previous.onclick=()=>current&&current.version!==null&&load(current.version,Math.max(0,current.offset-20));
  next.onclick=()=>current&&current.version!==null&&current.next!==null&&load(current.version,current.next);
  $('#version-close').onclick=close;
  dialog.addEventListener('cancel',invalidate);
  dialog.addEventListener('close',()=>{if(!dialog.open)invalidate();});
  $('#kb-select').addEventListener('change',close);
  // Startup requests can render rows before this script loads, or complete after it loads.
  // Delegate instead of relying on a subsequent wrapped refresh to bind each button.
  document.addEventListener('click',event=>{
    const button=event.target.closest('.history-document');if(button)return open(button.dataset.id);
  });
  const beforeHistoryRefresh=refresh;
  refresh=async()=>{close();await beforeHistoryRefresh();};
})();
