/* Real React components, local fixture responses only. No server or external network. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const webpackModule = require('next/dist/compiled/webpack/webpack');
webpackModule.init();
const { webpack } = webpackModule;
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(__dirname, '../..');
const temp = path.join(root, '.pytest-tmp/087-browser');
const output = path.join(root, 'reports/087-layout');
fs.mkdirSync(temp, { recursive: true }); fs.mkdirSync(output, { recursive: true });
const ui = path.join(root, 'packages/ui/src');
fs.writeFileSync(path.join(temp, 'link.tsx'), `import React from 'react'; export default function Link({href,children,prefetch,scroll,replace,...props}:any){return <a href={href} {...props}>{children}</a>}`);
fs.writeFileSync(path.join(temp, 'navigation.ts'), `export const usePathname=()=>'/nitki/85'; export const useRouter=()=>({push(){},replace(){},refresh(){}}); export const useSearchParams=()=>new URLSearchParams();`);
const fixture = {id:85,title:'Jak zmiana kontekstu wpływa na odbiór wypowiedzi',author:'reader_x',display_name:'@reader_x',x_profile:'https://x.com/reader_x',is_ai:true,continues:84,continuations:[86],comments_count:1,
  opinions:{positive:8,doubt:3,negative:1},items_count:3,published_at:'2026-10-03T08:00:00Z',updated_at:'2026-10-03T08:00:00Z',description:'',
  preview:[0,1,2].map((n)=>({id:n+1,position:n,kind:'link',box_type:['post','claim','source'][n],title:['Punkt wyjścia: co naprawdę powiedział autor','Twierdzenie wymaga pełnego kontekstu','Źródło i dane do samodzielnego sprawdzenia'][n],url:'https://example.org/material',domain:'example.org',note:'Komentarz autora wyjaśnia, jak materiały łączą się ze sobą. '.repeat(9),x_handle:'autorka',source_name:'Autorka wpisu',diagnosis_id:23,intensity:72,published_date:'2026-10-03T08:00:00Z',body:'Warto przeczytać pełną wypowiedź i sprawdzić źródła.',link_note:n?'Porównanie wypowiedzi z dokumentem źródłowym.':''}))};
fs.writeFileSync(path.join(temp, 'entry.tsx'), `import React from 'react';import {createRoot} from 'react-dom/client';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import {ThreadStrip} from ${JSON.stringify(path.join(ui,'components/community/ThreadStrip'))};import {MojaNitkaEditor} from ${JSON.stringify(path.join(ui,'components/MojaNitkaEditor'))};import {AccountDialog} from ${JSON.stringify(path.join(ui,'components/AccountDialog'))};import {XAccountSettings} from ${JSON.stringify(path.join(ui,'components/XAccountSettings'))};import {SocialNavigation} from ${JSON.stringify(path.join(ui,'components/community/SocialNavigation'))};import {ThreadModerationPanel} from ${JSON.stringify(path.join(ui,'components/community/ThreadModerationPanel'))};const client=new QueryClient({defaultOptions:{queries:{retry:false}}});const votes=new URLSearchParams(location.search).get('votes');const thread=${JSON.stringify(fixture)};if(votes!==null)thread.opinions={positive:Math.min(2,Number(votes)),doubt:Math.max(0,Number(votes)-2),negative:0};createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><div className="sc-social-layout"><SocialNavigation/><main>{location.pathname.includes("editor")?<MojaNitkaEditor threadId={8}/>:location.pathname.includes("login")?<AccountDialog open onClose={()=>{}}/>:location.pathname.includes("settings")?<XAccountSettings/>:<><ThreadStrip thread={thread} full /><ThreadModerationPanel /></>}</main></div></QueryClientProvider>);`);

async function main() {
  await new Promise((resolve,reject)=>webpack({mode:'development',devtool:false,entry:path.join(temp,'entry.tsx'),output:{path:temp,filename:'bundle.js'},
    resolve:{extensions:['.tsx','.ts','.js','.json'],modules:[path.join(root,'frontend-spin/node_modules'),'node_modules'],alias:{'next/link$':path.join(temp,'link.tsx'),'next/navigation$':path.join(temp,'navigation.ts')}},
    module:{rules:[{test:/\.(tsx?|css)$/,use:path.join(__dirname,'corrections.loader.cjs')}]},
    plugins:[new webpack.DefinePlugin({'process.env':JSON.stringify({NODE_ENV:'development',NEXT_PUBLIC_APP_ENABLED:'true',NEXT_PUBLIC_THREADS_ENABLED:'true',NEXT_PUBLIC_ACCOUNTS_ENABLED:'true',NEXT_PUBLIC_API_URL:''})})]
  },(error,stats)=>error||stats.hasErrors()?reject(error||new Error(stats.toString({all:false,errors:true}))):resolve()));
  const bundle=fs.readFileSync(path.join(temp,'bundle.js'),'utf8');
  const font=fs.readFileSync(path.join(root,'backend/news/assets/fonts/Montserrat[wght].ttf')).toString('base64');
  const css=fs.readFileSync(path.join(ui,'kit/kit.css'),'utf8')+'\n*{box-sizing:border-box}body{margin:0;background:var(--sc-bg);color:var(--sc-text);font-family:var(--sc-font-sans)}main{max-width:1100px;width:100%;margin:auto;padding:16px}' + `@font-face{font-family:Montserrat;src:url(data:font/ttf;base64,${font}) format('truetype');font-weight:100 900}`;
  const browser=await chromium.launch({channel:'chrome',headless:true});
  const errors=[];
  try {
    for(const width of [320,390,1024,1440]) {
      const page=await browser.newPage({viewport:{width,height:1000},locale:'pl-PL',reducedMotion:width===320?'reduce':'no-preference'});
      page.on('pageerror',e=>{errors.push(e.message);console.error(e.message)});
      let counts={positive:8,doubt:3,negative:1},mine=null, reports=0, moderated=false;
      let comments=[{id:1,body:'Warto sprawdzić @boks 3. '+ 'Pełny dokument pozwala ocenić tę wypowiedź. '.repeat(10),author:'czytelnik',created_at:new Date().toISOString(),edited_at:null,is_owner:true,can_edit:true,reactions_count:0,reacted:false}];
      await page.addInitScript(()=>{window.shared=null;Object.defineProperty(navigator,'share',{value:async(data)=>{window.shared=data}})});
      await page.route('**/*',route=>{
        const url=new URL(route.request().url()),method=route.request().method(),pathname=url.pathname;
        if(pathname==='/bundle.js') return route.fulfill({contentType:'text/javascript',body:bundle});
        if(pathname==='/api/auth/csrf/') return route.fulfill({json:{csrfToken:'fixture'}});
        if(pathname==='/api/account/me/') return route.fulfill({json:{authenticated:true,user:{id:1,username:'czytelnik',email_verified:true},csrfToken:'fixture'}});
        if(pathname==='/api/account/notifications/')return route.fulfill({json:{results:[],unread:3}});
        if(pathname==='/api/community/moderation/'){if(method==='POST')moderated=true;return route.fulfill({json:{results:moderated?[]:[{id:1,thread_id:85,target_kind:'comment',reason:'spam',details:'Testowe zgłoszenie',snapshot:'Testowy komentarz',status:'new',ai:{state:'unavailable'},appeal:'',decisions:[]}],next_page:null,rules:{N4:'Spam'}}});}
        if(pathname==='/api/account/follows/') return route.fulfill({json:[]});
        if(pathname.endsWith('/opinions/')) {
          if(method!=='GET') {const data=route.request().postDataJSON();if(mine)counts[mine]--;mine=data.polarity;counts[mine]++;}
          return route.fulfill({json:{counts,mine:mine?{polarity:mine}:null}});
        }
        if(pathname.endsWith('/report/')) {reports++;return route.fulfill({status:201,json:{status:'received',id:1}})}
        if(pathname.endsWith('/reaction/')) {comments[0].reacted=method==='POST';comments[0].reactions_count=method==='POST'?1:0;return route.fulfill({json:comments[0]});}
        if(pathname.includes('/comments/')) {
          if(method==='POST')comments.push({id:comments.length+1,...route.request().postDataJSON(),author:'czytelnik',created_at:new Date().toISOString(),edited_at:null,is_owner:true,can_edit:true,reactions_count:0,reacted:false});
          if(method==='DELETE') {comments=comments.filter(c=>!pathname.endsWith(`/${c.id}/`));return route.fulfill({status:204})}
          if(method==='PATCH')comments=comments.map(c=>pathname.endsWith(`/${c.id}/`)?{...c,...route.request().postDataJSON(),edited_at:new Date().toISOString()}:c);
          return route.fulfill({json:{results:comments,next_cursor:null,count:comments.length}});
        }
        if(pathname==='/nitki/85')return route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="pl" data-theme="dark"><meta charset="utf-8"><style>${css}</style><div id="root"></div><script src="/bundle.js"></script></html>`});
        return route.abort();
      });
      await page.goto('https://offline.test/nitki/85');
      await page.getByText('czytelnik',{exact:true}).waitFor();
      await page.screenshot({path:path.join(output,`${width}-x-card.png`),fullPage:true});
      assert.equal(await page.locator('.sc-thread-totals').count(),1);
      assert.match(await page.locator('.sc-thread-totals').innerText(), /8.*3.*1.*1 komentarzy/);
      assert.equal(await page.getByRole('link',{name:'Ciąg dalszy →',exact:true}).getAttribute('href'),'/nitki/86');
      assert.equal(await page.getByRole('link',{name:'← Poprzednia część',exact:true}).getAttribute('href'),'/nitki/84');
      await page.getByRole('button',{name:'Trafne 0',exact:true}).click();
      await page.locator('.sc-comment-reaction[aria-pressed="true"]').waitFor();
      assert.equal(comments[0].reactions_count,1);
      await page.getByRole('button',{name:'Trafne 1',exact:true}).click();
      await page.locator('.sc-comment-reaction[aria-pressed="false"]').waitFor();
      await page.getByLabel('Kolejność komentarzy').selectOption('new');
      assert.equal(await page.getByLabel('Kolejność komentarzy').inputValue(),'new');
      assert.ok(await page.getByRole('link',{name:'Otwórz na X',exact:true}).count()>=1);
      assert.ok(await page.getByRole('link',{name:'Zbadane: siła spinu 72/100',exact:true}).count()>=1);
      await page.getByRole('button',{name:'Dodaj swój komentarz',exact:true}).click();
      assert.equal(await page.locator('.sc-social-frame__icon').count(),3);
      assert.equal(await page.locator('.sc-thread-social-actions').locator(':scope > button, :scope > span').count(),4);
      assert.equal(await page.locator('.sc-thread-strip__box .sc-social-frame').count(),0);
      await page.getByRole('button',{name:'Oceń',exact:true}).click();
      await page.locator('.sc-social-ratings').getByRole('button',{name:/Trafna/}).click();
      await page.locator('.sc-social-ratings').getByRole('button',{name:/Mam wątpliwości/}).click();
      await page.locator('.sc-social-ratings [data-rating="doubt"][aria-pressed="true"]').waitFor();
      assert.equal(mine,'doubt');
      await page.getByRole('button',{name:'@boks 3',exact:true}).click();
      await page.locator('[data-box="3"].is-highlighted').waitFor();
      assert.equal(await page.getByLabel('Pozycja w nitce').innerText(),'3/3');
      assert.ok(await page.locator('.sc-thread-strip__track').evaluate(el=>el.scrollWidth>el.clientWidth)||width>=1024);
      await page.getByRole('button',{name:'Odpowiedz do boksu',exact:true}).click();
      assert.match(await page.getByRole('textbox',{name:'Komentarz pod nitką',exact:true}).inputValue(),/@boks 3/);
      await page.getByRole('button',{name:'Dodaj komentarz',exact:true}).click();
      await page.getByText('Komentarz dodany.').waitFor();
      await page.getByRole('button',{name:'Edytuj',exact:true}).first().click();
      await page.getByRole('textbox',{name:'Edytuj komentarz',exact:true}).fill('Poprawiony komentarz @boks 1');
      await page.locator('.sc-social-comments form').getByRole('button',{name:'Zapisz',exact:true}).click();
      await page.getByText('Poprawiony komentarz',{exact:false}).waitFor();
      await page.getByRole('button',{name:'Usuń',exact:true}).last().click();
      await page.getByRole('button',{name:'Udostępnij',exact:true}).click();
      assert.equal(await page.evaluate(()=>window.shared.url),'https://offline.test/nitki/85');
      await page.locator('.sc-thread-strip__head').getByRole('button',{name:'Zgłoś',exact:true}).click();
      await page.getByRole('dialog').getByRole('combobox').selectOption('privacy');
      await page.getByLabel('Opis',{exact:true}).fill('Opis zgłoszenia testowego');
      await page.getByRole('button',{name:'Wyślij zgłoszenie',exact:true}).click();
      await page.getByText('Zgłoszenie przyjęte.',{exact:false}).waitFor(); assert.equal(reports,1);
      await page.getByRole('dialog').waitFor({state:'hidden'});
      await page.getByText('Moderacja nitek i komentarzy',{exact:true}).click();
      await page.getByRole('combobox').nth(1).selectOption('hide');
      await page.getByRole('combobox').last().selectOption('N4');
      await page.getByLabel('Uzasadnienie dla autora i osoby zgłaszającej',{exact:true}).fill('Powtarzane reklamy.');
      await page.getByRole('button',{name:'Zapisz decyzję i powiadom strony'}).click();
      await page.getByText('Nie ma zgłoszeń oczekujących na decyzję.').waitFor();
      assert.equal(moderated,true);
      await page.getByText('Moderacja nitek i komentarzy',{exact:true}).click();
      await page.locator('.sc-social-frame__icon').first().focus();
      assert.equal(await page.locator('.sc-social-frame__icon [role="tooltip"]').first().isVisible(),true);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`overflow at ${width}`);
      assert.equal(await page.locator('.sc-social-navigation a').count(),5);
      await page.evaluate(()=>document.fonts.ready);
      await page.screenshot({path:path.join(output,`${width}.png`),fullPage:true});
      if(width===1440)for(const votes of [0,2,3]){
        await page.goto(`https://offline.test/nitki/85?votes=${votes}`);
        await page.locator('.sc-social-frame').waitFor();
        assert.equal(await page.locator('.sc-social-frame').getAttribute('data-highlight'),String(votes>=3));
        const styles=await page.locator('.sc-social-frame__icon > svg').evaluateAll(nodes=>nodes.map(n=>({color:getComputedStyle(n).color,opacity:Number(getComputedStyle(n).opacity)})));
        if(votes<3)assert.equal(new Set(styles.map(s=>s.color)).size,1);
        else assert.ok(styles[0].opacity>styles[1].opacity && styles[1].opacity>styles[2].opacity);
      }
      await page.close();
      console.log(`PASS ${width}px: ratings, references, edit, delete, report, share, tooltip, overflow`);
    }
    for(const width of [320,390,1024,1440]) {
      const page=await browser.newPage({viewport:{width,height:1000},locale:'pl-PL'});
      page.on('pageerror',e=>errors.push(e.message));
      let continuation=null, connection={connected:true,username:'reader_x',use_x_name:false,oauth_enabled:true,connect_url:'/api/account/x/start/?mode=connect'};
      const elements=Array.from({length:8},(_,i)=>({...fixture.preview[i%3],id:i+1,position:i,note:'',link_note:i?'Wspólny temat.':''}));
      await page.route('**/*',route=>{
        const req=route.request(),url=new URL(req.url()),pathName=url.pathname;
        if(pathName==='/bundle.js')return route.fulfill({contentType:'text/javascript',body:bundle});
        if(pathName==='/api/auth/csrf/')return route.fulfill({json:{csrfToken:'test'}});
        if(pathName==='/api/account/me/')return route.fulfill({json:{authenticated:true,x_enabled:!page.url().includes('disabled'),user:{id:1,username:'reader',email_verified:true},csrfToken:'test'}});
        if(pathName==='/api/account/notifications/')return route.fulfill({json:{results:[],unread:0}});
        if(pathName==='/api/account/context-threads/8/')return route.fulfill({json:{id:8,title:'Osiem boksów',description:'',query:'',categories:[],source_ids:[],articles:[],elements,is_public:false,created_at:'2026-10-03T08:00:00Z',updated_at:'2026-10-03T08:00:00Z'}});
        if(pathName==='/api/account/context-threads/' && req.method()==='POST'){continuation=req.postDataJSON();return route.fulfill({status:201,json:{id:9,...continuation}});}
        if(pathName==='/api/account/x-connection/'){
          if(req.method()==='PATCH')connection={...connection,...req.postDataJSON()};
          if(req.method()==='DELETE'){connection={...connection,connected:false};return route.fulfill({status:204});}
          return route.fulfill({json:connection});
        }
        if(pathName.startsWith('/test/'))return route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="pl" data-theme="dark"><meta charset="utf-8"><style>${css}</style><div id="root"></div><script src="/bundle.js"></script></html>`});
        return route.abort();
      });
      await page.goto('https://offline.test/test/editor');
      await page.getByRole('button',{name:'Ułóż kontynuację',exact:true}).waitFor();
      assert.equal(await page.locator('.sc-simple-thread__box').count(),8);
      assert.equal(await page.getByRole('button',{name:'Dodaj kolejny',exact:true}).count(),0);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`editor overflow ${width}`);
      await page.screenshot({path:path.join(output,`${width}-editor.png`),fullPage:true});
      await page.getByRole('button',{name:'Ułóż kontynuację',exact:true}).click();
      await page.waitForFunction(()=>true);
      assert.equal(continuation.continues,8);
      assert.equal(continuation.items.length,1);
      assert.equal(continuation.items[0].link_id,8);
      await page.goto('https://offline.test/test/login?disabled=1');
      await page.locator('.sc-account-form').first().waitFor();
      assert.equal(await page.getByRole('button',{name:'Zaloguj przez X',exact:true}).count(),0);
      await page.goto('https://offline.test/test/login');
      await page.getByRole('button',{name:'Zaloguj przez X',exact:true}).waitFor();
      await page.goto('https://offline.test/test/settings');
      await page.getByLabel('Wyświetlany nick').selectOption('x');
      await page.waitForFunction(()=>document.querySelector('select')?.value==='x');
      assert.equal(connection.use_x_name,true);
      await page.getByRole('button',{name:'Rozłącz konto X',exact:true}).click();
      await page.getByRole('link',{name:'Połącz konto X',exact:true}).waitFor();
      assert.equal(connection.connected,false);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      await page.close();
      console.log(`PASS ${width}px: creator max 8, continuation seed, X login gating, display name and disconnect`);
    }
    assert.deepEqual(errors,[]);
  } finally {await browser.close()}
}
main().catch(error=>{console.error(error);process.exitCode=1});
