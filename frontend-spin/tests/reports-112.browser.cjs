/* Offline: rzeczywiste komponenty i CSS, API wyłącznie z lokalnego mocka. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const webpackModule = require('next/dist/compiled/webpack/webpack'); webpackModule.init();
const { webpack } = webpackModule;
const { chromium } = require('C:/Users/User/AppData/Local/npm-cache/_npx/e41f203b7505f1fb/node_modules/playwright');
const root = path.resolve(__dirname, '../..');
const temp = path.join(root, '.pytest-tmp/112');
const evidence = path.join(root, 'artifacts/112');
const ui = path.join(root, 'packages/ui/src');
fs.mkdirSync(temp, {recursive:true}); fs.mkdirSync(evidence, {recursive:true});
fs.writeFileSync(path.join(temp,'link.tsx'), `import React from 'react';export default function Link({href,children,prefetch,scroll,replace,...props}:any){return <a href={href} {...props}>{children}</a>}`);
fs.writeFileSync(path.join(temp,'navigation.ts'), `export const usePathname=()=>'/dla-redakcji';export const useRouter=()=>({push(){},replace(){},refresh(){}});export const useSearchParams=()=>new URLSearchParams();`);
fs.writeFileSync(path.join(temp,'entry.tsx'), `import React from 'react';import {createRoot} from 'react-dom/client';import {PressDocument} from ${JSON.stringify(path.join(root,'frontend-spin/lib/documents/PressDocument'))};createRoot(document.getElementById('root')!).render(<PressDocument/>);`);
const camp = {count:4,weighted_spin_percent:62.5,average_intensity:35};
const sample = {available:true,start:'2026-10-05',week_end:'2026-10-11',total:8,camps:{government:camp,opposition:camp},scope:'Próbka obejmuje liczby zbiorcze za pełny tydzień. Pełny raport zawiera zestawienie technik, trendy klubów i linki do analiz. Próbka nie zawiera listy wypowiedzi ani pełnych tabel.'};
let scenario='empty';
async function main(){
  await new Promise((resolve,reject)=>webpack({mode:'development',devtool:false,entry:path.join(temp,'entry.tsx'),output:{path:temp,filename:'bundle.js'},
    resolve:{extensions:['.tsx','.ts','.js','.json'],modules:[path.join(root,'frontend-spin/node_modules'),'node_modules'],alias:{'next/link$':path.join(temp,'link.tsx'),'next/navigation$':path.join(temp,'navigation.ts'),'@spin-clinic/ui$':path.join(ui,'index.ts'),'@spin-clinic/ui/kit$':path.join(ui,'kit/index.ts')}},
    module:{rules:[{test:/\.(tsx?|css)$/,use:path.join(__dirname,'corrections.loader.cjs')}]},
    plugins:[new webpack.DefinePlugin({'process.env':JSON.stringify({NODE_ENV:'development'})})]
  },(error,stats)=>error||stats.hasErrors()?reject(error||new Error(stats.toString({all:false,errors:true}))):resolve()));
  let css=fs.readFileSync(path.join(root,'frontend-spin/app/globals.css'),'utf8')+'\n'+fs.readFileSync(path.join(ui,'kit/kit.css'),'utf8');
  const font=fs.readFileSync(path.join(root,'backend/news/assets/fonts/Montserrat[wght].ttf')).toString('base64');
  css+=`\n@font-face{font-family:Montserrat;src:url(data:font/ttf;base64,${font}) format('truetype');font-weight:100 900}*{box-sizing:border-box}body{margin:0;background:var(--sc-bg);color:var(--sc-text);font-family:var(--sc-font-sans)}.mock-header{height:64px;padding:16px 24px;border-bottom:1px solid var(--sc-line)}main{padding:24px;max-width:1200px;margin:auto}@media(max-width:640px){main{padding:20px 16px}}`;
  const server=http.createServer((req,res)=>{
    if(req.url.startsWith('/api/')) {res.setHeader('Content-Type','application/json');if(scenario==='error'){res.statusCode=503;res.end('{}');return;}const send=()=>res.end(JSON.stringify(scenario==='available'?sample:{available:false,reason:'no_approved_report',next_report_at:'2026-10-12T06:40:00+02:00'}));if(scenario==='loading')setTimeout(send,4000);else send();return;}
    if(req.url==='/bundle.js'){res.setHeader('Content-Type','text/javascript');res.end(fs.readFileSync(path.join(temp,'bundle.js')));return;}
    res.setHeader('Content-Type','text/html; charset=utf-8');res.end(`<!doctype html><html lang="pl" data-theme="dark"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>${css}</style></head><body><header class="mock-header">spin.clinic · lokalny podgląd testowy</header><main id="root"></main><script src="/bundle.js"></script></body></html>`);
  });
  await new Promise(resolve=>server.listen(8112,'127.0.0.1',resolve));
  const browser=await chromium.launch({headless:true,executablePath:'C:/Users/User/AppData/Local/ms-playwright/chromium-1134/chrome-win/chrome.exe',args:['--window-position=-32000,-32000','--window-size=1,1']});
  const errors=[],measurements=[];
  try{
    for(const width of [1440,390]){
      const page=await browser.newPage({viewport:{width,height:900},locale:'pl-PL',reducedMotion:'reduce'});
      page.on('pageerror',e=>errors.push(e.message));
      await page.route('**/*',r=>new URL(r.request().url()).hostname==='127.0.0.1'?r.continue():r.abort());
      for(const state of ['loading','empty','available','error']){
        scenario=state;await page.goto('http://127.0.0.1:8112/dla-redakcji');
        await page.getByRole('heading',{name:'Bezpłatna próbka',exact:true}).waitFor();
        if(state==='empty')await page.getByText('Próbka raportu pojawi się po najbliższym raporcie tygodniowym.',{exact:true}).waitFor();
        if(state==='available')await page.getByRole('heading',{name:'Rządzący',exact:true}).waitFor();
        if(state==='error')await page.getByText(/Nie udało się wczytać próbki/).waitFor();
        await page.evaluate(()=>document.fonts.ready);
        const measures=await page.evaluate(()=>{const rect=e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,height:r.height}};return {overflow:document.documentElement.scrollWidth>innerWidth,cards:[...document.querySelectorAll('.sc-rep-box')].map(e=>({...rect(e),title:rect(e.querySelector('h3')),footer:rect(e.querySelector('.sc-rep-box__foot'))})),cta:rect(document.querySelector('.sc-rep-contact .sc-btn')),sample:rect(document.querySelector('.sc-rep-sample')),gridGap:getComputedStyle(document.querySelector('.sc-rep-grid')).gap,menuGap:document.querySelector('.sc-doc-layout').getBoundingClientRect().top-document.querySelector('header').getBoundingClientRect().bottom}});
        assert(!measures.overflow,`${width}/${state} overflow`);assert(measures.cta.height>=44);assert.equal(await page.locator('.sc-press-page a[data-variant="primary"]').count(),1);assert.equal(await page.locator('#pilotaz').count(),0);
        assert.equal(measures.cards[0].height,measures.cards[1].height);
        measurements.push({width,state,...measures});
        await page.screenshot({path:path.join(evidence,`${state}-${width}.png`),fullPage:true});
      }
      assert.equal(new Set(measurements.filter(m=>m.width===width).map(m=>m.cta.top)).size,1,'CTA musi stać w tym samym miejscu we wszystkich stanach');
      await page.close();
    }
    assert.deepEqual(errors,[]);fs.writeFileSync(path.join(evidence,'measurements.json'),JSON.stringify(measurements,null,2));
    console.log('OK: 8 zrzutów, 4 stany, 1440/390, równe karty, jeden CTA, bez overflow i błędów JS.');
    scenario='empty';
    if(process.argv.includes('--serve')){console.log('Mock HTTP: http://127.0.0.1:8112/dla-redakcji');await browser.close();return;}
  }finally{if(!process.argv.includes('--serve')){await browser.close();server.close();}}
}
main().catch(e=>{console.error(e);process.exit(1)});
