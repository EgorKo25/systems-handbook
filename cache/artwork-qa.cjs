const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const {chromium}=require(process.env.BOOK_PLAYWRIGHT||'playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.BOOK_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 try{
  const p=await browser.newPage({viewport:{width:1100,height:650}}),bounds=[];
  for(const name of fs.readdirSync(path.join(__dirname,'assets')).filter(x=>x.endsWith('.svg'))){
   await p.goto(pathToFileURL(path.join(__dirname,'assets',name)).href);
   const overflow=await p.locator('svg text').evaluateAll(xs=>xs.map(x=>({text:x.textContent,b:x.getBBox()})).filter(x=>x.b.x<0||x.b.x+x.b.width>1100||x.b.y+x.b.height>650).map(x=>x.text));
   if(overflow.length)throw Error(name+': '+overflow.join('; '));
   bounds.push(name);
   await p.screenshot({path:path.join(__dirname,'../checks/cache-art-'+name+'.png')});
  }
  await p.setViewportSize({width:1440,height:1000});
  await p.goto(pathToFileURL(path.join(__dirname,'index.html')).href+'#cache-failover');
  await p.locator('.replication-lab [data-scenario]').selectOption('loss');
  for(let i=0;i<5;i++)await p.locator('.replication-lab [data-forward]').click();
  await p.locator('.replication-lab svg').scrollIntoViewIfNeeded();
  await p.screenshot({path:path.join(__dirname,'../checks/cache-replication-detail.png')});
  fs.writeFileSync(path.join(__dirname,'../checks/cache-artwork.json'),JSON.stringify({status:'PASS',assets:bounds},null,2)+'\n');
  console.log('PASS '+bounds.length+' SVG bounds');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
