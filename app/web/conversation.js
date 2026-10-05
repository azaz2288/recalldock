const conversationOptions=document.createElement('div');conversationOptions.className='row small muted';
conversationOptions.innerHTML='<label><input type="checkbox" id="continue-question"> 继续上一问</label><label><input type="checkbox" id="stream-answer" checked> 流式显示（生成中尚未校验）</label>';
$('#question-form').append(conversationOptions);
let activeParent='',previewFingerprint='';
let answerController=null;
const stopAnswer=document.createElement('button');stopAnswer.type='button';stopAnswer.className='btn secondary hidden';stopAnswer.textContent='停止生成';$('#ask').before(stopAnswer);
stopAnswer.onclick=()=>answerController?.abort();
const queryApi=api;
api=async(path,options={})=>{
  if(['/ask','/preview'].includes(path)&&typeof options.body==='string'){
    const body=JSON.parse(options.body);
    if(path==='/ask'&&!body.use_ai){activeParent=$('#continue-question').checked?(lastMessage||''):'';previewFingerprint='';}
    body.parent_id=activeParent;if(body.use_ai)body.context_fingerprint=previewFingerprint;
    options={...options,body:JSON.stringify(body)};
    if(path==='/ask'&&$('#stream-answer').checked){
      body.kb_id=selectedBase;body.semantic=$('#use-semantic').checked;
      answerController=new AbortController();stopAnswer.classList.remove('hidden');$('#kb-select').disabled=true;$('#ask').disabled=true;
      if($('#preview-dialog').open)$('#preview-dialog').close();
      $('#sources').innerHTML='';$('#ai-open').classList.add('hidden');lastMessage=null;lastSources=[];
      try{
      const response=await fetch('/api/ask-stream',{...options,body:JSON.stringify(body),signal:answerController.signal});
      if(!response.ok){const error=await response.json();throw Error(error.detail||'问答失败');}
      const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',doneResult=null,answer='';$('#answer').textContent='';
      while(true){
        const chunk=await reader.read();if(chunk.done)break;
        buffer+=decoder.decode(chunk.value,{stream:true});let end;
        while((end=buffer.indexOf('\n\n'))>=0){
          const block=buffer.slice(0,end);buffer=buffer.slice(end+2);
          const event=block.split('\n').find(l=>l.startsWith('event:'))?.slice(6).trim();
          const value=JSON.parse(block.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trim()).join('\n'));
          if(event==='text'){answer+=value;$('#answer').textContent=answer;$('#answer-mode').textContent='生成中 · 尚未校验';}
          if(event==='done')doneResult=value;
          if(event==='error'){$('#answer').textContent='回答未通过校验或连接中断，请重试。';throw Error(value.detail);}
        }
      }
      if(!doneResult)throw Error('回答流中断，没有保存未完成内容');return doneResult;
      }catch(error){$('#answer').textContent=error.name==='AbortError'?'生成已停止，当前内容未确认为有效回答。':'回答未完成或校验失败，请重试。';$('#answer-mode').textContent='未完成';lastMessage=null;lastSources=[];throw error.name==='AbortError'?new Error('已停止生成'):error;}
      finally{answerController=null;stopAnswer.classList.add('hidden');$('#kb-select').disabled=false;$('#ask').disabled=false;}
    }
  }
  const result=await queryApi(path,options);if(path==='/preview')previewFingerprint=result.context_fingerprint;return result;
};
$('#kb-select').addEventListener('change',()=>{lastMessage=null;activeParent='';previewFingerprint='';$('#continue-question').checked=false;});
