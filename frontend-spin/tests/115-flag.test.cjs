const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const routing = require('../lib/threadsRouting');
const ui = file => fs.readFileSync(path.join(__dirname, '../../packages/ui/src', file), 'utf8');

function load(file, env, mocks = {}, globals = {}) {
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exports = {};
  vm.runInNewContext(source, {
    exports, process: { env },
    require: name => Object.hasOwn(mocks, name) ? mocks[name] : require(path.resolve(__dirname, name)),
    URL, Date, Response, ...globals,
  });
  return exports;
}

test('flag false: stary portalowy watek /thread/* tez prowadzi na /klinika (302), wyjatek tylko dla podgladu', () => {
  const rows = routing.threadRedirects(false).filter(row => row.missing);
  for (const source of ['/thread', '/thread/:path*']) {
    const row = rows.find(item => item.source === source);
    assert.ok(row, source);
    assert.equal(row.destination, '/klinika');
    assert.equal(row.permanent, false);
    assert.equal(row.missing[0].key, 'sc_preview');
  }
});

test('flag true: /thread zostaje zwyklą trasą (bez przekierowania)', () => {
  assert.ok(routing.threadRedirects(true).every(row => !row.source.startsWith('/thread')));
});

test('apple-app-site-association: /thread/* tylko z flagą true', () => {
  for (const [flag, expectThread] of [['true', true], ['false', false], [undefined, false]]) {
    const env = { APPLE_TEAM_ID: 'T', APPLE_BUNDLE_ID: 'B', NEXT_PUBLIC_THREADS_ENABLED: flag };
    const source = fs.readFileSync(path.join(__dirname, '../app/.well-known/apple-app-site-association/route.ts'), 'utf8');
    const paths = [...source.matchAll(/\[('[^\]]*)\]/g)].map(match => match[1]);
    const withFlag = paths[0], without = paths[1];
    const used = env.NEXT_PUBLIC_THREADS_ENABLED === 'true' ? withFlag : without;
    assert.equal(used.includes('/thread/*'), expectThread, String(flag));
    assert.equal(/spinki/.test(used), flag === 'true');
  }
});

test('metadane wyszukiwarki nie wspominaja o spinkach przy fladze false', () => {
  for (const [flag, expectSpinki] of [['true', true], ['false', false], [undefined, false]]) {
    const layout = load('../app/search/layout.tsx', { NEXT_PUBLIC_THREADS_ENABLED: flag }, {
      'next': {},
      '../../lib/threadsRouting': { ...routing, isThreadsEnabled: () => routing.isThreadsEnabled({ NEXT_PUBLIC_THREADS_ENABLED: flag }) },
    });
    assert.equal(/spin(ek|ki)/i.test(layout.metadata.description + layout.metadata.title), expectSpinki, String(flag));
  }
});

test('komponenty konta: teksty o spinkach, linki /spinki i karty zalezne od flagi', () => {
  const panel = ui('components/MojeKonto.tsx');
  assert.match(panel, /threadsEnabled \? 'Zaloguj się, aby układać spinki, oceniać i komentować\.' : 'Zaloguj się, aby oceniać i komentować\.'/);
  assert.match(panel, /threadRows = threadsEnabled \?/);
  assert.match(panel, /saved = threadsEnabled \?/);
  assert.match(panel, /enabled: threadsEnabled/);
  const parts = ui('components/AccountDashboardParts.tsx');
  assert.match(parts, /filter\(\(\[key\]\) => threadsEnabled \|\| key !== 'threads'\)/);
  assert.match(parts, /\{threadsEnabled && !!row\.box_references\?\.length/);
  const phase2 = ui('components/AccountPhase2.tsx');
  assert.match(phase2, /THREADS_ENABLED \? \['figure', 'user'\] as const : \['figure'\] as const/);
  assert.match(phase2, /THREADS_ENABLED \? 'Obserwuj wybrane osoby i spinki/);
  const publicProfile = ui('components/PublicSocialProfile.tsx');
  assert.match(publicProfile, /const section = threadsEnabled \? chosen : 'comments'/);
  assert.match(publicProfile, /\{threadsEnabled && <button/);
  assert.match(publicProfile, /\{threadsEnabled && <FollowButton kind="user"/);
});

test('dialogi konta, usuwanie konta, odzyskiwanie i udostepnianie na X nie obiecuja spinek bez flagi', () => {
  for (const file of ['components/AccountDialog.tsx', 'components/AccountDelete.tsx', 'components/AccountRecovery.tsx', 'components/ShareOnX.tsx']) {
    const source = ui(file);
    assert.match(source, /useFeature/, file);
    assert.match(source, /THREADS_ENABLED/, file);
  }
  assert.match(ui('components/AccountDelete.tsx'), /threadsEnabled \? "Usuń konto i moje spinki" : "Usuń konto i moje dane"/);
});

test('pasek kontekstu: przykladowa spinka i zaproszenie dla dziennikarzy renderuja sie tylko z flagą', () => {
  assert.match(ui('components/ContextThreadStrip.tsx'), /return THREADS_ENABLED \? <ExampleStrip \/> : null;/);
  assert.match(ui('components/ContextThreadStrip.tsx'), /props\.articleId \|\| props\.figureId \|\| props\.url\) return THREADS_ENABLED \?/);
  assert.match(ui('components/JournalistInvite.tsx'), /if \(!useFeature\("THREADS_ENABLED"\)\) return null;/);
});

test('zadnego linku do /jak-dziala poza kodem za flagą', () => {
  const intro = fs.readFileSync(path.join(__dirname, '../app/FirstVisitIntro.tsx'), 'utf8');
  assert.match(intro, /if \(!threads \|\|/);
  assert.match(fs.readFileSync(path.join(__dirname, '../lib/documents/AboutDocument.tsx'), 'utf8'), /\{threads && <HowItWorksFilm/);
});

test('onboarding konta: kroki o polaczeniach i autorach spinek tylko z flagą', () => {
  const phase2 = ui('components/AccountPhase2.tsx');
  assert.match(phase2, /threadsEnabled \? \['Oceniaj połączenia'/);
  assert.match(phase2, /: \['Oceniaj diagnozy', 'Oceniasz diagnozy Dr\. Spina/);
  assert.match(phase2, /threadsEnabled \? \['Obserwuj', 'Obserwuj polityków i autorów/);
});
