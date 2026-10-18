// Optional browser integration test. Requires Playwright and Chromium.
const {spawn}=require('node:child_process');
const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const root=path.resolve(__dirname,'..');
async function main(){
 const server=spawn(process.env.PYTHON||'python3',['-u','play.py','--no-browser','--no-save'],{cwd:root});
 let browser;
 try{
  const address=await new Promise((resolve,reject)=>{let buffer='';const timer=setTimeout(()=>reject(Error('Server startup timeout')),20000);server.stdout.on('data',s=>{buffer+=s;const m=buffer.match(/http:\/\/127\.0\.0\.1:\d+\//);if(m){clearTimeout(timer);resolve(m[0])}});server.stderr.on('data',s=>process.stderr.write(s));server.once('exit',n=>{clearTimeout(timer);reject(Error('Server exited: '+n))})});
  browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--no-zygote','--single-process']});
  const page=await browser.newPage({viewport:{width:1160,height:960}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(address);
  await page.getByRole('button',{name:'e2, белые, пешка',exact:true}).click();
  await page.getByRole('button',{name:'e4, пусто',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#history').textContent.includes('Nf6'));
  await page.screenshot({path:path.join(root,'test-results/board-desktop.png'),fullPage:true});
  console.log('PASS human move + native response:',await page.locator('#history').textContent());
  const pgn=await (await page.request.get(address+'game.pgn')).text();
  if(!pgn.includes('e4 Nf6'))throw Error('PGN missing moves');
  await page.locator('#undo').click();
  await page.waitForFunction(()=>document.querySelector('#history').textContent==='Ходов пока нет.');
  await page.locator('#settings summary').click();
  await page.locator('#side').selectOption('black');await page.locator('#new').click();
  await page.waitForFunction(()=>document.querySelector('#history').textContent.includes('Nc3'));
  console.log('PASS undo + black game:',await page.locator('#history').textContent());
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.join(root,'test-results/board-mobile.png'),fullPage:true});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow');
  if(errors.length)throw Error(errors.join('\n'));
  console.log('PASS desktop/mobile, PGN download, no page errors');
 }finally{if(browser)await browser.close();server.kill('SIGTERM')}
}
main().catch(e=>{console.error(e);process.exitCode=1});
