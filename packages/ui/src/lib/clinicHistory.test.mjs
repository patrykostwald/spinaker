import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../../../../frontend-spin/package.json", import.meta.url));
const ts = require("typescript");
const code = ts.transpileModule(readFileSync(new URL("./clinicHistory.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const history = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);
const visit = id => ({ type: "diagnosis", id, title: "Nagłówek", camp: "government", verdict: "spin", intensity: 70, author: "Autor" });
globalThis.window = new EventTarget();

test("history retains 12 visits, deduplicates by type and ID, and moves revisits first", () => {
  const storage = new Map();
  globalThis.localStorage = { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
  for (let id = 1; id <= 14; id++) history.rememberClinicVisit(visit(id));
  assert.deepEqual(history.readClinicHistory().map(item => item.id), [14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3]);
  history.rememberClinicVisit({ ...visit(6), title: "Nowy nagłówek" });
  assert.equal(history.readClinicHistory()[0].title, "Nowy nagłówek");
  assert.equal(history.readClinicHistory().filter(item => item.id === 6).length, 1);
  history.rememberClinicVisit({ ...visit(6), type: "interview", camp: null, guest: "Gość" });
  assert.equal(history.readClinicHistory().filter(item => item.id === 6).length, 2);
  assert.ok(Date.parse(history.readClinicHistory()[0].viewed_at));
  history.writeClinicHistory([]);
  assert.equal(storage.has(history.CLINIC_HISTORY_KEY), false);
  assert.deepEqual(history.readClinicHistory(), []);
});

test("corrupt or unavailable browser storage does not break the page", () => {
  for (const raw of ["invalid", "null", "{}", '[null,{}, {"type":"diagnosis","id":-1}]']) {
    globalThis.localStorage = { getItem: () => raw };
    assert.deepEqual(history.readClinicHistory(), []);
  }
  globalThis.localStorage = new Proxy({}, { get() { throw new Error("Storage blocked"); } });
  assert.deepEqual(history.readClinicHistory(), []);
  assert.doesNotThrow(() => history.rememberClinicVisit(visit(1)));
  let cleared = false;
  window.addEventListener(history.CLINIC_HISTORY_EVENT, event => { cleared = event.detail.length === 0; }, { once: true });
  assert.doesNotThrow(() => history.writeClinicHistory([]));
  assert.ok(cleared);
});
