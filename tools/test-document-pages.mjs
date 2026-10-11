// Exercise the shipped handlers with controlled response ordering, not a copied model.
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const source=readFileSync(new URL('../app/web/document-pages.js',import.meta.url),'utf8');
function harness(){
  const elements=new Map(),pending=[],errors=[],closed=[];
  function element(id){
    if(!elements.has(id))elements.set(id,{id,textContent:'',innerHTML:'',disabled:false,open:false,events:{},dataset:{},
      replaceChildren(){this.innerHTML='';},after(){},addEventListener(name,fn){this.events[name]=fn;},
      showModal(){this.open=true;},close(){this.open=false;closed.push(()=>this.events.close?.());}});
    return elements.get(id);
  }
  const buttons=['a','b'].map(id=>({...element('button-'+id),dataset:{id}}));
  const context=vm.createContext({document:{createElement:()=>element('controls')},
    $:s=>element(s.slice(1)),$$:()=>buttons,selectedBase:'default',refresh:async()=>{},
    esc:v=>String(v).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;'),
    empty:()=>'<empty>',toast:(message)=>errors.push(message),encodeURIComponent,
    api:route=>new Promise((resolve,reject)=>pending.push({route,resolve,reject}))});
  vm.runInContext(source,context);
  const page=(id='a',offset=0,total=57,version=1,kb='default')=>({document:{id,name:'synthetic <title>',version,kb_id:kb},
    items:Array.from({length:Math.min(20,Math.max(0,total-offset))},(_,i)=>({idx:offset+i,page:1,text:`<body ${offset+i}>`})),
    total,offset,limit:20,next_offset:offset+20<total?offset+20:null});
  return {element,context,pending,buttons,errors,closed,page,async ready(){await context.refresh();},
    open:id=>buttons.find(b=>b.dataset.id===id).onclick(),click:id=>element(id).onclick()};
}
test('all 57 pieces can be paged with version guard, previous and explicit restart',async()=>{
  const h=harness();await h.ready();let action=h.open('a');h.pending[0].resolve(h.page());await action;
  assert.match(h.element('document-page').textContent,/1–20/);assert.equal(h.element('document-prev').disabled,true);
  action=h.click('document-next');assert.match(h.pending[1].route,/offset=20.*expected_version=1/);
  h.pending[1].resolve(h.page('a',20));await action;
  action=h.click('document-next');h.pending[2].resolve(h.page('a',40));await action;
  assert.match(h.element('document-content').innerHTML,/body 56/);assert.equal(h.element('document-next').disabled,true);
  assert.match(h.element('document-page').textContent,/41–57/);
  action=h.click('document-prev');h.pending[3].resolve(h.page('a',20));await action;
  assert.match(h.element('document-page').textContent,/21–40/);
  action=h.click('document-restart');assert.doesNotMatch(h.pending[4].route,/expected_version/);
  h.pending[4].resolve(h.page('a',0,0,2));await action;
  assert.match(h.element('document-page').textContent,/共 0.*0–0/);assert.equal(h.element('document-next').disabled,true);
});
test('late response for A cannot overwrite B, and text is escaped',async()=>{
  const h=harness();await h.ready();const a=h.open('a'),b=h.open('b');
  h.pending[1].resolve(h.page('b'));await b;h.pending[0].resolve(h.page());await a;
  assert.match(h.element('document-content').innerHTML,/&lt;body/);
  assert.doesNotMatch(h.element('document-content').innerHTML,/<body/);
  assert.equal(h.element('document-title').textContent,'synthetic <title>');
  assert.match(h.pending[1].route,/documents\/b\//);
});
test('close and knowledge-base change discard in-flight content',async()=>{
  for(const mode of ['close','change','cancel']){
    const h=harness();await h.ready();const action=h.open('a');
    if(mode==='close')h.click('document-close');
    else if(mode==='change'){h.context.selectedBase='other';h.element('kb-select').events.change();}
    else {h.element('document-dialog').events.cancel();h.element('document-dialog').open=false;}
    h.pending[0].resolve(h.page());await action;assert.equal(h.element('document-content').innerHTML,'');
  }
});
test('queued native close event does not invalidate a reopened view',async()=>{
  const h=harness();await h.ready();let action=h.open('a');h.pending[0].resolve(h.page());await action;
  h.click('document-close');action=h.open('b');for(const callback of h.closed)callback();
  h.pending[1].resolve(h.page('b'));await action;assert.match(h.element('document-page').textContent,/1–20/);
});
test('revision conflict clears the old page and requires explicit reload',async()=>{
  const h=harness();await h.ready();let action=h.open('a');h.pending[0].resolve(h.page());await action;
  action=h.click('document-next');assert.equal(h.element('document-content').innerHTML,'');
  h.pending[1].reject(new Error('文档版本已变化'));await action;
  assert.equal(h.element('document-next').disabled,true);assert.equal(h.element('document-prev').disabled,true);
  assert.deepEqual(h.errors,['文档版本已变化']);action=h.click('document-restart');
  h.pending[2].resolve(h.page('a',0,1,2));await action;assert.match(h.element('document-page').textContent,/版本 2/);
});
test('out-of-order page loads and unexpected metadata cannot render',async()=>{
  const h=harness();await h.ready();let action=h.open('a');h.pending[0].resolve(h.page());await action;
  const first=h.click('document-next'),second=h.click('document-next');
  h.pending[2].resolve(h.page('a',20));await second;h.pending[1].resolve(h.page('a',0));await first;
  assert.match(h.element('document-page').textContent,/21–40/);
  for(const wrong of [h.page('b',40),h.page('a',40,57,2),h.page('a',40,57,1,'other')]){
    action=h.click('document-restart'); // restart permits a new version, but never another document/base
    if(wrong.document.version===2){h.pending.at(-1).resolve(h.page());await action;action=h.click('document-next');}
    h.pending.at(-1).resolve(wrong);await action;assert.equal(h.element('document-content').innerHTML,'');
  }
  assert.equal(h.errors.length,3);
});
