const fs=require('fs');
const path=require('path');
const {createHash}=require('crypto');
const {pathToFileURL}=require('url');
const {chromium}=require(process.env.BOOK_PLAYWRIGHT||'playwright');
const {calculate}=require('./sources/calculator.js');
const root=path.resolve(__dirname,'..');
const url=pathToFileURL(path.join(__dirname,'index.html')).href;
function assert(value,message){if(!value)throw Error(message);}
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.BOOK_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],external=[],states=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});
 await page.goto(url);
 const data=await page.locator('#book-data').textContent();
 for(const chapter of JSON.parse(data)){
   await page.goto(url+'#'+chapter.id);
   await page.waitForTimeout(60);
   assert(await page.locator('[id="'+chapter.id+'"]').isVisible(),'chapter hidden '+chapter.id);
 }
 const ids=await page.locator('.deep-sketch').evaluateAll(els=>els.map(el=>el.id));
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1000});
  for(const chapter of JSON.parse(data)){
   await page.goto(url+'#'+chapter.id);
   await page.waitForTimeout(40);
   for(const picture of await page.locator('[id="'+chapter.id+'"] img').all()){
    await picture.scrollIntoViewIfNeeded();
    await picture.evaluate(el=>el.complete?Promise.resolve():new Promise(resolve=>{el.onload=resolve;el.onerror=resolve;}));
   }
   const images=await page.locator('[id="'+chapter.id+'"] img').evaluateAll(xs=>xs.map(x=>({ok:x.complete&&x.naturalWidth>0,src:x.getAttribute('src')})));
   assert(images.every(x=>x.ok),'image missing '+JSON.stringify(images));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'chapter overflow '+chapter.id+' '+width);
  }
  await page.goto(url+'#cache-failover');
  const lab=page.locator('.replication-lab');
  for(const scenario of ['loss','delivered','timeout']){
   await lab.locator('[data-scenario]').selectOption(scenario);
   for(let i=0;i<7;i++){
    assert((await lab.locator('[data-counter]').innerText()).includes('Шаг '+(i+1)+' из 7'),'replication step');
    assert((await lab.locator('[data-replication-state]').innerText()).length>80,'replication explanation');
    if(i<6)await lab.locator('[data-forward]').click();
   }
  }
  await lab.locator('svg').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(root,'checks/cache-replication-'+width+'.png')});
  await page.goto(url+'#35-time-model');
  const ttl=page.locator('[data-ttl-lab]');
  await ttl.locator('#ttl-freshness').fill('1');await ttl.locator('#ttl-background').fill('0');
  assert((await ttl.locator('output').innerText()).includes('Совместимого TTL нет.'),'TTL impossible interval');
  assert((await ttl.locator('output').innerText()).includes('1,75'),'TTL lower bound');
  await ttl.locator('#ttl-freshness').fill('2');
  assert((await ttl.locator('output').innerText()).includes('Совместимый диапазон существует.'),'TTL possible interval');
  await ttl.locator('#ttl-background').fill('2500');
  assert((await ttl.locator('output').innerText()).includes('Совместимого TTL нет.'),'TTL background consumes budget');
  await ttl.locator('#ttl-background').fill('0');await ttl.locator('#ttl-freshness').fill('1');
  await ttl.locator('.resource-chart').scrollIntoViewIfNeeded();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'TTL page overflow');
  await page.screenshot({path:path.join(root,'checks/cache-ttl-'+width+'.png')});
  await page.goto(url+'#30-mc-operation');
  const slab=page.locator('[data-slab-lab]');
  await slab.locator('#slab-pages').fill('1');
  assert((await slab.locator('output').innerText()).includes('не помещается: 1'),'slab capacity limit');
  await slab.locator('#slab-pages').fill('2');
  assert((await slab.locator('output').innerText()).includes('не помещается: 0'),'slab added page');
  await slab.locator('#slab-pages').fill('1');await slab.locator('.slab-pages').scrollIntoViewIfNeeded();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'slab page overflow');
  await page.screenshot({path:path.join(root,'checks/cache-slabs-'+width+'.png')});
 }
 await page.goto(url+'#33-eviction');
 const trainer=page.locator('.eviction-trainer');
 await trainer.locator('[data-policy]').selectOption('FIFO');
 await trainer.locator('[data-recalculate]').click();
 for(let i=0;i<4;i++)await trainer.locator('[data-next]').click();
 assert((await trainer.locator('[data-explanation]').innerText()).includes('После: B · C · D'),'FIFO evicted original insertion');
 await trainer.locator('[data-capacity]').fill('0');await trainer.locator('[data-recalculate]').click();
 assert((await trainer.locator('[data-error]').innerText()).length>10,'invalid capacity');
 await trainer.locator('[data-capacity]').fill('3');await trainer.locator('[data-recalculate]').click();
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1000});
  for(const id of ids){
   await page.goto(url+'#'+id);await page.waitForTimeout(90);
   const sketch=page.locator('#'+id),buttons=sketch.locator('.ds-steps button');
   assert(await buttons.count()===6,'step count '+id);
   for(let i=0;i<6;i++){
    await buttons.nth(i).click();
    assert((await sketch.locator('[data-ds-count]').innerText()).includes(String(i+1)+' из 6'),'step failed');
    const geometry=await page.evaluate(id=>{
      const el=document.getElementById(id),svg=el.querySelector('svg');
      return {width:innerWidth,scroll:document.documentElement.scrollWidth,svgWidth:svg.getBoundingClientRect().width,box:svg.getAttribute('viewBox')};
    },id);
    assert(geometry.scroll<=width,'page overflow '+id+' '+width);
    states.push({id,width,step:i+1,geometry});
   }
   const band=sketch.locator('.ds-bands button').first();
   await band.click();assert((await sketch.locator('.ds-band-detail').innerText()).length>10,'band detail');
  }
 }
 await page.setViewportSize({width:1440,height:1000});
 await page.goto(url+'#02-economics');
 assert((await page.locator('.cache-calculator output').innerText()).includes('1,02'),'calculator baseline');
 await page.locator('#calc-hit').fill('80');
 assert((await page.locator('.cache-calculator output').innerText()).includes('превышен'),'calculator budget');
 await page.locator('#calc-hit').fill('101');
 assert((await page.locator('.cache-calculator output').innerText()).includes('от 0 до 100'),'calculator invalid input');
 await page.locator('#calc-hit').fill('95');
 await page.locator('#calc-background').fill('4000');
 assert((await page.locator('.cache-calculator output').innerText()).includes('100% попаданий недостаточно'),'impossible budget');
 assert(calculate({rate:0,hit:100,cache:0,source:8,fill:0,background:0,budget:0}).within,'zero flow');
 assert(calculate({rate:1,hit:101,cache:0,source:8,fill:0,background:0,budget:0})===null,'out of bounds');
 await page.goto(url+'#07-redis');
 await page.locator('#dictionary-open').click();
 await page.locator('#term-search').fill('redis-cli');await page.waitForTimeout(70);
 assert((await page.locator('#terms').innerText()).includes('Клиент Redis'),'new command reference');
 assert((await page.locator('#terms').innerText()).includes('Браузерная модель её не исполняет'),'server simulator boundary');
 await page.keyboard.press('Escape');
 await page.locator('#dictionary-open').click();await page.locator('#term-search').fill('grep -E');
 assert((await page.locator('#terms').innerText()).includes('grep'),'Bash command reference');
 await page.keyboard.press('Escape');
 await page.locator('#search').fill('stampede');await page.waitForTimeout(220);
 assert((await page.locator('#search-results').innerText()).length>10,'full text search');
 await page.locator('#search').fill('');
 await page.goto(url+'#04-patterns');
 await page.locator('#note-04-patterns').fill('Проверить защитную версию');
 await page.locator('[id="04-patterns"] .read-toggle').click();await page.waitForTimeout(450);
 await page.reload();
 assert(await page.locator('#note-04-patterns').inputValue()==='Проверить защитную версию','notes persistence');
 await page.goto(url+'#cache-race');
 await page.locator('#cache-race .ds-steps button').nth(4).click();
 await page.locator('#cache-race').scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(root,'checks/cache-desktop.png')});
 await page.locator('#theme').click();
 await page.screenshot({path:path.join(root,'checks/cache-dark.png')});
 await page.setViewportSize({width:390,height:844});
 await page.waitForTimeout(250);
 assert(await page.locator('#side-nav').evaluate(el=>el.getBoundingClientRect().right<=1),'mobile sidebar hidden after transition');
 await page.locator('#menu').click();await page.waitForTimeout(200);
 assert(await page.locator('#side-nav').evaluate(el=>el.getBoundingClientRect().left>=-1),'mobile menu opens');
 await page.locator('#nav-04-patterns').click();await page.waitForTimeout(200);
 await page.locator('#cache-race').scrollIntoViewIfNeeded();
 await page.evaluate(()=>scrollTo({top:document.getElementById('cache-race').getBoundingClientRect().top+scrollY-130,behavior:'instant'}));
 await page.screenshot({path:path.join(root,'checks/cache-mobile.png')});
 await page.emulateMedia({media:'print'});
 await page.evaluate(()=>window.dispatchEvent(new Event('beforeprint')));
 assert(await page.locator('.chapter:visible').count()===JSON.parse(data).length,'print all chapters');
 await page.emulateMedia({media:'screen'});await page.evaluate(()=>window.dispatchEvent(new Event('afterprint')));
 await page.setViewportSize({width:1440,height:1000});
 await page.goto(pathToFileURL(path.join(root,'bash/index.html')).href);
 await page.locator('#dictionary-open').click();
 await page.locator('#term-search').fill('Cache stampede');await page.waitForTimeout(90);
 assert((await page.locator('#terms').innerText()).includes('Cache stampede'),'cross-volume glossary');
 const href=await page.locator('#terms a[href*="cache/index.html"]').first().getAttribute('href');
 assert(href.includes('glossary-term-'),'cross-volume anchor');
 assert(errors.length===0,'browser errors: '+errors.join('; '));
 assert(external.length===0,'external active requests');
 fs.writeFileSync(path.join(root,'checks/cache-browser.json'),JSON.stringify({status:'PASS',book_sha256:createHash('sha256').update(fs.readFileSync(path.join(__dirname,'index.html'))).digest('hex'),chapters:JSON.parse(data).length,diagramStates:states.length,states,errors,external,checks:['file://','navigation','mobile','dark theme','diagrams','calculator','commands','shared glossary','notes','print','illustrations','replication scenarios','eviction trainer','TTL budget','slab budget']},null,2)+'\n');
 console.log(JSON.stringify({status:'PASS',chapters:JSON.parse(data).length,states:states.length,errors}));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
