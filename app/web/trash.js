// Deletion becomes recoverable, without executing archive content or model calls.
const trashButton=document.createElement('button');
trashButton.className='btn secondary';trashButton.id='trash-open';trashButton.textContent='文档回收站';
$('#all-docs').before(trashButton);
const trashDialog=document.createElement('dialog');trashDialog.id='trash-dialog';
trashDialog.setAttribute('aria-label','文档回收站');
trashDialog.innerHTML='<div class="row"><h2>文档回收站</h2><span class="spacer"></span><button class="btn secondary" id="trash-close">关闭回收站</button></div><p class="small muted">移入的文档不参与新的检索，正文与索引保留，恢复后可用。历史问答已保存的来源不会删除；这里不是安全擦除，也不会自动清空。</p><div id="trash-items"></div><div class="row"><button class="btn secondary" id="trash-prev">上一页</button><span id="trash-page" role="status"></span><button class="btn secondary" id="trash-next">下一页</button></div>';
document.body.append(trashDialog);
let trashOffset=0,trashTotal=0,trashGeneration=0;
function clearCurrentEvidence(){
  lastSources=[];lastMessage=null;lastQuestion='';activeParent='';previewFingerprint='';
  $('#sources').innerHTML='';$('#ai-open').classList.add('hidden');
  $('#answer').textContent='文档状态已变化，请重新检索。';$('#answer-mode').textContent='需要重新检索';
  $('#continue-question').checked=false;
}
function availableLifecycle(){if(answerController){toast('请先停止或完成当前生成，再修改文档状态',true);return false;}return true;}
const beforeTrashRefresh=refresh;
refresh=async()=>{
  await beforeTrashRefresh();
  $$('.delete-document').forEach(button=>{
    button.textContent='移入回收站';
    button.onclick=guard(async()=>{
      if(!availableLifecycle())return;
      button.disabled=true;
      try{await api('/documents/'+encodeURIComponent(button.dataset.id),{method:'DELETE'});clearCurrentEvidence();toast('已移入回收站，可恢复');await refresh();}
      finally{button.disabled=false;}
    });
  });
};
async function loadTrash(){
  const kb=selectedBase,generation=++trashGeneration;
  const data=await api(`/trash?kb_id=${encodeURIComponent(kb)}&offset=${trashOffset}&limit=20`);
  if(kb!==selectedBase||generation!==trashGeneration)return;
  trashTotal=data.total;
  if(trashOffset>=trashTotal&&trashOffset>0){trashOffset=Math.max(0,Math.floor((trashTotal-1)/20)*20);return loadTrash();}
  $('#trash-items').innerHTML=data.items.length?data.items.map(d=>`<article class="row" style="padding:12px 0"><div><strong>${esc(d.name)}</strong><p class="small muted">版本 ${d.version} · 移入时间 ${esc(new Date(d.deleted_at*1000).toLocaleString())}</p></div><span class="spacer"></span><button class="btn secondary restore-document" data-id="${esc(d.id)}">恢复文档</button></article>`).join(''):empty('回收站为空','活动文档的移入操作可在这里恢复。');
  $('#trash-page').textContent=`共 ${trashTotal} 份 · ${trashTotal?trashOffset+1:0}–${Math.min(trashOffset+20,trashTotal)}`;
  $('#trash-prev').disabled=trashOffset===0;$('#trash-next').disabled=trashOffset+20>=trashTotal;
  $$('.restore-document').forEach(button=>button.onclick=guard(async()=>{
    if(!availableLifecycle())return;
    button.disabled=true;
    try{await post('/trash/'+encodeURIComponent(button.dataset.id)+'/restore',{});clearCurrentEvidence();toast('文档已恢复，可重新检索');await refresh();await loadTrash();}
    finally{button.disabled=false;}
  }));
}
trashButton.onclick=guard(async()=>{const kb=selectedBase;trashOffset=0;await loadTrash();if(kb===selectedBase)trashDialog.showModal();});
$('#trash-close').onclick=()=>trashDialog.close();
$('#trash-prev').onclick=guard(async()=>{trashOffset=Math.max(0,trashOffset-20);await loadTrash();});
$('#trash-next').onclick=guard(async()=>{trashOffset+=20;await loadTrash();});
$('#kb-select').addEventListener('change',()=>{trashGeneration++;trashDialog.close();$('#trash-items').replaceChildren();});
