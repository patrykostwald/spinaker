import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../../../../frontend-spin/package.json", import.meta.url));
const ts = require("typescript");
const code = ts.transpileModule(readFileSync(new URL("./clinicNavigation.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const navigation = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);

test("powrót zachowuje pełny adres filtrów i odrzuca obce cele", () => {
  const url = "/klinika/diagnozy?account=42&q=teza%20bez%20dowodu&sort=strong";
  assert.equal(navigation.clinicResultsUrl(url), url);
  for (const value of [null, "https://example.org/", "//example.org", "javascript:alert(1)", "/klinika/diagnozy-inna"]) {
    assert.equal(navigation.clinicResultsUrl(value), "/klinika/diagnozy");
  }
});

test("pozycja i liczba stron należą do konkretnego zestawu filtrów", () => {
  const storage = new Map();
  globalThis.window = { scrollY: 1742 };
  globalThis.sessionStorage = { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
  const url = "/klinika/diagnozy?account=42";
  navigation.rememberClinicResults(url, 3);
  assert.deepEqual(navigation.readClinicResults(url), { top: 1742, pages: 3 });
  assert.equal(navigation.readClinicResults("/klinika/diagnozy?account=43"), null);
  navigation.clearClinicResults(url);
  assert.equal(navigation.readClinicResults(url), null);
});

test("uszkodzony albo niedostępny zapis nie przerywa nawigacji", () => {
  for (const value of ["not json", '{"top":-1,"pages":3}', '{"top":200,"pages":0}', '{"top":200,"pages":1.5}']) {
    globalThis.sessionStorage = { getItem: () => value };
    assert.equal(navigation.readClinicResults("/klinika/diagnozy"), null);
  }
  globalThis.sessionStorage = new Proxy({}, { get() { throw new Error("Storage disabled"); } });
  assert.equal(navigation.readClinicResults("/klinika/diagnozy"), null);
  assert.doesNotThrow(() => navigation.rememberClinicResults("/klinika/diagnozy", 2));
  assert.doesNotThrow(() => navigation.clearClinicResults("/klinika/diagnozy"));
});
