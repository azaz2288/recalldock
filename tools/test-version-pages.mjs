// Run the shipped historical-view controller under deterministic response ordering.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../app/web/version-pages.js',import.meta.url),'utf8');
function harness(){
  const elements=new Map(),pending=[],closed=[],errors=[];
  function element(id){
    if(!elements.has(id))elements.set(id,{id,textContent:'',innerHTML:'',disabled:false,open:false,dataset:{},events:{},
      append(){},replaceChildren(){this.innerHTML='';},addEventListener(name,fn){this.events[name]=fn;},
      showModal(){this.open=true;},close(){this.open=false;closed.push(()=>this.events.close?.());}});
    return elements.get(id);
  }
  const buttons=['a','b'].map(id=>({...element('version-button-'+id),dataset:{id}}));
  const documentEvents={};
  const context=vm.createContext({document:{body:{append(){}},createElement:()=>element('version-dialog'),
    addEventListener:(name,fn)=>documentEvents[name]=fn},
    $:s=>element(s.slice(1)),$$:()=>buttons,selectedBase:'default',refresh:async()=>{},
    encodeURIComponent,esc:v=>String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'),
    empty:()=>'<empty>',toast:message=>errors.push(message),
    api:route=>new Promise((resolve,reject)=>pending.push({route,resolve,reject}))});
  vm.runInContext(source,context);
  const page=(id='a',version=1,offset=0,total=57,kb='default')=>({document:{id,kb_id:kb,name:'synthetic <title>',version},
    items:Array.from({length:Math.min(20,Math.max(0,total-offset))},(_,i)=>({page:1,idx:offset+i,text:`<history ${offset+i}>`})),
    total,offset,limit:20,next_offset:offset+20<total?offset+20:null});
  return {element,pending,context,closed,errors,page,ready:()=>context.refresh(),
    open:id=>documentEvents.click({target:{closest:()=>buttons.find(b=>b.dataset.id===id)}}),click:id=>element(id).onclick(),
    choose:version=>element('version-list').events.click({target:{closest:()=>({dataset:{version:String(version)}})}})};
}
async function start(h,id='a'){
  await h.ready();const action=h.open(id);h.pending.at(-1).resolve([{version:2},{version:1}]);await action;
}
test('history paginates all 57 chunks and uses immutable selected version',async()=>{
  const h=harness();await start(h);let action=h.choose(1);assert.match(h.pending[1].route,/versions\/1\/page\?kb_id=default&offset=0&limit=20/);
  h.pending[1].resolve(h.page());await action;assert.match(h.element('version-page').textContent,/1–20/);
  action=h.click('version-next');h.pending[2].resolve(h.page('a',1,20));await action;
  action=h.click('version-next');h.pending[3].resolve(h.page('a',1,40));await action;
  assert.match(h.element('version-content').innerHTML,/history 56/);assert.equal(h.element('version-next').disabled,true);
  action=h.click('version-prev');h.pending[4].resolve(h.page('a',1,20));await action;
  assert.match(h.element('version-page').textContent,/21–40/);
});
test('late old version never replaces newly selected version and text is escaped',async()=>{
  const h=harness();await start(h);const first=h.choose(1),second=h.choose(2);
  h.pending[2].resolve(h.page('a',2));await second;h.pending[1].resolve(h.page());await first;
  assert.match(h.element('version-page').textContent,/版本 2/);
  assert.match(h.element('version-content').innerHTML,/&lt;history/);assert.doesNotMatch(h.element('version-content').innerHTML,/<history/);
  assert.equal(h.element('version-title').textContent,'synthetic <title> · 历史版本 2');
});
test('close, Escape and knowledge-base change discard late page and list responses',async()=>{
  for(const phase of ['list','page'])for(const mode of ['close','cancel','change']){
    const h=harness();await h.ready();let action=h.open('a');
    if(phase==='page'){h.pending[0].resolve([{version:1}]);await action;action=h.choose(1);}
    if(mode==='close')h.click('version-close');
    if(mode==='cancel'){h.element('version-dialog').events.cancel();h.element('version-dialog').open=false;}
    if(mode==='change'){h.context.selectedBase='other';h.element('kb-select').events.change();}
    h.pending.at(-1).resolve(phase==='page'?h.page():[{version:1}]);await action;
    assert.equal(h.element('version-content').innerHTML,'');assert.equal(h.element('version-list').innerHTML,'');
  }
});
test('queued close event cannot clear a reopened history dialog',async()=>{
  const h=harness();await start(h);h.click('version-close');const action=h.open('b');
  for(const fn of h.closed)fn();h.pending[1].resolve([{version:1}]);await action;
  const page=h.choose(1);h.pending[2].resolve(h.page('b'));await page;
  assert.match(h.element('version-page').textContent,/1–20/);
});
test('revoked permission and wrong metadata fail closed without keeping old text',async()=>{
  for(const errorMode of ['revoke','metadata']){
    const h=harness();await start(h);let action=h.choose(1);h.pending[1].resolve(h.page());await action;
    action=h.click('version-next');assert.equal(h.element('version-content').innerHTML,'');
    if(errorMode==='revoke')h.pending[2].reject(new Error('没有知识库访问权限'));
    else h.pending[2].resolve(h.page('b',1,20));await action;
    assert.equal(h.errors.length,1);assert.equal(h.element('version-next').disabled,true);
    assert.equal(h.element('version-prev').disabled,true);
  }
});
test('out-of-order document lists cannot replace newer document and empty versions stay empty',async()=>{
  const h=harness();await h.ready();const a=h.open('a'),b=h.open('b');
  h.pending[1].resolve([]);await b;h.pending[0].resolve([{version:1}]);await a;
  assert.equal(h.element('version-next').disabled,true);assert.doesNotMatch(h.element('version-list').innerHTML,/data-version/);
  assert.equal(h.element('version-content').innerHTML,'');
});

test('buttons rendered before or after controller installation work without an extra refresh',async()=>{
  const h=harness();const action=h.open('a');h.pending[0].resolve([{version:1}]);await action;
  const view=h.choose(1);h.pending[1].resolve(h.page());await view;
  assert.match(h.element('version-page').textContent,/1–20/);
});
