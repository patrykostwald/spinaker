import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../../../../frontend-spin/package.json", import.meta.url));
const ts = require("typescript");
const code = ts.transpileModule(readFileSync(new URL("./models.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const models = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);

test("pełna nazwa modelu to wersja i firma, bez ścieżki dostawcy", () => {
  assert.equal(models.modelFullName("openai/gpt-oss-20b"), "gpt-oss-20b · OpenAI");
  assert.equal(models.modelFullName("speakleash/Bielik-11B-v3.0-Instruct:publicai"), "Bielik-11B-v3.0-Instruct · SpeakLeash / Cyfronet");
  assert.equal(models.modelFullName("gemini-3.8-flash"), "gemini-3.8-flash · Google");
  assert.equal(models.modelFullName("nieznany-model-1"), "nieznany-model-1");
  assert.equal(models.modelFullName("x", "Firma"), "x · Firma");
});

test("zbiorcze „konsylium” i brak modelu opisane słowami", () => {
  assert.match(models.modelFullName("konsylium"), /Konsylium AI/);
  assert.equal(models.modelFullName(""), "model nieznany");
});

test("zgodność modeli podana liczbami", () => {
  assert.equal(models.agreementWords("4/5"), "4 z 5 odpowiadających modeli zgodnych z wynikiem końcowym");
  assert.equal(models.agreementWords("4 / 5"), "4 z 5 odpowiadających modeli zgodnych z wynikiem końcowym");
  assert.equal(models.agreementWords("brak"), "");
  assert.equal(models.agreementWords(null), "");
});
