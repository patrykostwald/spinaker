import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../../../../frontend-spin/package.json", import.meta.url));
const ts = require("typescript");
const code = ts.transpileModule(readFileSync(new URL("./cite.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { buildCitation } = await import(`data:text/javascript;base64,${Buffer.from(code).toString("base64")}`);

test("cytat zawiera tytuł, autora, permalink, datę publikacji i datę dostępu", () => {
  const text = buildCitation({ author: "TVN24", title: "Budżet", publishedAt: "2026-11-03T12:00:00Z", url: "https://spin.clinic/material/3", accessedAt: "2026-11-04T08:00:00Z" });
  assert.equal(text, "TVN24. „Budżet”. spin.clinic, opublikowano: 3 listopada 2026, dostęp: 4 listopada 2026, https://spin.clinic/material/3");
});

test("brak daty publikacji jest nazwany wprost, a rodzaj trafia po tytule", () => {
  const text = buildCitation({ title: "Diagnoza", kind: "diagnoza AI", publishedAt: null, url: "https://spin.clinic/klinika/1", accessedAt: "2026-11-04T08:00:00Z" });
  assert.equal(text, "„Diagnoza” (diagnoza AI). spin.clinic, data publikacji nieustalona, dostęp: 4 listopada 2026, https://spin.clinic/klinika/1");
});

test("niepoprawna data publikacji nie psuje cytatu", () => {
  assert.match(buildCitation({ title: "X", publishedAt: "nie-data", url: "https://spin.clinic/x" }), /data publikacji nieustalona/);
});

test("strona bez daty publikacji może podać datę aktualizacji", () => {
  const text = buildCitation({ title: "Jan Kowalski", kind: "profil osoby publicznej", updatedAt: "2026-10-31T20:58:41Z", url: "https://spin.clinic/osoby-publiczne/10", accessedAt: "2026-11-05T08:00:00Z" });
  assert.equal(text, "„Jan Kowalski” (profil osoby publicznej). spin.clinic, zaktualizowano: 31 października 2026, dostęp: 5 listopada 2026, https://spin.clinic/osoby-publiczne/10");
});
