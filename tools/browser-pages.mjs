// Optional actual Chromium regression against tools/pages_demo.py (synthetic only).
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
  const context=await browser.newContext({viewport:{width:1280,height:900}});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
  await page.goto('http://127.0.0.1:8899/');
  const original=page.locator('.view-document').first();await original.waitFor();await original.click();
  await page.locator('#document-page').filter({hasText:'1–20'}).waitFor();
  assert.equal(await page.locator('#document-prev').isDisabled(),true);
  await page.locator('#document-next').click();
  await page.locator('#document-page').filter({hasText:'21–40'}).waitFor();
  await page.locator('#document-next').click();
  await page.locator('#document-page').filter({hasText:'41–56'}).waitFor();
  assert.equal(await page.locator('#document-next').isDisabled(),true);
  assert.match(await page.locator('#document-content').textContent(),/TAIL-ORIGINAL-120/);
  await page.locator('#document-prev').click();
  await page.locator('#document-page').filter({hasText:'21–40'}).waitFor();
  await page.locator('#document-close').click();await original.click();
  await page.locator('#document-page').filter({hasText:'1–20'}).waitFor();
  await page.setViewportSize({width:390,height:844});
  await page.locator('#document-next').click();
  await page.locator('#document-page').filter({hasText:'21–40'}).waitFor();
  const layout=await page.evaluate(()=>({viewport:innerWidth,body:document.body.scrollWidth,
    dialogWidth:document.querySelector('#document-dialog').getBoundingClientRect().width,
    dialogScroll:document.querySelector('#document-dialog').scrollWidth,
    dialogClient:document.querySelector('#document-dialog').clientWidth}));
  assert.ok(layout.body<=layout.viewport,JSON.stringify(layout));
  assert.ok(layout.dialogScroll<=layout.dialogClient,JSON.stringify(layout));
  if(process.argv[2])await page.screenshot({path:process.argv[2],fullPage:false});
  await page.locator('#document-close').click();
  const options=await page.locator('#kb-select option').evaluateAll(nodes=>nodes.map(n=>({value:n.value,text:n.textContent})));
  const other=options.find(o=>o.text.includes('合成空库'));assert.ok(other);
  await page.locator('#kb-select').selectOption(other.value);
  await page.locator('#recent-docs .empty').waitFor();
  assert.equal(await page.locator('#document-dialog').evaluate(d=>d.open),false);
  assert.equal(await page.locator('#document-content').textContent(),'');
  await page.locator('#kb-select').selectOption('default');await original.waitFor();await original.click();
  await page.locator('#document-page').filter({hasText:'1–20'}).waitFor();
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({synthetic:true,chunks:56,pages:'20+20+16',tail:true,reopen:true,kbSwitch:true,layout,errors}));
  await context.close();
}finally{await browser.close();}
