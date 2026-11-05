import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../../../../frontend-spin/package.json", import.meta.url));
const ts = require("typescript");
const code = ts.transpileModule(readFileSync(new URL("./plural.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { plural, FORMS } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);

test("deklinacja: diagnoza/diagnozy/diagnoz", () => {
  const got = [0, 1, 2, 3, 4, 5, 11, 12, 14, 22, 24, 42, 100, 112].map(n => plural(n, FORMS.diagnosis));
  assert.deepEqual(got, ["diagnoz", "diagnoza", "diagnozy", "diagnozy", "diagnozy", "diagnoz", "diagnoz", "diagnoz", "diagnoz", "diagnozy", "diagnozy", "diagnozy", "diagnoz", "diagnoz"]);
});

test("deklinacja: wpis, materiał, dzień", () => {
  assert.equal(plural(1, FORMS.entry), "wpis");
  assert.equal(plural(3, FORMS.entry), "wpisy");
  assert.equal(plural(5, FORMS.entry), "wpisów");
  assert.equal(plural(42, FORMS.material), "materiały");
  assert.equal(plural(12, FORMS.material), "materiałów");
  assert.equal(plural(1, FORMS.day), "dzień");
  assert.equal(plural(24, FORMS.day), "dni");
  assert.equal(plural(5, FORMS.source), "źródeł");
  assert.equal(plural(22, FORMS.vote), "głosowania");
});
