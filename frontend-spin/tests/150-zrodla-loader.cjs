// Wspólny pomocnik testów 151-154 („Teraz”: łącze i zdrowie źródeł): wczytuje moduły TS/TSX z app/przeszlosc/teraz razem z ich
// względnymi importami (typescript.transpileModule), z podstawianymi modułami zewnętrznymi. Pliki .css są pomijane.
// Sam nie zawiera testów.
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const root = path.join(__dirname, '..');
const dir = 'app/przeszlosc/teraz';
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

function utworzLoader(mocks = {}, { fetch } = {}) {
  const cache = new Map();
  function load(file) {
    if (file.endsWith('.json')) return JSON.parse(read(file));
    const bez = file.replace(/\.tsx?$/, '');
    const wzgledna = [`${bez}.ts`, `${bez}.tsx`, `${bez}/index.ts`].find(k => fs.existsSync(path.join(root, k)));
    if (!wzgledna) throw new Error(`brak modułu ${file}`);
    const abs = path.join(root, wzgledna);
    if (cache.has(abs)) return cache.get(abs).exports;
    const source = ts.transpileModule(fs.readFileSync(abs, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
    }).outputText;
    const module = { exports: {} };
    cache.set(abs, module);
    const req = name => {
      if (name in mocks) return mocks[name];
      if (name.endsWith('.css')) return {};
      if (name.startsWith('.')) return load(path.relative(root, path.resolve(path.dirname(abs), name)).split(path.sep).join('/'));
      return require(name);
    };
    new Function('module', 'exports', 'require', 'process', 'fetch', source)(module, module.exports, req, { env: {} },
      (...args) => (fetch ?? (() => { throw new Error('bez sieci'); }))(...args));
    return module.exports;
  }
  return load;
}

/** Tekst widoczny w znaczniku HTML (bez tagów i encji). */
const tekst = html => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();

module.exports = { root, dir, read, utworzLoader, tekst };
