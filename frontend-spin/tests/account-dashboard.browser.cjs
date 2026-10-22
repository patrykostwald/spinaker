/* Actual React components, isolated fixtures. All requests are intercepted. */
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const webpackModule = require('next/dist/compiled/webpack/webpack'); webpackModule.init();
const { webpack } = webpackModule;
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(__dirname, '../..'), temp = path.join(root, '.pytest-tmp/086-browser'), output = path.join(root, 'reports/086-layout');
fs.mkdirSync(temp, {recursive:true}); fs.mkdirSync(output, {recursive:true});
const ui = path.join(root, 'packages/ui/src');
fs.writeFileSync(path.join(temp,'link.tsx'), `import React from 'react';export default function Link({href,children,prefetch,scroll,replace,...props}:any){return <a href={href} {...props}>{children}</a>}`);
fs.writeFileSync(path.join(temp,'navigation.ts'), `export const usePathname=()=>location.pathname;export const useRouter=()=>({push(){},replace(){},refresh(){}});export const useSearchParams=()=>new URLSearchParams();`);
fs.writeFileSync(path.join(temp,'entry.tsx'), `import React from 'react';import {createRoot} from 'react-dom/client';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import {MojeKonto} from ${JSON.stringify(path.join(ui,'components/MojeKonto'))};import {PublicSocialProfile} from ${JSON.stringify(path.join(ui,'components/PublicSocialProfile'))};const client=new QueryClient({defaultOptions:{queries:{retry:false}}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}>{location.pathname.startsWith('/profile')?<PublicSocialProfile username="autor"/>:<MojeKonto/>}</QueryClientProvider>);`);
const date='2026-10-03T09:00:00Z';
const thread={id:86,title:'Jak kontekst zmienia odbiór wypowiedzi',description:'Dwa źródła i komentarz do ich zestawienia.',is_public:true,hidden_at:null,author:'autor',author_id:2,opinions:{positive:8,doubt:3,negative:1},comments_count:4,articles:[],items_count:2,published_at:date,updated_at:date,preview:[0,1].map(n=>({id:n+1,position:n,kind:'link',title:n?'Dokument i dane do sprawdzenia':'Punkt wyjścia: wypowiedź',domain:'example.org',url:'https://example.org',note:'Komentarz autora',link_note:n?'Zestawienie ze źródłem':''}))};
const activity=[{id:'comment-1',kind:'comments',created_at:date,title:thread.title,url:'/nitki/86#comment-1',thread_id:86,body:'Sprawdź @boks 2 i pełny dokument. '.repeat(5),box_references:[2]},{id:'rating-1',kind:'ratings',created_at:date,title:thread.title,url:'/nitki/86',polarity:'doubt'},{id:'vote-1',kind:'votes',created_at:date,title:'Rozmowa o projekcie ustawy',url:'/klinika/wywiady/glosowanie',won:true,day:'2026-10-02'}];
async function main(){
  await new Promise((resolve,reject)=>webpack({mode:'development',devtool:false,entry:path.join(temp,'entry.tsx'),output:{path:temp,filename:'bundle.js'},resolve:{extensions:['.tsx','.ts','.js','.json'],modules:[path.join(root,'frontend-spin/node_modules'),'node_modules'],alias:{'next/link$':path.join(temp,'link.tsx'),'next/navigation$':path.join(temp,'navigation.ts')}},module:{rules:[{test:/\.(tsx?|css)$/,use:path.join(__dirname,'corrections.loader.cjs')}]},plugins:[new webpack.DefinePlugin({'process.env':JSON.stringify({NODE_ENV:'development',NEXT_PUBLIC_THREADS_ENABLED:'true',NEXT_PUBLIC_ACCOUNTS_ENABLED:'true',NEXT_PUBLIC_API_URL:''})})]},(e,s)=>e||s.hasErrors()?reject(e||new Error(s.toString({all:false,errors:true}))):resolve()));
  const bundle=fs.readFileSync(path.join(temp,'bundle.js'),'utf8');
  const font=fs.readFileSync(path.join(root,'backend/news/assets/fonts/Montserrat[wght].ttf')).toString('base64');
  const css=fs.readFileSync(path.join(ui,'kit/kit.css'),'utf8')+`\nbody{margin:0;background:var(--sc-bg);color:var(--sc-text);font-family:var(--sc-font-sans)}@font-face{font-family:Montserrat;src:url(data:font/ttf;base64,${font}) format('truetype');font-weight:100 900}`;
  const html=`<!doctype html><html lang="pl" data-theme="dark"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style><div id="root"></div><script src="/bundle.js"></script></html>`;
  const browser=await chromium.launch({channel:'chrome',headless:true}); const errors=[], unexpected=[], results=[];
  try {for(const width of [320,390,1024,1440]){
    const page=await browser.newPage({viewport:{width,height:1000},locale:'pl-PL',reducedMotion:'reduce'});
    page.on('pageerror',e=>errors.push(e.message));
    let profile={id:1,username:'czytelnik',bio:'Sprawdzam źródła i kontekst wypowiedzi.',date_joined:date,public_activity:true,counts:{threads:3,ratings:12,comments:4}};
    let signedIn=true, registration=null, muted=false, appealed=false, prefs={service_enabled:true,social_enabled:false,email_digest:'off',push_followed:false,push_thread_replies:false,push_spin_of_day:false};
    await page.route('**/*',route=>{
      const url=new URL(route.request().url()), p=url.pathname, method=route.request().method(), data=()=>route.request().postDataJSON();
      const json=value=>route.fulfill({json:value});
      if(p==='/bundle.js')return route.fulfill({contentType:'text/javascript',body:bundle});
      if(p==='/konto'||p==='/profile/autor')return route.fulfill({contentType:'text/html',body:html});
      if(p==='/api/auth/csrf/')return json({csrfToken:'fixture'});
      if(p==='/api/account/me/')return json({authenticated:signedIn,user:signedIn?{id:1,username:profile.username,email:'test@example.org',email_verified:true,accepted_terms_version:'2026-10-03'}:null,csrfToken:'fixture'});
      if(p==='/api/account/register/'){registration=data();return json({authenticated:false,user:null,csrfToken:'fixture'})}
      if(p==='/api/account/profile/'){if(method==='PATCH')profile={...profile,...data()};return json(profile)}
      if(p==='/api/account/context-threads/'){const status=url.searchParams.get('status');return json({results:[thread,{...thread,id:87,title:'Szkic porównania źródeł',is_public:false},{...thread,id:88,title:'Nitka oczekująca na decyzję',hidden_at:date}].filter(row=>status==='all'||!status||(row.hidden_at?status==='hidden':row.is_public?status==='published':status==='draft')),next_page:null})}
      if(p==='/api/account/activity/')return json({results:activity.filter(row=>!url.searchParams.get('kind')||url.searchParams.get('kind')==='all'||row.kind===url.searchParams.get('kind')),next_page:null});
      if(p==='/api/account/follows/')return json([{id:1,kind:'user',target_id:2,label:'autor',url:'/profile/autor'},{id:2,kind:'thread',target_id:86,label:thread.title,url:'/nitki/86'}]);
      if(p==='/api/account/favorites/'||p==='/api/account/article-favorites/')return json({results:[],next_page:null});
      if(p==='/api/account/notifications/')return json({unread:1,results:[{id:1,title:'Rozpatrzono zgłoszenie',url:'/konto#zgloszenia',kind:'report_status',read_at:null,created_at:date}]});
      if(p==='/api/account/notifications/read/')return json({unread:0});
      if(p==='/api/account/reports/')return json({results:[{id:1,mine:true,status:appealed?'pending':'removed',can_appeal:!appealed,appealed,target_kind:'comment',decisions:[{action:'hide',rule:'N4',explanation:'Powtarzająca się reklama bez związku z tematem.',created_at:date}]}],next_page:null});
      if(p==='/api/community/reports/1/'){appealed=true;return json({status:'appeal'})}
      if(p==='/api/account/notification-settings/'){if(method==='PATCH')prefs={...prefs,...data()};return json(prefs)}
      if(p==='/api/account/mutes/') {if(method==='POST')muted=true;return json({results:muted?[{target_id:2,target__username:'autor'}]:[]})}
      if(p==='/api/account/mutes/2/'){muted=false;return route.fulfill({status:204})}
      if(p==='/api/profiles/autor/')return json({...profile,id:2,username:'autor',muted,threads:{results:muted?[]:[thread],next_page:null},comments:{results:muted?[]:[activity[0]],next_page:null}});
      if(p==='/api/profiles/autor/report/')return json({id:1});
      unexpected.push(p);return route.abort();
    });
    const check=async name=>{await page.evaluate(()=>document.fonts.ready);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${name} overflow ${width}`);await page.screenshot({path:path.join(output,`${width}-${name}.png`),fullPage:true});};
    await page.goto('https://offline.test/konto'); await page.getByRole('heading',{name:'@czytelnik',exact:true}).waitFor();
    await page.getByRole('button',{name:'Pomiń',exact:true}).click();
    await check('nitki');
    for(const label of ['Szkice','Opublikowane','Ukryte']){await page.getByRole('button',{name:label,exact:true}).click();await page.locator('.sc-account-thread-list > li').first().waitFor();assert.equal(await page.locator('.sc-account-thread-list > li').count(),1)}
    const nav=page.getByRole('navigation',{name:'Sekcje konta'});
    await nav.getByRole('link',{name:'Aktywność',exact:true}).click();await page.getByText('Wywiad wybrany',{exact:false}).waitFor();await check('aktywnosc');
    await page.getByRole('button',{name:'Głosy',exact:true}).click();await page.getByText('Wywiad wybrany',{exact:false}).waitFor();assert.equal(await page.locator('.sc-account-timeline > li').count(),1);
    await nav.getByRole('link',{name:'Obserwowani',exact:true}).click();await page.getByRole('heading',{name:'Zapisane',exact:true}).waitFor();await check('obserwowani');
    await nav.getByRole('link',{name:'Powiadomienia',exact:true}).click();await page.getByText('Rozpatrzono zgłoszenie',{exact:true}).waitFor();await check('powiadomienia');
    await nav.getByRole('link',{name:'Zgłoszenia',exact:true}).click();await page.getByRole('button',{name:'Odwołaj się',exact:true}).waitFor();await check('zgloszenia');
    await page.getByRole('button',{name:'Odwołaj się',exact:true}).click();await page.getByLabel('Uzasadnienie odwołania').fill('Proszę o ponowną ocenę.');await page.getByRole('button',{name:'Wyślij odwołanie'}).click();await page.getByText('Wykorzystano jednorazowe odwołanie.').waitFor();assert.equal(await page.getByRole('button',{name:'Odwołaj się',exact:true}).count(),0);
    await nav.getByRole('link',{name:'Ustawienia',exact:true}).click();await page.getByRole('button',{name:'Zapisz profil',exact:true}).waitFor();await check('ustawienia');
    await page.getByLabel('Nick',{exact:true}).fill('nowy_nick');await page.getByRole('button',{name:'Zapisz profil',exact:true}).click();await page.getByRole('heading',{name:'@nowy_nick',exact:true}).waitFor();
    await page.getByLabel('Powiadomienia społecznościowe',{exact:true}).click();await page.getByText('Zapisano powiadomienia.',{exact:true}).waitFor();assert.equal(prefs.social_enabled,true);
    await page.goto('https://offline.test/profile/autor');await page.getByRole('heading',{name:'@autor',exact:true}).waitFor();await check('profil');
    await page.getByRole('button',{name:'Komentarze',exact:true}).click();await page.locator('.sc-account-timeline').waitFor();await check('profil-komentarze');
    await page.getByRole('button',{name:'Wycisz',exact:true}).click();await page.getByText('Wyciszono nitki i komentarze tej osoby.').waitFor();assert.ok(muted);
    await page.getByRole('button',{name:'Odcisz',exact:true}).click();await page.getByRole('button',{name:'Wycisz',exact:true}).waitFor();
    await page.getByRole('button',{name:'Zgłoś',exact:true}).first().click();await page.getByRole('dialog').getByRole('button',{name:'Wyślij zgłoszenie'}).click();await page.getByText('Zgłoszenie przyjęte.',{exact:false}).waitFor();
    signedIn=false;await page.goto('https://offline.test/konto');await page.getByRole('button',{name:'Zaloguj się lub załóż konto'}).click();await page.getByRole('button',{name:'Nie masz konta? Zarejestruj się'}).click();
    await page.getByLabel('Nazwa użytkownika',{exact:false}).fill('nowy_czytelnik');await page.getByLabel('E-mail',{exact:true}).fill('new@example.org');await page.getByLabel('Hasło',{exact:false}).fill('Str0ng~unique~086!');
    await page.getByRole('checkbox',{name:/Akceptuję/}).check();
    assert.equal(await page.getByRole('checkbox',{name:/newsletter/}).isChecked(),false);
    await check('rejestracja');await page.getByRole('button',{name:'Utwórz konto'}).click();assert.equal(registration,null);
    await page.getByRole('checkbox',{name:'Mam ukończone 18 lat.'}).check();await page.getByRole('button',{name:'Utwórz konto'}).click();await page.getByText('Sprawdź pocztę, aby potwierdzić e-mail.',{exact:false}).waitFor();assert.ok(registration.adult);assert.equal(registration.newsletter,false);assert.ok(!('accepted_privacy' in registration));
    results.push({width,overflow:false,sections:6,profile:true,appeal:true,settings:true,mute:true});console.log(`PASS ${width}px: six sections, profile, appeal, settings, mute, report, no overflow`);await page.close();
  }assert.deepEqual(errors,[]);assert.deepEqual(unexpected,[]);fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));}finally{await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
