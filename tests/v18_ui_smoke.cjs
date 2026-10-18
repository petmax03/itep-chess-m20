const {spawn}=require('node:child_process'),path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..');
(async()=>{
 const server=spawn('python3',['-u','play.py','--no-browser','--no-save'],{cwd:root});let browser;
 try{
  const address=await new Promise((res,rej)=>{let buffer='';let t=setTimeout(()=>rej(Error('startup timeout')),15000);server.stdout.on('data',s=>{buffer+=s;let m=buffer.match(/http:\/\/127\.0\.0\.1:\d+\//);if(m){clearTimeout(t);res(m[0])}});server.stderr.on('data',s=>process.stderr.write(s));});
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:1280,height:1000}});let errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(address);await page.waitForFunction(()=>document.querySelector('#status').textContent==='Ваш ход.');
  await page.locator('#calculation-settings summary').click();
  for(const d of ['5','4','3']){
   await page.locator('#depth').selectOption(d);await page.locator('#apply-budget').click();
   await page.waitForFunction(d=>document.querySelector('#settings-result').textContent.includes('глубина '+d),d);
   const s=await(await page.request.get(address+'api/state')).json();if(s.depth!==+d)throw Error('wrong depth');
   if(s.budget!==({'3':3e9,'4':1e10,'5':2e10}[d]))throw Error('wrong budget');
  }
  await page.locator('#depth').selectOption('5');await page.locator('#apply-budget').click();
  await page.waitForFunction(()=>document.querySelector('#settings-result').textContent.includes('глубина 5'));
  await page.screenshot({path:path.join(root,'test-results/v18/desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(root,'test-results/v18/mobile.png'),fullPage:true});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('overflow');
  await page.locator('#depth').selectOption('3');await page.locator('#apply-budget').click();
  await page.waitForFunction(()=>document.querySelector('#settings-result').textContent.includes('глубина 3'));
  await page.locator('#move-input').fill('e4');await page.locator('#send').click();
  await page.waitForFunction(()=>document.querySelectorAll('.history-move').length===2);
  const pgn=await(await page.request.get(address+'game.pgn')).text();
  if(!pgn.includes('[SearchDepth "3"]')||!pgn.includes('[%m20_depth 3]'))throw Error('PGN depth absent');
  if(errors.length)throw Error(errors.join('\n'));
  console.log('PASS: depth selectors 3/4/5, budgets, desktop/mobile, legal answer, PGN, no JS errors');
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1});
