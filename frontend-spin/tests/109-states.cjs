const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const fixture = require('./109-fixture.cjs');
const output = path.resolve(__dirname, '../../artifacts/109');
(async () => {
 const browser = await chromium.launch({ headless:true, executablePath:'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe', args:['--window-position=-32000,-32000','--window-size=1,1'] });
 const results = [];
 try {
 for (const width of [1440,390,900]) {
  let scenario = 'normal', newsletter = 'error';
  const page = await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce',serviceWorkers:'block'});
  const errors = []; page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url = new URL(route.request().url());
   if (!['localhost','127.0.0.1'].includes(url.hostname)) return route.abort();
   if (!url.pathname.startsWith('/api/')) return route.continue();
   if (url.pathname === '/api/clinic/') {
    if (scenario==='loading') await new Promise(r=>setTimeout(r,2500));
    if (scenario==='error') return route.fulfill({status:503,json:{}});
    if (scenario==='empty') return route.fulfill({json:{...fixture.page, columns:{government:[],opposition:[]}, messages:{government:null,opposition:null}, interview:null, stats:undefined}});
   }
   if (url.pathname.includes('/newsletter/') && newsletter==='error') return route.fulfill({status:503,json:{detail:'Test: spróbuj ponownie.'}});
   return route.fulfill({json:fixture.response(url.pathname)});
  });
  await page.goto('http://127.0.0.1:3009');
  await page.locator('.sc-overview-diagnosis').first().waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);
  const geometry = await page.evaluate(()=>{
   const rect=e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height}};
   const parts=[...document.querySelector('.sc-overview').children].filter(e=>e.getBoundingClientRect().height>0);
   const colors=['--sc-text','--sc-text-2','--sc-accent','--sc-positive','--sc-negative'].map(token=>{
    const el=document.createElement('span');el.style.color=`var(${token})`;document.body.append(el);const color=getComputedStyle(el).color;el.remove();return {token,color};
   });
   return {sections:parts.map(e=>({name:e.id||e.className,...rect(e)})), gaps:parts.slice(1).map((e,i)=>rect(e).top-rect(parts[i]).bottom), colors,
    targets:[...document.querySelectorAll('.sc-overview a:not(.sc-newsletter__trap),.sc-overview button,.sc-shell-mobile a,.sc-shell-header a')].filter(e=>e.getBoundingClientRect().height>0).map(e=>({text:e.textContent,...rect(e)})),
    consent:rect(document.querySelector('.sc-newsletter__consent')),
    reduced:[...document.querySelectorAll('.sc-overview-metrics dl>div')].map(e=>getComputedStyle(e).animationName),
   };
  });
  assert.ok(geometry.targets.every(t=>t.height>=44), JSON.stringify(geometry.targets.filter(t=>t.height<44)));
  assert.ok(geometry.reduced.every(v=>v==='none'));
  await page.locator('a[href="#alerty"]').click();
  await page.getByLabel('Adres e-mail',{exact:true}).fill('test@example.invalid');
  await page.getByRole('button',{name:'Powiadom mnie o starcie'}).click();
  await page.getByRole('alert').filter({hasText:'Zaznacz zgodę'}).waitFor();
  await page.locator('.sc-newsletter input[type=checkbox]').check();
  await page.getByRole('button',{name:'Powiadom mnie o starcie'}).click();
  await page.getByRole('alert').filter({hasText:'Test: spróbuj'}).waitFor();
  newsletter='success';
  await page.getByRole('button',{name:'Powiadom mnie o starcie'}).click();
  await page.getByRole('status').filter({hasText:'Sprawdź skrzynkę'}).waitFor();
  if(width!==900) await page.screenshot({path:path.join(output,`success-${width}.png`),fullPage:true});
  await page.goto('http://127.0.0.1:3009/klinika');
  await page.locator('.sc-overview-details summary').click();
  await page.locator('.sc-ind-show__day').first().waitFor();
  const chart = await page.evaluate(()=>({labels:[...document.querySelectorAll('.sc-ind-show__tiles li > span')].map(e=>e.getBoundingClientRect().bottom),dates:[...document.querySelectorAll('.sc-ind-show__day time')].map(e=>e.getBoundingClientRect().bottom)}));
  if(width!==900) await page.screenshot({path:path.join(output,`expanded-${width}.png`),fullPage:true});
  await page.goto('http://127.0.0.1:3009');
  await page.locator('.sc-overview-diagnosis').first().waitFor();
  const last=page.locator('.sc-shell-footer > a').last(); await last.focus();
  const focus=await last.evaluate(e=>({bottom:e.getBoundingClientRect().bottom,viewport:innerHeight,outline:getComputedStyle(e).outlineStyle}));
  assert.equal(focus.outline,'solid');
  assert.ok(focus.bottom<=900-(width===390?64:0),'focus hidden by bottom nav');
  if(width!==900) {
   scenario='empty'; await page.reload(); await page.getByText('Pierwsze diagnozy pojawią się po publikacji analiz.').waitFor();
   await page.screenshot({path:path.join(output,`empty-${width}.png`),fullPage:true});
   scenario='error'; await page.reload(); await page.getByRole('button',{name:'Spróbuj ponownie',exact:true}).waitFor({timeout:30000});
   await page.screenshot({path:path.join(output,`error-${width}.png`),fullPage:true});
   scenario='normal'; await page.getByRole('button',{name:'Spróbuj ponownie',exact:true}).click(); await page.locator('.sc-overview-diagnosis').first().waitFor();
   scenario='loading'; await page.reload({waitUntil:'domcontentloaded'}); await page.getByText('Wczytujemy najnowsze analizy…').waitFor();
   await page.screenshot({path:path.join(output,`loading-${width}.png`),fullPage:true});
  }
  assert.deepEqual(errors,[]);
  results.push({width,geometry,chart,focus});
  fs.writeFileSync(path.join(output,'states-measurements.json'),JSON.stringify(results,null,2));
  await page.close();
 }
 console.log('PASS: newsletter consent/error/success, data empty/error/retry/loading, expanded clinic, focus, 44px targets, reduced motion, 900px overflow.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
