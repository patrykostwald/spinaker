const { chromium } = require('./109-playwright.cjs');
const fs = require('node:fs');
const path = require('node:path');
const fixture = require('./109-fixture.cjs');
const assert = require('node:assert/strict');
const rgb = s => s.match(/[\d.]+/g).slice(0,3).map(Number);
const luminance = c => c.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
(async()=>{
 const b=await chromium.launch({});
 try {
 const p=await b.newPage({viewport:{width:390,height:900},reducedMotion:'reduce'});
 await p.route('**/*',r=>{const u=new URL(r.request().url());return !['localhost','127.0.0.1'].includes(u.hostname)?r.abort():u.pathname.startsWith('/api/')?r.fulfill({json:fixture.response(u.pathname)}):r.continue();});
 await p.goto('http://127.0.0.1:3009');await p.locator('.sc-overview-diagnosis').first().waitFor();
 const samples=await p.evaluate(()=>{
  const selectors=['.sc-overview-intro h1','.sc-overview-kicker','.sc-overview-excerpt','.sc-overview-diagnosis:nth-child(1) b','.sc-overview-diagnosis:nth-child(2) b','.sc-overview-diagnosis:nth-child(3) b','.sc-overview-actions a:last-child','.sc-newsletter button','.sc-newsletter__consent','.sc-shell-mobile a'];
  return selectors.map(selector=>{const e=document.querySelector(selector);const s=getComputedStyle(e);let n=e,bg;while(n){bg=getComputedStyle(n).backgroundColor;if(bg!=='rgba(0, 0, 0, 0)')break;n=n.parentElement;}return {selector,color:s.color,background:bg||'rgb(0, 0, 0)'};});
 });
 const result=samples.map(s=>{const a=luminance(rgb(s.color)),b=luminance(rgb(s.background));return {...s,ratio:+((Math.max(a,b)+.05)/(Math.min(a,b)+.05)).toFixed(2)}});
 fs.writeFileSync(path.resolve(__dirname,'../../artifacts/109/contrast.json'),JSON.stringify(result,null,2));
 assert.ok(result.every(s=>s.ratio>=4.5),JSON.stringify(result.filter(s=>s.ratio<4.5)));
 console.log('PASS: sampled text/background contrast >=4.5:1; minimum',Math.min(...result.map(s=>s.ratio)));
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
